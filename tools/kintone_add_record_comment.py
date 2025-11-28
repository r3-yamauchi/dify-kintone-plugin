from __future__ import annotations

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
    resolve_timeout,
    resolve_tool_parameter,
)

_ALLOWED_MENTION_TYPES = {"USER", "GROUP", "ORGANIZATION"}


class KintoneAddRecordCommentTool(Tool):
    """kintoneのレコードコメント追加APIを呼び出すツール。"""

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

        try:
            record_id = self._normalize_record_id(tool_parameters.get("record_id"))
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

        try:
            comment_text = self._normalize_comment_text(tool_parameters.get("comment_text"))
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            mentions = self._normalize_mentions(tool_parameters.get("mentions"))
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 10.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "kintone_app_id": kintone_app_id,
                "record_id": record_id,
                "comment_text_length": len(comment_text),
                "mentions_count": len(mentions),
            },
        )

        headers = build_headers(kintone_api_token)
        url = f"{kintone_domain}/k/v1/record/comment.json"
        request_body: dict[str, Any] = {
            "app": kintone_app_id,
            "record": record_id,
            "comment": {
                "text": comment_text,
            },
        }
        if mentions:
            request_body["comment"]["mentions"] = mentions

        try:
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
                yield self.create_text_message(self._build_http_error_message(error))
                return
            except RequestException as error:
                yield self.create_text_message(f"kintone APIへの接続中にエラーが発生しました: {str(error)}")
                return

            try:
                data = response.json()
            except json.JSONDecodeError:
                yield self.create_text_message("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")
                return

            yield log_response(self, "kintone add record comment response", data)

            comment_id = data.get("id")
            if not comment_id:
                yield self.create_text_message("コメントの投稿に成功しましたが、コメントIDを取得できませんでした。")
                return

            yield self.create_variable_message("comment_id", comment_id)
            yield self.create_variable_message("response", data)

            summary: dict[str, Any] = {
                "comment_id": comment_id,
                "record_id": record_id,
                "app_id": kintone_app_id,
                "mentions_count": len(mentions),
                "created_at": data.get("createdAt"),
            }
            creator = data.get("creator")
            if isinstance(creator, dict):
                summary["creator"] = creator

            yield self.create_json_message(summary)

            mention_suffix = f" / メンション {len(mentions)} 件" if mentions else ""
            yield self.create_text_message(
                f"レコードID {record_id} へのコメント投稿が完了しました (コメントID: {comment_id}{mention_suffix})"
            )

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

    def _normalize_comment_text(self, raw_value: Any) -> str:
        if raw_value is None:
            raise ValueError("comment_text を指定してください。")
        text = str(raw_value).strip()
        if not text:
            raise ValueError("comment_text には空でない文字列を指定してください。")
        if len(text) > 10000:
            raise ValueError("comment_text は10000文字以内に収めてください。")
        return text

    def _normalize_mentions(self, raw_value: Any) -> List[Dict[str, str]]:
        if raw_value in (None, ""):
            return []

        if isinstance(raw_value, str):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError as error:
                raise ValueError("mentions には有効なJSON文字列または配列を指定してください。") from error
        elif isinstance(raw_value, list):
            parsed = raw_value
        elif isinstance(raw_value, dict):
            parsed = [raw_value]
        else:
            raise ValueError("mentions にはリスト、オブジェクト、またはJSON文字列を指定してください。")

        normalized: list[dict[str, str]] = []
        for index, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                raise ValueError("mentions の各要素はcode/typeを含むオブジェクトである必要があります。")
            code = str(item.get("code", "")).strip()
            mention_type = str(item.get("type", "")).strip().upper()
            if not code:
                raise ValueError(f"mentions[{index}] のcodeが空です。")
            if mention_type not in _ALLOWED_MENTION_TYPES:
                allowed = ", ".join(sorted(_ALLOWED_MENTION_TYPES))
                raise ValueError(f"mentions[{index}] のtypeは {allowed} から指定してください。")
            normalized.append({"code": code, "type": mention_type})

        if len(normalized) > 10:
            raise ValueError("mentions は最大10件まで指定できます。")

        return normalized

    def _build_http_error_message(self, error: HTTPError) -> str:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if status_code == 401:
            return "kintone APIの認証に失敗しました。APIトークンを確認してください。"
        if status_code == 403:
            return "kintone APIへのアクセス権限がありません。コメント投稿権限を確認してください。"
        if status_code == 404:
            return "対象のkintoneアプリまたはレコードが見つかりません。app_idとrecord_idを確認してください。"
        if status_code and status_code >= 500:
            return f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。"

        message = str(error)
        response = getattr(error, "response", None)
        if response is not None:
            try:
                details = response.json()
                detail_message = details.get("message") or details.get("error")
                if detail_message:
                    message = detail_message
            except (ValueError, AttributeError):
                # 追加情報なし
                pass
        return f"kintone APIリクエスト中にHTTPエラーが発生しました: {message}"
