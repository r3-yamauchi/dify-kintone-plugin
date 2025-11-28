from __future__ import annotations

import ast
import json
from collections.abc import Generator
from typing import Any, Dict, List

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
    normalize_app_id,
    normalize_domain,
    parse_single_record_data,
    resolve_timeout,
    resolve_tool_parameter,
    validate_record_structure,
)


class KintoneUpdateRecordTool(Tool):
    """kintoneの単一レコード更新APIを呼び出すツール。アップサートは行わない。"""

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
            kintone_app_id = normalize_app_id(tool_parameters.get("kintone_app_id"))
        except ValueError:
            yield self.create_text_message("kintone アプリIDには正の整数を指定してください。")
            return

        record_id = None
        update_key = None
        record_id_raw = tool_parameters.get("record_id")
        update_key_raw = tool_parameters.get("updateKey")
        update_key_value_raw = tool_parameters.get("updateKeyValue")

        if is_blank(record_id_raw) and is_blank(update_key_raw):
            yield self.create_text_message("record_id または updateKey のいずれかを指定してください。")
            return

        if not is_blank(record_id_raw):
            try:
                record_id = self._normalize_record_id(record_id_raw)
            except ValueError as error:
                yield self.create_text_message(str(error))
                return

        if not is_blank(update_key_raw):
            try:
                update_key = self._normalize_update_key(update_key_raw, update_key_value_raw)
            except ValueError as error:
                yield self.create_text_message(str(error))
                return

        try:
            kintone_api_token = normalize_api_tokens(
                resolve_tool_parameter(self, tool_parameters, "kintone_api_token")
            )
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        record_data = tool_parameters.get("record_data")
        if record_data in (None, ""):
            yield self.create_text_message("レコードデータが見つかりません。record_dataパラメータを確認してください。")
            return

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "kintone_app_id": kintone_app_id,
                "record_id": record_id,
                "has_update_key": update_key is not None,
                "has_record_data": bool(record_data),
            },
        )

        try:
            record_json = parse_single_record_data(record_data)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        validation_errors = validate_record_structure(record_json)
        if validation_errors:
            yield self.create_text_message("レコードデータの構造が不正です:\n" + "\n".join(validation_errors))
            return

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 30.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        headers = build_headers(kintone_api_token, method_override="PUT")
        url = f"{kintone_domain}/k/v1/record.json"

        try:
            request_body = {
                "app": kintone_app_id,
            }
            if record_id is not None:
                request_body["id"] = record_id
            if update_key is not None:
                request_body["updateKey"] = update_key
            request_body["record"] = record_json

            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=request_body,
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
                    yield self.create_text_message("対象のkintoneアプリまたはレコードが見つかりません。app_idとrecord_idを確認してください。")
                elif isinstance(status_code, int) and status_code >= 500:
                    yield self.create_text_message(f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。")
                else:
                    yield self.create_text_message(f"kintone APIリクエスト中にHTTPエラーが発生しました: {str(error)}")
                return
            except RequestException as error:
                yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(error)}")
                return

            try:
                data = response.json()
            except json.JSONDecodeError:
                yield self.create_text_message("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")
                return

            yield log_response(
                self,
                "kintone update response",
                data,
            )

            revision = data.get("revision")
            yield self.create_variable_message("response", data)
            result_json = {
                "app_id": kintone_app_id,
                "record_id": record_id,
                "revision": revision,
            }
            if update_key is not None:
                result_json["updateKey"] = update_key
            yield self.create_json_message(result_json)
            suffix = f" / リビジョン: {revision}" if revision is not None else ""
            target_label = f"レコードID {record_id}" if record_id is not None else f"updateKey {update_key}"
            yield self.create_text_message(f"{target_label} の更新が完了しました{suffix}。")

        except Exception as error:  # noqa: BLE001
            yield self.create_text_message(f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(error)}")

    def _normalize_record_id(self, raw_value: Any) -> int:
        text = str(raw_value).strip() if raw_value is not None else ""
        if not text:
            raise ValueError("record_id には正の整数を指定してください。")
        try:
            record_id = int(text)
        except ValueError as error:
            raise ValueError("record_id には正の整数を指定してください。") from error
        if record_id <= 0:
            raise ValueError("record_id には正の整数を指定してください。")
        return record_id

    def _normalize_update_key(self, raw_value: Any, fallback_value: Any | None = None) -> Dict[str, Any]:
        """updateKeyとして field/value を持つオブジェクトを正規化する。

        - 既存仕様: {"field": "...", "value": "..."} のオブジェクト/文字列を許容
        - 拡張仕様: フィールドコードだけの文字列を受け取り、value は updateKeyValue から補完
        """

        parsed_data: Any = None

        if isinstance(raw_value, dict):
            parsed_data = raw_value
        elif isinstance(raw_value, str):
            text = raw_value.strip()
            if not text:
                raise ValueError("updateKey は空にできません。")
            try:
                parsed_data = json.loads(text)
            except json.JSONDecodeError:
                try:
                    parsed_data = ast.literal_eval(text)
                except (ValueError, SyntaxError):
                    parsed_data = None

            # フィールドコードのみの文字列を許容する（JSONに解釈できなかった場合や、単一文字列として解釈された場合）
            if parsed_data is None or isinstance(parsed_data, str):
                field_code = parsed_data if isinstance(parsed_data, str) else text
                if not isinstance(field_code, str) or not field_code.strip():
                    raise ValueError("updateKey.field を文字列で指定してください。")
                if is_blank(fallback_value):
                    raise ValueError("updateKey がフィールドコードのみの場合は updateKeyValue を指定してください。")
                return {"field": field_code.strip(), "value": fallback_value}
        else:
            raise ValueError("updateKey はJSONオブジェクトまたは文字列で指定してください。")

        if not isinstance(parsed_data, dict):
            raise ValueError("updateKey はJSONオブジェクトで指定してください。")

        field = parsed_data.get("field")
        value = parsed_data.get("value")
        if not isinstance(field, str) or not field.strip():
            raise ValueError("updateKey.field を文字列で指定してください。")
        if value in (None, ""):
            raise ValueError("updateKey.value を指定してください。")

        return {"field": field.strip(), "value": value}
