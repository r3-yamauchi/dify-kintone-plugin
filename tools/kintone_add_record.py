import json
from collections.abc import Generator
from typing import Any, Dict, List

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
    normalize_app_id,
    normalize_domain,
    resolve_timeout,
    resolve_tool_parameter,
)


class KintoneAddRecordTool(Tool):
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # kintone の認証情報およびアプリIDを取得
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
            kintone_app_id = normalize_app_id(tool_parameters.get("kintone_app_id"))
        except ValueError:
            yield self.create_text_message("kintone アプリIDには正の整数を指定してください。")
            return

        try:
            kintone_api_token = normalize_api_tokens(
                resolve_tool_parameter(self, tool_parameters, "kintone_api_token")
            )
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        # レコードデータの取得
        record_data = tool_parameters.get("record_data")
        if record_data in (None, ""):
            yield self.create_text_message("レコードデータが見つかりません。record_dataパラメータを確認してください。")
            return

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "kintone_app_id": kintone_app_id,
                "has_record_data": bool(record_data),
            },
        )

        # レコードデータをJSONとして解析
        try:
            record_json = self._normalize_record_payload(record_data)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        field_count = len(record_json)
        attachment_fields = sum(
            1
            for value in record_json.values()
            if isinstance(value, dict)
            and isinstance(value.get("value"), list)
            and value["value"]
            and isinstance(value["value"][0], dict)
            and "fileKey" in value["value"][0]
        )

        yield self.create_log_message(
            label="Record payload summary",
            data={
                "field_count": field_count,
                "attachment_field_count": attachment_fields,
            },
        )

        # レコードデータの基本的な構造を検証
        validation_errors = self._validate_record_structure(record_json)
        if validation_errors:
            error_message = "レコードデータの構造が不正です:\n" + "\n".join(validation_errors)
            yield self.create_text_message(error_message)
            return

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 30.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        # APIリクエスト用のヘッダー設定
        headers = build_headers(kintone_api_token)

        # kintone のレコード追加 API のエンドポイント
        url = f"https://{kintone_domain}/k/v1/record.json"

        try:
            # リクエスト用のJSONボディを作成
            request_body = {
                "app": kintone_app_id,
                "record": record_json
            }

            # APIリクエストの実行
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=timeout_seconds
                )
                # HTTPエラーがあれば例外を発生
                response.raise_for_status()
            except Timeout:
                yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
                return
            except HTTPError as e:
                # HTTPステータスコードに基づいたエラーメッセージ
                status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
                if status_code == 401:
                    yield self.create_text_message("kintone APIの認証に失敗しました。APIトークンを確認してください。")
                elif status_code == 403:
                    yield self.create_text_message("kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。")
                elif status_code == 404:
                    yield self.create_text_message("指定されたkintoneアプリが見つかりません。アプリIDを確認してください。")
                elif status_code >= 500:
                    yield self.create_text_message(f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。")
                else:
                    yield self.create_text_message(f"kintone APIリクエスト中にHTTPエラーが発生しました: {str(e)}")
                return
            except RequestException as e:
                yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(e)}")
                return

            # レスポンスのJSONデータを解析
            try:
                data = response.json()
            except json.JSONDecodeError:
                yield self.create_text_message("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")
                return

            yield log_response(self, "kintone add record response", data)

            # レコードIDの取得
            record_id = data.get("id")
            if not record_id:
                yield self.create_text_message("レコードの追加に成功しましたが、レコードIDを取得できませんでした。")
                return

            # 成功メッセージを返す
            yield self.create_variable_message("record_id", record_id)
            yield self.create_variable_message("response", data)
            revision = data.get("revision")
            yield self.create_json_message(
                {
                    "record_id": record_id,
                    "revision": revision,
                    "app_id": kintone_app_id,
                    "field_count": field_count,
                }
            )
            if revision is not None:
                success_message = f"レコードが正常に追加されました。レコードID: {record_id} / リビジョン: {revision}"
            else:
                success_message = f"レコードが正常に追加されました。レコードID: {record_id}"
            yield self.create_text_message(success_message)

        except Exception as e:
            # 予期しないエラーの処理
            error_message = f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(e)}"
            yield self.create_text_message(error_message)
            
    def _validate_record_structure(self, record_data: Dict[str, Any]) -> List[str]:
        """
        レコードデータの基本的な構造を検証する関数
        
        Args:
            record_data: 検証するレコードデータ
            
        Returns:
            エラーメッセージのリスト（空リストの場合は検証成功）
        """
        errors = []
        
        # レコードデータが辞書型であることを確認
        if not isinstance(record_data, dict):
            errors.append("レコードデータは辞書型である必要があります")
            return errors
            
        # 各フィールドの構造を検証
        for field_code, field_data in record_data.items():
            # フィールドコードが文字列であることを確認
            if not isinstance(field_code, str):
                errors.append(f"フィールドコードは文字列である必要があります: {field_code}")
                continue
                
            # フィールドデータが辞書型であることを確認
            if not isinstance(field_data, dict):
                errors.append(f"フィールド '{field_code}' のデータは辞書型である必要があります")
                continue
                
            # valueキーが存在することを確認
            if "value" not in field_data:
                errors.append(f"フィールド '{field_code}' に 'value' キーがありません")
                
        return errors

    def _normalize_record_payload(self, payload: Any) -> Dict[str, Any]:
        """record_dataパラメータを辞書形式に正規化する。"""

        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                raise ValueError("レコードデータが有効なJSON形式ではありません。正しいJSON形式で入力してください。") from None
            if isinstance(parsed, dict):
                return parsed

        raise ValueError("レコードデータはJSONオブジェクト形式で指定してください。")
