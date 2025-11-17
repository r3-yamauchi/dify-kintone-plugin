"""
where: kintone_integration/tools/kintone_query.py
what: Difyのkintoneレコード検索ツール実装
why: kintone APIを通じたレコード取得と結果整形を担う
"""

import re
import json
from collections.abc import Generator
from typing import Any, Dict, List, Optional

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


class KintoneTool(Tool):
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

        raw_app_id = tool_parameters.get("kintone_app_id")
        if raw_app_id in (None, ""):
            yield self.create_text_message("kintone アプリIDが見つかりません。kintone_app_idパラメータを確認してください。")
            return
        try:
            kintone_app_id = normalize_app_id(raw_app_id)
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

        # クエリ文字列の取得
        query_str = tool_parameters.get("query", "")
        (
            clean_query,
            user_limit,
            user_offset,
            has_limit,
            has_offset,
            has_order_by,
        ) = self._normalize_query(query_str)

        if has_limit and user_limit and user_limit > 500:
            yield self.create_text_message(
                "kintone REST APIのlimit上限は500です。全件取得する場合はlimitを省略してください。"
            )
            return

        try:
            output_mode = self._resolve_output_mode(tool_parameters.get("output_mode"))
        except ValueError:
            yield self.create_text_message(
                "output_mode は「テキスト + JSON」,「テキストのみ」,「JSONをページごとに即時返却」,「フラット化したJSON」のいずれかを指定してください。"
            )
            return

        produce_text = output_mode in {"text_only", "both"}
        stream_json = output_mode == "json_stream"
        collect_json = output_mode in {"both", "flattened_json"}
        flatten_json = output_mode == "flattened_json"

        # ユーザー指定のlimitがある場合はそれを使用、なければデフォルト値
        limit = user_limit if user_limit is not None else 500

        # ユーザー指定のoffsetがある場合はそれを使用、なければデフォルト値
        initial_offset = user_offset if user_offset is not None else 0
        offset = initial_offset

        pagination_log = None
        if has_limit or has_offset:
            pagination_log = self.create_log_message(
                label="Detected pagination parameters",
                data={
                    "limit": user_limit,
                    "offset": user_offset,
                    "output_mode": output_mode,
                },
            )
            yield pagination_log

        # ページネーション処理の設定
        # ユーザーがlimitを指定した場合：
        #   - ユーザーが指定した件数だけを取得する（ページネーションを行わない）
        #   - ユーザーの意図を尊重し、指定された件数以上は取得しない
        # ユーザーがlimitを指定していない場合：
        #   - 全件取得するためにページネーションを行う
        #   - デフォルトのlimit値（500）を使用して複数回APIを呼び出す
        should_paginate = not has_limit
        use_record_id_paging = should_paginate and not has_order_by
        pagination_strategy = "record_id" if use_record_id_paging else "offset"

        pagination_mode_log = self.create_log_message(
            label="Pagination mode",
            data={
                "paginate": should_paginate,
                "effective_limit": limit,
                "start_offset": initial_offset,
                "output_mode": output_mode,
                "strategy": pagination_strategy,
            },
        )
        yield pagination_mode_log

        # ページネーション処理用の変数
        all_records = [] if collect_json else None
        all_flattened_records = [] if flatten_json else None
        text_records: list[list[str]] | None = [] if produce_text else None
        total_records = 0
        page_count = 0
        last_record_id: Optional[int] = None
        record_id_cursor: Optional[int] = 0 if use_record_id_paging else None
        offset_query_with_guard: Optional[str] = None if use_record_id_paging else self._ensure_min_record_id_condition(clean_query, 0)

        # フィールドリストの処理
        fields_list = None
        fields_param = tool_parameters.get("fields")
        if fields_param is not None:
            try:
                parsed_fields = self._parse_fields(fields_param)
            except ValueError as error:
                yield self.create_text_message(str(error))
                return
            if parsed_fields:
                fields_list = parsed_fields

        if fields_list is not None:
            fields_list = [*fields_list, "$id"]
            fields_list = self._deduplicate_fields(fields_list)

        try:
            timeout_seconds = resolve_timeout(tool_parameters.get("request_timeout"), 30.0)
        except ValueError:
            yield self.create_text_message("request_timeout には正の数値を指定してください。")
            return

        yield log_parameters(
            self,
            {
                "kintone_domain": kintone_domain,
                "kintone_app_id": kintone_app_id,
                "query_present": bool(query_str),
                "output_mode": output_mode,
                "user_limit": user_limit,
                "user_offset": user_offset,
            },
        )

        # APIリクエスト用のヘッダー設定
        headers = build_headers(kintone_api_token, method_override="GET")

        # kintone のレコード取得 API のエンドポイント
        url = f"https://{kintone_domain}/k/v1/records.json"

        request_count = 0

        try:
            # ページネーションを使用して全レコードを取得
            while True:
                # クエリ文字列にページング条件を追加
                if use_record_id_paging:
                    base_query = clean_query
                    if record_id_cursor is not None:
                        id_condition = f"$id > {record_id_cursor}"
                        if base_query:
                            base_query = f"{base_query} and {id_condition}"
                        else:
                            base_query = id_condition

                    query_parts = []
                    if base_query:
                        query_parts.append(base_query)
                    query_parts.append("order by $id asc")
                    query_parts.append(f"limit {limit}")
                    query = " ".join(query_parts).strip()
                else:
                    query_core = offset_query_with_guard or ""
                    if query_core:
                        query = f"{query_core} limit {limit} offset {offset}"
                    else:
                        query = f"$id > 0 limit {limit} offset {offset}"

                # POSTリクエスト用のJSONボディを作成
                request_body = {
                    "app": kintone_app_id,
                    "query": query,
                }
                
                # 事前に処理したfieldsリストがある場合は追加
                if fields_list:
                    request_body["fields"] = fields_list

                # APIリクエストの実行
                try:
                    # GETの代わりにPOSTメソッドを使用
                    response = requests.post(
                        url,
                        headers=headers,
                        json=request_body,  # paramsの代わりにjsonを使用
                        timeout=timeout_seconds
                    )
                    # HTTPエラーがあれば例外を発生
                    response.raise_for_status()
                    request_count += 1
                except Timeout:
                    yield self.create_text_message("kintone APIへのリクエストがタイムアウトしました。ネットワーク接続を確認してください。")
                    return
                except HTTPError as e:
                    # HTTPステータスコードに基づいたエラーメッセージ
                    status_code = e.response.status_code if hasattr(e, "response") else "unknown"
                    detail = self._extract_http_error_detail(e)

                    def _with_detail(message: str) -> str:
                        return f"{message} 詳細: {detail}" if detail else message

                    if status_code == 401:
                        yield self.create_text_message(
                            _with_detail("kintone APIの認証に失敗しました。APIトークンを確認してください。")
                        )
                    elif status_code == 403:
                        yield self.create_text_message(
                            _with_detail("kintone APIへのアクセス権限がありません。APIトークンの権限を確認してください。")
                        )
                    elif status_code == 404:
                        yield self.create_text_message(
                            _with_detail("指定されたkintoneアプリが見つかりません。アプリIDを確認してください。")
                        )
                    elif status_code >= 500:
                        yield self.create_text_message(
                            _with_detail(f"kintoneサーバーでエラーが発生しました（ステータスコード: {status_code}）。")
                        )
                    else:
                        yield self.create_text_message(
                            _with_detail(f"kintone APIリクエスト中にHTTPエラーが発生しました: {str(e)}")
                        )
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

                # レコードデータの取得と検証
                records = data.get("records", [])

                # レコードが存在しなければループを抜ける
                if not records:
                    break

                # 取得したレコードを結果リストに追加
                total_records += len(records)
                page_count += 1
                if collect_json and all_records is not None:
                    all_records.extend(records)
                if flatten_json and all_flattened_records is not None:
                    for record in records:
                        all_flattened_records.append(self._flatten_record(record))

                if produce_text and text_records is not None:
                    for record in records:
                        record_lines = []
                        for field_name in record.keys():
                            field_value = get_field_value(record, field_name)
                            if field_value and field_value != "不明":
                                record_lines.append(f"{field_name}: {field_value}")
                        if record_lines:
                            text_records.append(record_lines)

                if stream_json:
                    yield self.create_json_message(
                        {
                            "page": page_count,
                            "offset": offset,
                            "limit": limit,
                            "records": records,
                        }
                    )

                if use_record_id_paging:
                    last_id_value = self._extract_record_id(records[-1])
                    if last_id_value is None:
                        yield self.create_text_message(
                            "$id フィールドを取得できなかったためページネーションを継続できません。fields パラメータをご確認ください。"
                        )
                        return
                    last_record_id = last_id_value
                    record_id_cursor = last_id_value

                # ページネーション処理の判断
                # 1. ユーザーがlimitを指定した場合（should_paginate = False）：
                #    - 1回だけAPIを呼び出し、指定された件数だけを取得
                # 2. ユーザーがlimitを指定していない場合（should_paginate = True）：
                #    - 全件取得するまで繰り返しAPIを呼び出す
                if not should_paginate:
                    # ユーザーがlimitを指定した場合は1回だけ取得
                    break

                # 取得したレコード数が指定したlimitより少ない場合、全てのレコードを取得完了
                if len(records) < limit:
                    break

                if use_record_id_paging:
                    continue

                # 次のページのoffsetを設定
                offset += limit

            summary_payload = {
                "total_records": total_records,
                "requests_made": request_count,
                "request_limit": limit,
                "initial_offset": initial_offset,
                "final_offset": None if use_record_id_paging else offset,
                "used_pagination": should_paginate,
                "fields": fields_list,
                "effective_query": clean_query or None,
                "pages": page_count,
                "pagination_strategy": pagination_strategy,
            }
            if has_limit:
                summary_payload["user_defined_limit"] = user_limit
            if has_offset:
                summary_payload["user_defined_offset"] = user_offset
            if use_record_id_paging and last_record_id is not None:
                summary_payload["last_record_id"] = last_record_id

            if output_mode == "both":
                records_output = all_records or []
                json_payload = {
                    "summary": summary_payload,
                    "records": records_output,
                }
                yield self.create_json_message(json_payload)
            elif output_mode == "flattened_json":
                records_output = all_flattened_records or []
                json_payload = {
                    "summary": summary_payload,
                    "records": records_output,
                }
                yield self.create_json_message(json_payload)
                yield self.create_text_message(json.dumps(records_output, ensure_ascii=False))
            elif output_mode == "json_stream":
                yield self.create_json_message({"summary": summary_payload})

            if output_mode in {"both", "text_only"}:
                if total_records == 0:
                    yield self.create_text_message(f"'{query_str}' に一致するレコードは見つかりませんでした。")
                else:
                    text_lines = [f"取得したレコード件数: {total_records}"]
                    if text_records:
                        for idx, record_lines in enumerate(text_records):
                            if idx > 0:
                                text_lines.append("---")
                            text_lines.extend(record_lines)
                    yield self.create_text_message("\n".join(text_lines))

            yield log_response(
                self,
                "kintone query summary",
                {
                    "total_records": total_records,
                    "requests_made": request_count,
                    "output_mode": output_mode,
                    "pagination_strategy": pagination_strategy,
                },
            )

        except Exception as e:
            # 予期しないエラーの処理
            error_message = f"kintone API 呼び出し中に予期しないエラーが発生しました: {str(e)}"
            yield self.create_text_message(error_message)

    def _normalize_query(
        self, raw_query: Optional[str]
    ) -> tuple[str, Optional[int], Optional[int], bool, bool, bool]:
        """
        クエリ文字列からlimit/offsetを取り除き、余分な結合演算子を整形する。
        """
        query = (raw_query or "").strip()
        if not query:
            return "", None, None, False, False, False

        limit_match = re.search(r"\blimit\s+(\d+)", query, flags=re.IGNORECASE)
        has_limit = bool(limit_match)
        user_limit = int(limit_match.group(1)) if has_limit else None

        offset_match = re.search(r"\boffset\s+(\d+)", query, flags=re.IGNORECASE)
        has_offset = bool(offset_match)
        user_offset = int(offset_match.group(1)) if has_offset else None

        clean_query = query
        if has_limit:
            clean_query = re.sub(r"\blimit\s+\d+", "", clean_query, flags=re.IGNORECASE)
        if has_offset:
            clean_query = re.sub(r"\boffset\s+\d+", "", clean_query, flags=re.IGNORECASE)

        clean_query = re.sub(r"\s+", " ", clean_query).strip()
        clean_query = self._remove_trailing_connectors(clean_query)
        has_order_by = bool(re.search(r"\border\s+by\b", clean_query, flags=re.IGNORECASE))

        return clean_query, user_limit, user_offset, has_limit, has_offset, has_order_by

    @staticmethod
    def _resolve_output_mode(raw_mode: Any) -> str:
        """output_modeパラメータを正規化する。"""

        if raw_mode is None:
            return "both"
        if isinstance(raw_mode, str):
            normalized = raw_mode.strip().lower()
            if normalized in {"text_only", "json_stream", "both", "flattened_json"}:
                return normalized
        raise ValueError("invalid output mode")

    def _parse_fields(self, raw_fields: Any) -> list[str]:
        """fieldsパラメータをリストへ正規化する。"""

        tokens: Any
        if isinstance(raw_fields, list):
            tokens = raw_fields
        elif isinstance(raw_fields, str):
            text = raw_fields.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as error:
                    raise ValueError("fields は JSON 配列形式が正しくありません。") from error
                tokens = parsed
            else:
                tokens = [part.strip() for part in re.split(r"[,\n]", text) if part.strip()]
        else:
            raise ValueError("fields パラメータは文字列または配列で指定してください。")

        if not isinstance(tokens, list):
            raise ValueError("fields は配列形式で指定してください。")

        cleaned: list[str] = []
        for item in tokens:
            if not isinstance(item, str):
                raise ValueError("fields の各要素は文字列である必要があります。")
            trimmed = item.strip()
            if trimmed:
                cleaned.append(trimmed)

        return cleaned

    @staticmethod
    def _deduplicate_fields(fields: list[str]) -> list[str]:
        """fieldsリストから重複を除去し、指定順序を維持する。"""

        seen: set[str] = set()
        result: list[str] = []
        for field in fields:
            if field in seen:
                continue
            seen.add(field)
            result.append(field)
        return result

    @staticmethod
    def _remove_trailing_connectors(query: str) -> str:
        """
        末尾に残った and / or / order by などの不要な結合記号を取り除く。
        """
        if not query:
            return ""

        result = query
        trailing_pattern = re.compile(r"(?:\b(?:and|or)\b|\border\s+by\b)\s*$", flags=re.IGNORECASE)
        while True:
            match = trailing_pattern.search(result)
            if not match:
                break
            result = result[: match.start()].rstrip()
        return result

    @staticmethod
    def _extract_http_error_detail(error: HTTPError) -> Optional[str]:
        """
        HTTPエラーに含まれるレスポンス内容を要約して返す。
        """
        response = getattr(error, "response", None)
        if response is None:
            return None
        text = getattr(response, "text", "") or ""
        text = text.strip()
        if not text:
            return None
        text = re.sub(r"\s+", " ", text)
        if len(text) > 200:
            text = f"{text[:197]}..."
        return text

    @staticmethod
    def _extract_record_id(record: Dict[str, Any]) -> Optional[int]:
        """レコードから $id の整数値を取り出す。"""

        field = record.get("$id")
        if field is None:
            return None

        value = field
        if isinstance(field, dict):
            value = field.get("value")

        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ensure_min_record_id_condition(query: str, minimum_id: int) -> str:
        """order by 句の前で $id > minimum_id を必ず付与する。"""

        condition = f"$id > {minimum_id}"
        base = (query or "").strip()
        if not base:
            return condition

        order_match = re.search(r"\border\s+by\b", base, flags=re.IGNORECASE)
        if not order_match:
            return f"{base} and {condition}"

        prefix = base[: order_match.start()].strip()
        suffix = base[order_match.start():].strip()

        if prefix:
            prefix = f"{prefix} and {condition}"
        else:
            prefix = condition

        return f"{prefix} {suffix}".strip()

    def _flatten_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        kintone レコードをフラットな辞書形式に変換する。
        フィールドコードをキーとし、その値を直接持つ。
        """
        row = {}
        for field_code, field_data in record.items():
            row[field_code] = self._flatten_field(field_data)
        return row

    def _flatten_field(self, field_data: Any) -> Any:
        """Flatten SUBTABLE構造を含むフィールドを標準化する。"""
        if self._is_subtable_dict(field_data):
            return self._flatten_subtable(field_data)

        extracted = self._extract_value(field_data)
        if self._looks_like_subtable_rows(extracted):
            return self._flatten_subtable(extracted)
        return extracted

    def _flatten_subtable(self, field_data: Any) -> Any:
        """SUBTABLEの value 配列を [{id, ...}] 形式へ展開する。"""
        if isinstance(field_data, dict):
            rows = field_data.get("value", [])
        else:
            rows = field_data

        if not isinstance(rows, list):
            return field_data

        flattened_rows: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                flattened_rows.append(row)
                continue

            flattened_row: Dict[str, Any] = {}
            for key, value in row.items():
                if key == "value" and isinstance(value, dict):
                    for sub_field_code, sub_field_data in value.items():
                        flattened_row[sub_field_code] = self._extract_value(
                            sub_field_data
                        )
                else:
                    flattened_row[key] = value
            flattened_rows.append(flattened_row)
        return flattened_rows

    @staticmethod
    def _extract_value(field_data: Any) -> Any:
        if isinstance(field_data, dict) and "value" in field_data:
            return field_data["value"]
        return field_data

    @staticmethod
    def _is_subtable_dict(field_data: Any) -> bool:
        return isinstance(field_data, dict) and field_data.get("type") == "SUBTABLE"

    @staticmethod
    def _looks_like_subtable_rows(value: Any) -> bool:
        if not isinstance(value, list):
            return False
        return any(isinstance(row, dict) and "value" in row for row in value)


def get_field_value(record: Dict[str, Any], field_name: str) -> Any:
    """
    kintone レコードから指定されたフィールドの値を取り出して返す関数。

    この関数は、kintoneの複雑なデータ構造を処理し、フィールドの値を取得します。
    入れ子になったデータ構造を再帰的に処理し、不要な情報（id, type）を除外します。
    フィールドが存在しない、または値が空の場合は "不明" を返します。

    Args:
        record (Dict[str, Any]): kintoneのレコードデータ
        field_name (str): 取得するフィールドの名前

    Returns:
        str: フィールドの値、または "不明"
    """
    # フィールドの取得と存在確認
    field = record.get(field_name)
    if field is None:
        return "不明"

    # 入れ子構造を処理する関数
    def clean_value(value: Any) -> Any:
        """
        kintoneの入れ子構造を再帰的に処理し、必要な値のみを抽出する内部関数。
        
        Args:
            value: 処理する値（任意の型）
            
        Returns:
            Any: 処理された値
        """
        # 辞書型の処理
        if isinstance(value, dict):
            # idキーのみの辞書は空文字を返す
            if set(value.keys()) == {"id"}:
                return ""
            
            # valueキーがある場合はその中身を処理
            if "value" in value:
                # typeキーは無視
                inner_value = value["value"]
                return clean_value(inner_value)
            
            # その他の辞書は再帰的に処理
            result = {}
            for k, v in value.items():
                # type と id キーは無視
                if k not in ["type", "id"]:
                    cleaned = clean_value(v)
                    # 空でない値、または0やFalseなど有効な値の場合は追加
                    if cleaned is not None and (cleaned != "" or isinstance(cleaned, (int, float, bool))):
                        result[k] = cleaned
            
            # 空の辞書は空文字を返す
            return result if result else ""
        
        # リスト型の処理
        elif isinstance(value, list):
            # リスト内の各要素を処理
            result = []
            for item in value:
                # idとvalueを持つ辞書の場合、valueの中身のみを処理
                if isinstance(item, dict) and "id" in item and "value" in item:
                    cleaned = clean_value(item["value"])
                else:
                    cleaned = clean_value(item)
                
                # 空でない値、または0やFalseなど有効な値の場合は追加
                if cleaned is not None and (cleaned != "" or isinstance(cleaned, (int, float, bool))):
                    result.append(cleaned)
            
            # 空のリストは空文字を返す
            return result if result else ""
        
        # 基本型はそのまま返す
        return value

    # 処理した値を取得
    cleaned_value = clean_value(field)
    
    # 空の辞書やリストの場合は「不明」を返す
    if cleaned_value == "" and isinstance(cleaned_value, (dict, list)):
        return "不明"
    
    # 0やFalseなどの有効な値を適切に処理
    if cleaned_value == 0 or cleaned_value is False:
        return str(cleaned_value)
    
    # 空の値は「不明」を返す
    if not cleaned_value and not isinstance(cleaned_value, (int, float, bool)):
        return "不明"
    
    # 辞書とリストはJSON文字列に変換
    if isinstance(cleaned_value, (dict, list)):
        try:
            # 日本語などの非ASCII文字をエスケープせずに処理
            return json.dumps(cleaned_value, ensure_ascii=False)
        except (TypeError, ValueError):
            # JSON変換に失敗した場合は文字列表現を返す
            return str(cleaned_value)
    
    # その他の型は文字列に変換
    return str(cleaned_value)
