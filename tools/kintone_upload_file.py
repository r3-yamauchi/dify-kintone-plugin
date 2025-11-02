"""
where: tools/kintone_upload_file.py
what: kintoneへのファイルアップロードを行うDifyツール
why: チャットフローから渡されたファイルをkintoneに保存しfileKeyを取得するため
"""

from __future__ import annotations

import base64
import binascii
import copy
import json
import math
import re
from collections.abc import Generator
from typing import Any, Dict, List, Tuple

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

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


class KintoneUploadFileTool(Tool):
    """kintoneのファイルAPIにアップロードしfileKeyを返却するツール。"""

    # kintone REST API の1ファイル上限 (公式ドキュメント基準: 1GB)。
    # Difyツールとしては32MB程度が実用的な上限なので、双方の条件に収まる値を採用する。
    MAX_UPLOAD_BYTES = min(1024 * 1024 * 1024, 32 * 1024 * 1024)

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
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

        file_parameter = tool_parameters.get("upload_file")
        if file_parameter is None:
            yield self.create_text_message("アップロードするファイルが見つかりません。upload_fileパラメータを確認してください。")
            return

        records_mapping_param = tool_parameters.get("records_mapping")

        try:
            file_names_param = tool_parameters.get("file_names")
            file_name_overrides = self._parse_file_names(file_parameter, file_names_param)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            files_to_upload = self._prepare_files(file_parameter, file_name_overrides)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        if not files_to_upload:
            yield self.create_text_message("アップロードするファイルが指定されていません。少なくとも1件のファイルを選択してください。")
            return

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 30.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return
        url = f"https://{kintone_domain}/k/v1/file.json"
        headers = build_headers(kintone_api_token, content_type=None)

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "file_count": len(files_to_upload),
                "has_records_mapping": records_mapping_param is not None,
            },
        )

        uploaded_files: List[Dict[str, Any]] = []
        uploaded_details: List[Dict[str, Any]] = []
        file_names: List[str] = []

        try:
            for file_bytes, file_name, mime_type in files_to_upload:
                if not file_bytes:
                    yield self.create_text_message(f"ファイル '{file_name}' の内容が空です。別のファイルを指定してください。")
                    return
                if len(file_bytes) > self.MAX_UPLOAD_BYTES:
                    limit_mb = max(1, math.ceil(self.MAX_UPLOAD_BYTES / (1024 * 1024)))
                    yield self.create_text_message(
                        f"ファイル '{file_name}' のサイズが大きすぎます。{limit_mb}MB 以下のファイルを指定してください。"
                    )
                    return

                files = {
                    "file": (file_name, file_bytes, mime_type or "application/octet-stream"),
                }

                try:
                    response = requests.post(
                        url,
                        headers=headers,
                        files=files,
                        timeout=timeout_seconds,
                    )
                    response.raise_for_status()
                except Timeout:
                    yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
                    return
                except HTTPError as error:
                    status_code = error.response.status_code if getattr(error, "response", None) else "unknown"
                    if status_code == 401:
                        yield self.create_text_message("kintone APIの認証に失敗しました。APIトークンを確認してください。")
                    elif status_code == 403:
                        yield self.create_text_message("kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。")
                    elif status_code == 404:
                        yield self.create_text_message("kintone APIのエンドポイントが見つかりません。ドメイン設定を確認してください。")
                    elif isinstance(status_code, int) and status_code >= 500:
                        yield self.create_text_message(f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。")
                    else:
                        yield self.create_text_message(f"kintone APIリクエスト中にHTTPエラーが発生しました: {str(error)}")
                    return
                except RequestException as error:
                    yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(error)}")
                    return

                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    yield self.create_text_message("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")
                    return

                file_key = response_data.get("fileKey")
                if not file_key:
                    yield self.create_text_message("ファイルはアップロードされましたが、fileKeyを取得できませんでした。")
                    return

                yield self.create_log_message(
                    label="Uploaded file",
                    data={
                        "file_name": file_name,
                        "size": len(file_bytes),
                        "mime_type": mime_type or "application/octet-stream",
                        "status_code": response.status_code,
                    },
                )

                uploaded_files.append({"fileKey": str(file_key)})
                uploaded_details.append(
                    {
                        "fileKey": str(file_key),
                        "file_name": file_name,
                        "size": len(file_bytes),
                        "mime_type": mime_type or "application/octet-stream",
                        "status_code": response.status_code,
                    }
                )
                file_names.append(file_name)

            yield self.create_variable_message("uploaded_files", uploaded_files)

            json_payload: Dict[str, Any] = {
                "uploaded_files": uploaded_files,
                "details": uploaded_details,
            }

            if records_mapping_param is not None:
                try:
                    records_payload = self._build_records_payload(records_mapping_param, uploaded_files)
                except ValueError as error:
                    yield self.create_text_message(str(error))
                    return

                records_json = json.dumps(records_payload, ensure_ascii=False)
                yield self.create_variable_message("records_data", records_json)
                json_payload = {
                    "uploaded_files": uploaded_files,
                    "records_data": records_payload,
                    "details": uploaded_details,
                }
                yield self.create_log_message(
                    label="Records mapping summary",
                    data={
                        "records_count": len(records_payload.get("records", [])),
                    },
                )

            yield self.create_json_message(json_payload)
            yield log_response(
                self,
                "kintone upload summary",
                {
                    "file_count": len(uploaded_files),
                    "details": uploaded_details,
                    "has_records_payload": records_mapping_param is not None,
                },
            )

            if len(uploaded_files) == 1:
                yield self.create_text_message(
                    f"ファイル '{file_names[0]}' のアップロードに成功しました。fileKey: {uploaded_files[0]['fileKey']}"
                )
            else:
                joined_keys = ", ".join(item["fileKey"] for item in uploaded_files)
                joined_names = ", ".join(file_names)
                yield self.create_text_message(
                    f"{len(uploaded_files)}件のファイルをアップロードしました。ファイル: {joined_names} / fileKeys: {joined_keys}"
                )

        except Exception as error:  # pylint: disable=broad-except
            yield self.create_text_message(f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(error)}")

    def _parse_file_names(
        self,
        payload: Any,
        raw_names: Any,
    ) -> List[str] | None:
        """file_namesパラメータを解析してファイル名リストを返す。"""

        if raw_names is None:
            return None

        if isinstance(payload, list):
            payload_count = len(payload)
        else:
            payload_count = 1

        def _sanitize_list(values: List[Any]) -> List[str] | None:
            sanitized: List[str] = []
            for value in values:
                if not isinstance(value, str):
                    return None
                trimmed = value.strip()
                if not trimmed:
                    return None
                try:
                    sanitized.append(self._normalize_filename(trimmed))
                except ValueError:
                    return None
            return sanitized

        if isinstance(raw_names, list):
            cleaned = _sanitize_list(raw_names)
            if cleaned is None:
                return None
        elif isinstance(raw_names, str):
            stripped = raw_names.strip()
            if not stripped:
                return None
            if stripped.startswith('['):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    return None
                if not isinstance(parsed, list):
                    return None
                cleaned = _sanitize_list(parsed)
                if cleaned is None:
                    return None
            else:
                try:
                    cleaned = [self._normalize_filename(stripped)]
                except ValueError:
                    return None
        else:
            return None

        if payload_count == 1:
            if len(cleaned) > 1:
                raise ValueError("file_names パラメータが不正です。単一ファイルの場合は1件のみ指定してください。")
            return cleaned

        # payload_count > 1
        if len(cleaned) != payload_count:
            raise ValueError("file_names パラメータはアップロードするファイル数と同じ数のファイル名を指定してください。")

        return cleaned

    def _prepare_files(
        self,
        payload: Any,
        override_names: List[str] | None,
    ) -> List[Tuple[bytes, str, str | None]]:
        """アップロード対象のファイル群を正規化する。"""

        if isinstance(payload, list):
            if not payload:
                return []
            if override_names and len(override_names) != len(payload):
                raise ValueError("file_names パラメータはアップロードするファイル数と同じ数のファイル名を指定してください。")
            return [
                self._normalize_single_file(item, override_names[idx] if override_names else None)
                for idx, item in enumerate(payload)
            ]

        if override_names and len(override_names) != 1:
            raise ValueError("file_names パラメータが不正です。単一ファイルの場合は1件のみ指定してください。")

        return [self._normalize_single_file(payload, override_names[0] if override_names else None)]

    def _normalize_single_file(
        self,
        payload: Any,
        file_name_override: str | None = None,
    ) -> Tuple[bytes, str, str | None]:
        """単一ファイル表現をバイト列へ変換する。"""

        mapping = self._coerce_file_payload(payload)
        if mapping is not None:
            meta = mapping.get("meta") or {}
            data_field = mapping.get("data")

            if data_field is None:
                file_bytes = self._download_file_payload(mapping)
            else:
                if isinstance(data_field, str):
                    try:
                        file_bytes = base64.b64decode(data_field, validate=True)
                    except (ValueError, binascii.Error):
                        raise ValueError("ファイルデータをbase64として解釈できませんでした。") from None
                elif isinstance(data_field, bytes):
                    file_bytes = data_field
                else:
                    raise ValueError("upload_fileのdataフィールド形式が不明です。base64文字列で指定してください。")

            mime_type = meta.get("mime_type") or mapping.get("mime_type")
            filename_candidate = (
                file_name_override
                or meta.get("filename")
                or mapping.get("filename")
                or "uploaded-file"
            )
            filename_candidate = self._normalize_filename(filename_candidate)

            return file_bytes, filename_candidate, mime_type

        if isinstance(payload, str):
            try:
                file_bytes = base64.b64decode(payload, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("upload_fileをbase64文字列として解析できませんでした。") from None

            filename = self._normalize_filename(file_name_override or "uploaded-file")
            return file_bytes, filename, None

        raise ValueError("upload_fileパラメータの形式がサポートされていません。")

    def _coerce_file_payload(self, payload: Any) -> Dict[str, Any] | None:
        """upload_fileエントリを辞書形式に正規化する。"""

        if isinstance(payload, dict):
            return payload

        for attr in ("model_dump", "dict"):
            if hasattr(payload, attr):
                try:
                    data = getattr(payload, attr)()
                except TypeError:
                    data = getattr(payload, attr)(by_alias=True)
                if isinstance(data, dict):
                    return data

        if hasattr(payload, "__dict__"):
            data = vars(payload)
            if isinstance(data, dict):
                return data

        return None

    def _download_file_payload(self, payload: Dict[str, Any]) -> bytes:
        """Difyのtool_fileなど、URL経由で渡されるファイルをダウンロードする。"""

        url = payload.get("url") or payload.get("remote_url")
        if not url:
            raise ValueError("upload_fileにdataフィールドが存在せず、ダウンロード用URLも指定されていません。")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Timeout:
            raise ValueError("ファイルのダウンロードがタイムアウトしました。再度お試しください。") from None
        except HTTPError as error:
            status_code = error.response.status_code if getattr(error, "response", None) else "unknown"
            raise ValueError(f"ファイルのダウンロードに失敗しました（ステータスコード: {status_code}）。") from None
        except RequestException as error:
            raise ValueError(f"ファイルのダウンロード中にエラーが発生しました: {str(error)}") from None

        content = response.content
        if not content:
            raise ValueError("ダウンロードしたファイルの内容が空でした。")
        return content

    def _normalize_filename(self, filename: str) -> str:
        """kintoneに渡すファイル名を正規化する。"""

        name = filename.strip()
        if not name:
            raise ValueError("file_names パラメータに空のファイル名が含まれています。")

        name = name.replace("\\", "/")
        name = name.split("/")[-1]

        if not re.match(r'^[^\\/:*?"<>|]+$', name):
            raise ValueError("ファイル名に使用できない文字が含まれています。")

        if len(name.encode("utf-8")) > 255:
            raise ValueError("ファイル名が長すぎます。255バイト以下にしてください。")

        return name

    def _build_records_payload(
        self,
        mapping_param: Any,
        uploaded_files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """records_mappingパラメータからkintone_upsert_records向けのrecordsデータを生成する。"""

        if isinstance(mapping_param, str):
            try:
                mapping = json.loads(mapping_param)
            except json.JSONDecodeError:
                raise ValueError("records_mapping はJSON文字列で指定してください。") from None
        elif isinstance(mapping_param, dict):
            mapping = mapping_param
        else:
            raise ValueError("records_mapping はJSON文字列またはオブジェクトで指定してください。")

        records_config = mapping.get("records") if isinstance(mapping, dict) else None
        if not isinstance(records_config, list) or not records_config:
            raise ValueError("records_mapping には 'records' 配列を含めてください。")

        if not uploaded_files:
            raise ValueError("アップロードされたファイルが存在しません。")

        file_count = len(uploaded_files)
        record_count = len(records_config)

        if record_count == 1:
            attachments_per_record = [uploaded_files]
        else:
            if record_count != file_count:
                raise ValueError("records_mapping のレコード数とアップロードしたファイル数が一致しません。")
            attachments_per_record = [[uploaded_files[i]] for i in range(file_count)]

        composed_records: List[Dict[str, Any]] = []

        for idx, base_entry in enumerate(records_config):
            if not isinstance(base_entry, dict):
                raise ValueError("records_mapping の各要素はオブジェクトで指定してください。")

            entry = copy.deepcopy(base_entry)
            attachment_field = entry.pop("attachment_field", None)
            if not isinstance(attachment_field, str) or not attachment_field.strip():
                raise ValueError("records_mapping の各要素に attachment_field を指定してください。")

            record_body = entry.setdefault("record", {})
            if not isinstance(record_body, dict):
                raise ValueError("records_mapping の 'record' はオブジェクトで指定してください。")

            record_body[attachment_field] = {
                "value": [{"fileKey": item["fileKey"]} for item in attachments_per_record[idx]]
            }

            composed_records.append(entry)

        return {"records": composed_records}
