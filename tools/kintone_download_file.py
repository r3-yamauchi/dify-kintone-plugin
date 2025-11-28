import json
from collections.abc import Generator
from io import BytesIO
from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException, Timeout, HTTPError

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .common import (
    build_headers,
    is_blank,
    log_parameters,
    log_response,
    normalize_api_tokens,
    normalize_domain,
    resolve_timeout,
    resolve_tool_parameter,
)


class KintoneDownloadFileTool(Tool):
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # kintone の認証情報を取得
        raw_domain = resolve_tool_parameter(self, tool_parameters, "kintone_domain")
        if is_blank(raw_domain):
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        try:
            kintone_domain = normalize_domain(raw_domain)
        except ValueError:
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        try:
            kintone_api_token = normalize_api_tokens(
                resolve_tool_parameter(self, tool_parameters, "kintone_api_token")
            )
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 30.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        # ファイルキーの取得
        file_key = tool_parameters.get("file_key")
        if not file_key:
            yield self.create_text_message("ファイルキーが見つかりません。file_keyパラメータを確認してください。")
            return

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "has_file_key": bool(file_key),
            },
        )

        # APIリクエスト用のヘッダー設定
        headers = build_headers(
            kintone_api_token,
            content_type=None,
            extra={"Accept": "*/*"},
        )

        # kintone のファイルダウンロード API のエンドポイント
        url = f"{kintone_domain}/k/v1/file.json"

        # クエリパラメータの設定
        params = {
            "fileKey": file_key
        }

        try:
            # APIリクエストの実行
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=timeout_seconds,
                    stream=True  # ストリーミングモードを有効化
                )
                # HTTPエラーがあれば例外を発生
                response.raise_for_status()
            except Timeout:
                yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
                return
            except HTTPError as e:
                # kintoneのエラーメッセージをそのまま返す
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                except (json.JSONDecodeError, AttributeError):
                    error_message = str(e)

                yield self.create_text_message(f"kintone APIエラー: {error_message}")
                return
            except RequestException as e:
                yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(e)}")
                return

            # Content-Typeとファイル名を取得
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            file_name = self._extract_filename(response.headers.get('Content-Disposition'))

            # ファイルデータの読み込み（15MB制限）
            max_file_size = 15 * 1024 * 1024  # 15MB
            buffer = BytesIO()
            total_size = 0
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                buffer.write(chunk)
                total_size += len(chunk)
                if total_size > max_file_size:
                    yield self.create_text_message("ファイルサイズが大きすぎます。15MB以下のファイルを指定してください。")
                    return
            file_data = buffer.getvalue()

            if total_size > int(max_file_size * 0.9):
                yield self.create_log_message(
                    label="Large file download",
                    data={"size": total_size, "threshold": max_file_size},
                )

            metadata = {"mime_type": content_type}
            if file_name:
                metadata["file_name"] = file_name

            # create_blob_messageを使用してファイルを返す
            yield self.create_blob_message(
                file_data,
                metadata
            )
            yield self.create_json_message(
                {
                    "file_key": file_key,
                    "mime_type": content_type,
                    "size": total_size,
                    "file_name": file_name,
                    "download_url": url,
                }
            )
            yield log_response(
                self,
                "kintone download metadata",
                {
                    "file_key": file_key,
                    "mime_type": content_type,
                    "size": total_size,
                    "file_name": file_name,
                    "download_url": url,
                },
            )

        except Exception as e:
            # 予期しないエラーの処理
            error_message = f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(e)}"
            yield self.create_text_message(error_message)
    def _extract_filename(self, content_disposition: Optional[str]) -> Optional[str]:
        """Content-Dispositionヘッダーからファイル名を抽出する。"""

        if not content_disposition:
            return None
        parts = [part.strip() for part in content_disposition.split(';') if part.strip()]
        for part in parts:
            if part.lower().startswith('filename*='):
                _, value = part.split('=', 1)
                # RFC 5987: charset'lang'value
                stripped = value.strip('"')
                try:
                    _, _, encoded = stripped.split("'", 2)
                    return requests.utils.unquote(encoded)
                except ValueError:
                    try:
                        encoded = stripped.split("''", 1)[1]
                        return requests.utils.unquote(encoded)
                    except (IndexError, ValueError):
                        continue
            if part.lower().startswith('filename='):
                _, value = part.split('=', 1)
                filename = value.strip('"')
                return filename or None
        return None
