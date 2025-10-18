"""
# where: kintone_integration/tools/kintone_get_fields.py
# what: Dify ツールとして kintone アプリのフィールド定義を取得する。
# why: レコード操作前にフィールド構造を確認できるようにするため。
"""
import json
from collections.abc import Generator
from typing import Any, Dict

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class KintoneGetFieldsTool(Tool):
    """
    kintone アプリのフィールド定義を取得するツール。

    kintone のフォーム設定 API を呼び出し、出力モードに応じたフィールド情報を返す。
    """

    _BASIC_EXCLUDE_TYPES = {"GROUP", "RECORD_NUMBER", "REFERENCE_TABLE"}
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        kintone_domain = tool_parameters.get("kintone_domain")
        if not kintone_domain:
            yield self.create_text_message("kintone ドメインが見つかりません。kintone_domainパラメータを確認してください。")
            return

        kintone_app_id = tool_parameters.get("kintone_app_id")
        if not kintone_app_id:
            yield self.create_text_message("kintone アプリIDが見つかりません。kintone_app_idパラメータを確認してください。")
            return

        try:
            normalized_app_id = self._normalize_app_id(kintone_app_id)
        except ValueError:
            yield self.create_text_message(f"kintone アプリIDが無効です。整数値を指定してください（現在の入力: {kintone_app_id!r}）。")
            return

        kintone_api_token = tool_parameters.get("kintone_api_token")
        if not kintone_api_token:
            yield self.create_text_message("kintone APIトークンが見つかりません。kintone_api_tokenパラメータを確認してください。")
            return

        try:
            include_full = self._normalize_detail_flag(tool_parameters.get("detail_level", False))
        except ValueError:
            yield self.create_text_message("detail_level には真偽値（true/false）を指定してください。")
            return

        headers = {
            "X-Cybozu-API-Token": kintone_api_token,
            "Content-Type": "application/json",
            "X-HTTP-Method-Override": "GET",  # kintone APIが推奨するメソッドオーバーライドを利用
        }

        url = f"https://{kintone_domain}/k/v1/app/form/fields.json"
        request_body = {"app": normalized_app_id}

        try:
            response = requests.post(
                url,
                headers=headers,
                json=request_body,
                timeout=10,
            )
            response.raise_for_status()
        except Timeout:
            yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
            return
        except HTTPError as error:
            status_code = error.response.status_code if hasattr(error, "response") else "unknown"
            error_detail = self._extract_error_detail(error)
            if status_code == 401:
                yield self.create_text_message("kintone APIの認証に失敗しました。APIトークンを確認してください。")
            elif status_code == 403:
                yield self.create_text_message("kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。")
            elif status_code == 404:
                yield self.create_text_message("指定されたkintoneアプリが見つかりません。アプリIDを確認してください。")
            else:
                message = f"kintone APIリクエスト中にHTTPエラーが発生しました（ステータスコード: {status_code}）。"
                if error_detail:
                    message += f" 詳細: {error_detail}"
                yield self.create_text_message(message)
            return
        except RequestException as error:
            yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(error)}")
            return

        try:
            data = response.json()
        except ValueError:
            yield self.create_text_message("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")
            return

        properties = data.get("properties", {})
        if not isinstance(properties, dict) or not properties:
            yield self.create_text_message("フィールド定義が見つかりませんでした。アプリ設定を確認してください。")
            return

        if include_full:
            body = properties
        else:
            body = self._build_basic_view(properties)

        payload = json.dumps(body, ensure_ascii=False, indent=2)
        yield self.create_variable_message("fields", body)
        yield self.create_text_message(payload)

    def _build_basic_view(self, properties: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        フィールドごとに主要プロパティのみを抽出した辞書を返す。
        """

        summary: Dict[str, Dict[str, Any]] = {}
        for field_code, config in sorted(properties.items()):
            field_type = config.get("type", "UNKNOWN")
            if field_type in self._BASIC_EXCLUDE_TYPES:
                continue
            field_info: Dict[str, Any] = {
                "code": config.get("code", field_code),
                "type": field_type,
            }

            if "required" in config:
                field_info["required"] = config["required"]
            if "unique" in config:
                field_info["unique"] = config["unique"]
            if "options" in config:
                field_info["options"] = config["options"]
            if "fields" in config and isinstance(config["fields"], dict):
                field_info["fields"] = self._build_nested_fields(config["fields"])
            summary[field_code] = field_info
        return summary

    def _normalize_app_id(self, app_id: Any) -> int:
        """
        ユーザー入力のアプリIDを整数へ正規化する。空白や小数表現を許容するが、整数に変換できなければ例外を投げる。
        """

        # 文字列・数値のどちらでも動作するように str → strip → int 化する
        cleaned = str(app_id).strip()
        if not cleaned:
            raise ValueError("empty app id")
        return int(cleaned)

    def _extract_error_detail(self, error: HTTPError) -> str:
        """
        kintone API が返す JSON のコードやメッセージを抽出し、デバッグ情報として返す。
        """

        response = getattr(error, "response", None)
        if response is None:
            return ""
        try:
            payload = response.json()
        except ValueError:
            return ""

        detail_parts = []
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

    def _build_nested_fields(self, nested_properties: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        サブテーブル等の入れ子になったフィールド情報を整形する。
        """

        nested_summary: Dict[str, Dict[str, Any]] = {}
        for nested_code, nested_config in sorted(nested_properties.items()):
            nested_type = nested_config.get("type", "UNKNOWN")
            nested_info: Dict[str, Any] = {
                "code": nested_config.get("code", nested_code),
                "type": nested_type,
            }
            if "required" in nested_config:
                nested_info["required"] = nested_config["required"]
            if "unique" in nested_config:
                nested_info["unique"] = nested_config["unique"]
            if "options" in nested_config:
                nested_info["options"] = nested_config["options"]
            nested_summary[nested_code] = nested_info
        return nested_summary

    def _normalize_detail_flag(self, flag: Any) -> bool:
        """
        detail_levelフラグを真偽値へ正規化する。
        """

        if isinstance(flag, bool):
            return flag
        if flag is None:
            return False
        if isinstance(flag, str):
            normalized = flag.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n", ""}:
                return False
        if isinstance(flag, (int, float)):
            return bool(flag)
        raise ValueError("invalid flag")
