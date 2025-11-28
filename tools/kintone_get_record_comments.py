from __future__ import annotations

import json
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
    normalize_app_id,
    normalize_domain,
    resolve_timeout,
    resolve_tool_parameter,
)

_PAGE_SIZE = 10  # kintone APIのコメント取得上限
_MAX_PAGES = 1000  # 無限ループ防止の安全弁


class _ApiCallError(Exception):
    """kintone API 呼び出しでユーザー向けメッセージを伴うエラーを表す。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class KintoneGetRecordCommentsTool(Tool):
    """kintone レコードコメント取得ツール。limit 未指定または 11 以上で全件取得モード。"""

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
            order = self._normalize_order(tool_parameters.get("order", "asc"))
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            offset = self._normalize_offset(tool_parameters.get("offset", 0))
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            limit_value, full_fetch = self._normalize_limit(tool_parameters.get("limit"))
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
                "order": order,
                "offset": offset,
                "limit": limit_value,
                "full_fetch": full_fetch,
            },
        )

        headers = build_headers(kintone_api_token, method_override="GET")
        url = f"{kintone_domain}/k/v1/record/comments.json"

        try:
            if full_fetch:
                api_order = "asc"
                output_order = order if order == "asc" else "desc"
                result = self._fetch_all_comments(
                    url=url,
                    headers=headers,
                    app_id=kintone_app_id,
                    record_id=record_id,
                    api_order=api_order,
                    output_order=output_order,
                    offset=offset,
                    timeout_seconds=timeout_seconds,
                )
            else:
                api_order = order
                output_order = order
                result = self._fetch_limited_comments(
                    url=url,
                    headers=headers,
                    app_id=kintone_app_id,
                    record_id=record_id,
                    api_order=api_order,
                    output_order=output_order,
                    offset=offset,
                    target_limit=limit_value,
                    timeout_seconds=timeout_seconds,
                )
        except _ApiCallError as error:
            yield self.create_text_message(error.message)
            return

        comments, meta = result
        meta["total_count"] = len(comments)
        comments = self._sort_comments(comments, output_order)
        meta["first_id"] = comments[0].get("id") if comments else None
        meta["last_id"] = comments[-1].get("id") if comments else None
        yield self.create_variable_message("comments", comments)
        yield self.create_variable_message("meta", meta)
        yield self.create_json_message({"comments": comments, "meta": meta})

        text_summary = self._build_text_summary(comments, meta)
        yield self.create_text_message(text_summary)

        yield log_response(
            self,
            "kintone get record comments response",
            {"comment_count": len(comments), **meta},
        )

    def _fetch_single_page(
        self,
        *,
        url: str,
        headers: Dict[str, str],
        app_id: int,
        record_id: int,
        order: str,
        offset: int,
        limit: int,
        timeout_seconds: float,
    ) -> Tuple[List[dict], Dict[str, Any]] | None:
        body = {
            "app": app_id,
            "record": record_id,
            "order": order,
            "offset": offset,
            "limit": limit,
        }
        response = self._call_api(url, headers, body, timeout_seconds)

        comments = self._extract_comments(response)
        meta = {
            "mode": "single",
            "requested_limit": limit,
            "used_pages": 1,
            "offset_start": offset,
            "order": order,
            "older": response.get("older"),
            "newer": response.get("newer"),
        }
        return comments, meta

    def _fetch_all_comments(
        self,
        *,
        url: str,
        headers: Dict[str, str],
        app_id: int,
        record_id: int,
        api_order: str,
        output_order: str,
        offset: int,
        timeout_seconds: float,
    ) -> Tuple[List[dict], Dict[str, Any]] | None:
        comments: list[dict] = []
        page = 0
        current_offset = offset
        last_flags: dict[str, Any] = {}

        while True:
            if page >= _MAX_PAGES:
                warning = f"コメント取得を {_MAX_PAGES} ページで打ち切りました。結果が欠けている可能性があります。"
                comments.append({"warning": warning})
                break

            body = {
                "app": app_id,
                "record": record_id,
                "order": api_order,
                "offset": current_offset,
                "limit": _PAGE_SIZE,
            }

            response = self._call_api(url, headers, body, timeout_seconds)

            batch = self._extract_comments(response)
            last_flags = {"older": response.get("older"), "newer": response.get("newer")}
            comments.extend(batch)

            page += 1
            has_more_flag = response.get("newer") if api_order == "asc" else response.get("older")
            has_more = bool(has_more_flag)
            if not batch:
                break
            if not has_more:
                break

            current_offset += _PAGE_SIZE

        meta = {
            "mode": "all",
            "page_size": _PAGE_SIZE,
            "used_pages": page,
            "offset_start": offset,
            "order": output_order,
            **last_flags,
        }
        return comments, meta

    def _fetch_limited_comments(
        self,
        *,
        url: str,
        headers: Dict[str, str],
        app_id: int,
        record_id: int,
        api_order: str,
        output_order: str,
        offset: int,
        target_limit: int,
        timeout_seconds: float,
    ) -> Tuple[List[dict], Dict[str, Any]]:
        comments: list[dict] = []
        page = 0
        current_offset = offset
        last_flags: dict[str, Any] = {}

        while True:
            if page >= _MAX_PAGES:
                warning = f"コメント取得を {_MAX_PAGES} ページで打ち切りました。結果が欠けている可能性があります。"
                comments.append({"warning": warning})
                break

            remaining = target_limit - len(comments)
            if remaining <= 0:
                break
            page_limit = min(_PAGE_SIZE, remaining if remaining > 0 else _PAGE_SIZE)

            body = {
                "app": app_id,
                "record": record_id,
                "order": api_order,
                "offset": current_offset,
                "limit": page_limit,
            }

            response = self._call_api(url, headers, body, timeout_seconds)
            batch = self._extract_comments(response)
            last_flags = {"older": response.get("older"), "newer": response.get("newer")}
            comments.extend(batch)

            page += 1

            has_more_flag = response.get("newer") if api_order == "asc" else response.get("older")
            has_more = bool(has_more_flag)

            if len(comments) >= target_limit:
                break
            if not batch:
                break
            if not has_more:
                break

            current_offset += _PAGE_SIZE

        sorted_comments = self._sort_comments(comments, output_order)
        truncated = sorted_comments[:target_limit]

        meta = {
            "mode": "limited",
            "page_size": _PAGE_SIZE,
            "used_pages": page,
            "offset_start": offset,
            "order": output_order,
            "requested_limit": target_limit,
            "older": last_flags.get("older"),
            "newer": last_flags.get("newer"),
        }
        return truncated, meta

    def _call_api(
        self,
        url: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
        except Timeout:
            raise _ApiCallError("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
        except HTTPError as error:
            raise _ApiCallError(self._build_http_error_message(error))
        except RequestException as error:
            raise _ApiCallError(f"kintone APIへの接続中にエラーが発生しました: {str(error)}")

        try:
            return response.json()
        except json.JSONDecodeError:
            raise _ApiCallError("kintone APIからの応答を解析できませんでした。無効なJSONレスポンスです。")

    def _extract_comments(self, data: Dict[str, Any]) -> List[dict]:
        comments = data.get("comments", [])
        if not isinstance(comments, list):
            return []
        return comments

    def _build_text_summary(self, comments: List[dict], meta: Dict[str, Any]) -> str:
        count = meta.get("total_count", len(comments))
        first_id = meta.get("first_id")
        last_id = meta.get("last_id")
        lines = [f"取得件数: {count} 件"]
        if first_id is not None or last_id is not None:
            lines.append(f"先頭ID: {first_id} / 末尾ID: {last_id}")
        return "\n".join(lines)

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

    def _normalize_order(self, raw_value: Any) -> str:
        text = str(raw_value).strip().lower() if raw_value is not None else "asc"
        if text == "":
            text = "asc"
        if text not in {"asc", "desc"}:
            raise ValueError("order には asc または desc を指定してください。")
        return text

    def _normalize_offset(self, raw_value: Any) -> int:
        text = str(raw_value).strip() if raw_value is not None else "0"
        if text == "":
            text = "0"
        try:
            value = int(text)
        except ValueError as error:
            raise ValueError("offset には 0 以上の整数を指定してください。") from error
        if value < 0:
            raise ValueError("offset には 0 以上の整数を指定してください。")
        return value

    def _normalize_limit(self, raw_value: Any) -> Tuple[int | None, bool]:
        """limit値と全件取得モードの判定を返す。"""
        if raw_value is None or str(raw_value).strip() == "":
            return None, True

        text = str(raw_value).strip()
        try:
            value = int(text)
        except ValueError as error:
            raise ValueError("limit には正の整数を指定してください。") from error

        if value <= 0:
            raise ValueError("limit には正の整数を指定してください。")

        return value, False

    def _build_http_error_message(self, error: HTTPError) -> str:
        status_code = error.response.status_code if getattr(error, "response", None) else "unknown"
        base = f"kintone APIリクエスト中にHTTPエラーが発生しました（ステータスコード: {status_code}）。"
        try:
            detail = error.response.json()
            message = detail.get("message") if isinstance(detail, dict) else None
        except Exception:  # noqa: BLE001
            message = None

        if status_code == 401:
            base = "kintone APIの認証に失敗しました。APIトークンを確認してください。"
        elif status_code == 403:
            base = "kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。"
        elif status_code == 404:
            base = "指定されたレコードまたはアプリが見つかりませんでした。app_id と record_id を確認してください。"

        if message:
            return f"{base} 詳細: {message}"
        return base

    def _sort_comments(self, comments: List[dict], order: str) -> List[dict]:
        """コメントIDで再ソートする（order=desc で全件取得後の重複/欠落を軽減）。"""

        if not comments or order not in {"asc", "desc"}:
            return comments

        def _key(item: dict):
            raw_id = item.get("id")
            try:
                return int(raw_id)
            except Exception:
                return str(raw_id)

        reverse = order == "desc"
        try:
            return sorted(comments, key=_key, reverse=reverse)
        except Exception:
            # ソート不能な場合は元の順序を返す
            return comments
