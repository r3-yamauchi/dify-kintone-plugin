"""
# where: kintone_integration/tools/kintone_validate_record_data.py
# what: kintone_add_record用record_dataを事前検証するツールを提供する。
# why: レコード追加前にJSON構造とフィールド型整合性を確認し、エラーを早期に検出するため。
"""
import json
import re
from collections.abc import Generator
from typing import Any, Dict, List, Tuple

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class KintoneValidateRecordDataTool(Tool):
    """record_data文字列の構文とフィールド型整合性を検証するツール。"""

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        kintone_domain = tool_parameters.get("kintone_domain")
        if not kintone_domain:
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        kintone_app_id = tool_parameters.get("kintone_app_id")
        if kintone_app_id is None:
            yield self.create_text_message("kintone アプリIDが見つかりません。kintone_app_idパラメータを確認してください。")
            return

        kintone_api_token = tool_parameters.get("kintone_api_token")
        if not kintone_api_token:
            yield self.create_text_message("kintone APIトークンが見つかりません。kintone_api_tokenパラメータを確認してください。")
            return

        record_data = tool_parameters.get("record_data")
        if record_data is None:
            yield self.create_text_message("record_data が見つかりません。record_dataパラメータを確認してください。")
            return

        # JSONパース
        try:
            record_json = json.loads(record_data)
        except json.JSONDecodeError as error:
            yield self.create_text_message(
                f"record_data を JSON として解析できませんでした: {error.msg} (pos={error.pos})"
            )
            return

        # 基本構造の検証
        structure_errors = self._validate_record_structure(record_json)
        if structure_errors:
            message = "record_data の構造が不正です:\n" + "\n".join(structure_errors)
            yield self.create_text_message(message)
            return

        # フィールド情報の取得と詳細検証
        try:
            normalized_app_id = self._normalize_app_id(kintone_app_id)
        except ValueError:
            yield self.create_text_message(
                f"kintone アプリIDが無効です。整数値を指定してください（現在の入力: {kintone_app_id!r}）。"
            )
            return

        try:
            field_types = self._get_app_fields(kintone_domain, normalized_app_id, kintone_api_token)
        except Timeout:
            yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
            return
        except HTTPError as error:
            detail = self._extract_error_detail(error)
            status_code = error.response.status_code if hasattr(error, "response") else "unknown"
            yield self.create_text_message(
                f"kintone APIリクエスト中にHTTPエラーが発生しました（ステータスコード: {status_code}）。詳細: {detail or 'なし'}"
            )
            return
        except RequestException as error:
            yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(error)}")
            return
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        is_valid, validation_errors = self._validate_field_values(record_json, field_types)
        if not is_valid:
            message = "record_data の検証に失敗しました:\n" + "\n".join(validation_errors)
            yield self.create_text_message(message)
            return

        sanitized = json.dumps(record_json, ensure_ascii=False, indent=2)
        yield self.create_variable_message("validated_record_data", sanitized)
        yield self.create_variable_message("validated_record_object", record_json)
        yield self.create_text_message(sanitized)

    def _validate_record_structure(self, record_data: Dict[str, Any]) -> List[str]:
        """record_dataの基本的な構造を検証し、問題があればエラー文を返す。"""

        errors: List[str] = []
        if not isinstance(record_data, dict):
            errors.append("record_data は辞書型である必要があります")
            return errors

        for field_code, field_data in record_data.items():
            if not isinstance(field_code, str):
                errors.append(f"フィールドコードは文字列である必要があります: {field_code!r}")
                continue

            if not isinstance(field_data, dict):
                errors.append(f"フィールド '{field_code}' の値は辞書型である必要があります")
                continue

            if "value" not in field_data:
                errors.append(f"フィールド '{field_code}' に 'value' キーがありません")

        return errors

    def _normalize_app_id(self, app_id: Any) -> int:
        """app_idを整数へ正規化する。"""

        cleaned = str(app_id).strip()
        if not cleaned:
            raise ValueError("kintone アプリIDが空です。")
        return int(cleaned)

    def _get_app_fields(self, domain: str, app_id: int, api_token: str) -> Dict[str, str]:
        """kintoneフォーム設定からフィールドタイプ情報を取得する。"""

        headers = {
            "X-Cybozu-API-Token": api_token,
            "Content-Type": "application/json",
            "X-HTTP-Method-Override": "GET",
        }
        url = f"https://{domain}/k/v1/app/form/fields.json"
        request_body = {"app": app_id}

        response = requests.post(
            url,
            headers=headers,
            json=request_body,
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        properties = data.get("properties", {})
        if not isinstance(properties, dict) or not properties:
            raise ValueError("kintone アプリにフィールド定義が存在しません。アプリ設定を確認してください。")

        return {field_code: info.get("type", "UNKNOWN") for field_code, info in properties.items()}

    def _validate_field_values(
        self, record_data: Dict[str, Any], field_types: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """フィールドタイプごとの詳細バリデーションを行う。"""

        errors: List[str] = []

        for field_code, field_data in record_data.items():
            if field_code not in field_types:
                continue

            field_type = field_types[field_code]
            value = record_data[field_code].get("value")

            if field_type == "NUMBER":
                if value is not None and value != "":
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"フィールド '{field_code}' の値は数値である必要があります: {value}")

            elif field_type == "DATE":
                if value and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
                    errors.append(
                        f"フィールド '{field_code}' の値は YYYY-MM-DD 形式である必要があります: {value}"
                    )

            elif field_type == "TIME":
                if value and not re.match(r"^\d{2}:\d{2}$", str(value)):
                    errors.append(
                        f"フィールド '{field_code}' の値は HH:MM 形式である必要があります: {value}"
                    )

            elif field_type == "DATETIME":
                if value and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?$", str(value)):
                    errors.append(
                        f"フィールド '{field_code}' の値は YYYY-MM-DDThh:mm:ssZ 形式である必要があります: {value}"
                    )

            elif field_type in {"CHECK_BOX", "MULTI_SELECT"}:
                if value is not None and not isinstance(value, list):
                    errors.append(f"フィールド '{field_code}' の値はリスト形式である必要があります: {value}")

            elif field_type in {"USER_SELECT", "ORGANIZATION_SELECT", "GROUP_SELECT"}:
                if value is not None:
                    if not isinstance(value, list):
                        errors.append(f"フィールド '{field_code}' の値はリスト形式である必要があります: {value}")
                    else:
                        for item in value:
                            if not isinstance(item, dict) or "code" not in item or "type" not in item:
                                errors.append(
                                    f"フィールド '{field_code}' の各項目には 'code' と 'type' キーが必要です: {item}"
                                )

        return len(errors) == 0, errors

    def _extract_error_detail(self, error: HTTPError) -> str:
        """kintone APIが返す詳細エラー情報を抽出する。"""

        response = getattr(error, "response", None)
        if response is None:
            return ""

        try:
            payload = response.json()
        except ValueError:
            return ""

        detail_parts: List[str] = []
        code = payload.get("code")
        message = payload.get("message")
        errors = payload.get("errors")

        if code:
            detail_parts.append(f"code={code}")
        if message:
            detail_parts.append(f"message={message}")
        if errors and isinstance(errors, dict):
            detail_parts.append(f"errors={errors}")

        return ", ".join(detail_parts)
