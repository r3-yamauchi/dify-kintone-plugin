
"""Dify tool for flattening kintone JSON records (with optional subtable support)."""

import json
from collections.abc import Generator
from typing import Any, Dict, List, Optional

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class KintoneFlattenJsonTool(Tool):
    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        """
        kintoneのレコード配列（JSON形式）をフラットなJSONオブジェクトの配列に変換します。
        """
        records_input = tool_parameters.get("records_json")
        try:
            subtable_field_code = self._normalize_subtable_field_code(
                tool_parameters.get("subtable_field_code")
            )
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            fields_filter = self._normalize_fields_param(tool_parameters.get("fields"))
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        if records_input is None:
            payload = []
        elif isinstance(records_input, str):
            try:
                payload = json.loads(records_input)
            except json.JSONDecodeError:
                yield self.create_text_message(
                    "records_json には有効なJSONオブジェクト/配列を指定してください。"
                )
                return
        else:
            payload = records_input

        records = self._extract_records_array(payload)
        if records is None:
            yield self.create_text_message(
                "records_json からレコード配列を抽出できませんでした。`records` キーを含むJSON、またはレコード配列を指定してください。"
            )
            return

        if subtable_field_code:
            result_payload = self._collect_subtable_rows(
                records,
                subtable_field_code,
                fields_filter=fields_filter,
            )
        else:
            # 各レコードをフラット化し、必要に応じてフィールドを絞り込む
            result_payload = []
            for record in records:
                if not isinstance(record, dict):
                    result_payload.append(record)
                    continue
                flattened = self._flatten_record(record)
                filtered = self._apply_fields_filter(flattened, fields_filter)
                result_payload.append(filtered)

        # 結果をJSONメッセージ + テキストメッセージとして出力
        try:
            json_payload = {"records": result_payload}
            text_payload = json.dumps(result_payload, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            yield self.create_text_message(f"結果のJSONシリアライズ中にエラーが発生しました: {e}")
            return

        yield self.create_json_message(json_payload)
        yield self.create_text_message(text_payload)

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
        """Flatten SUBTABLE structures; otherwise extract plain value."""
        if self._is_subtable_dict(field_data):
            return self._flatten_subtable(field_data)

        extracted = self._extract_value(field_data)
        if self._looks_like_subtable_rows(extracted):
            return self._flatten_subtable(extracted)
        return extracted

    def _flatten_subtable(self, field_data: Any) -> Any:
        """Flatten SUBTABLE rows if possible, otherwise return as-is."""
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

    def _extract_value(self, field_data: Any) -> Any:
        """Extract the `value` key when present."""
        if isinstance(field_data, dict) and "value" in field_data:
            return field_data["value"]
        return field_data

    def _collect_subtable_rows(
        self,
        records: List[Dict[str, Any]],
        subtable_field_code: str,
        fields_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Collect specified SUBTABLE rows across all records."""
        collected_rows: List[Dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue

            field_data = record.get(subtable_field_code)
            if field_data is None:
                continue

            rows = self._flatten_subtable(field_data)
            if isinstance(rows, list):
                parent_field_values: Dict[str, Any] = {}
                if fields_filter:
                    flattened_parent = self._flatten_record(record)
                    parent_field_values = {
                        field_code: flattened_parent[field_code]
                        for field_code in fields_filter
                        if field_code in flattened_parent
                    }

                for row in rows:
                    if not fields_filter:
                        collected_rows.append(row)
                        continue

                    if isinstance(row, dict):
                        filtered_row: Dict[str, Any] = dict(row)
                    else:
                        filtered_row = {"value": row}

                    for field_code in fields_filter:
                        if field_code in parent_field_values:
                            filtered_row[field_code] = parent_field_values[field_code]
                    collected_rows.append(filtered_row)
        return collected_rows

    def _apply_fields_filter(
        self, record: Dict[str, Any], fields_filter: Optional[List[str]]
    ) -> Dict[str, Any]:
        if not fields_filter or not isinstance(record, dict):
            return record
        filtered: Dict[str, Any] = {}
        for field_code in fields_filter:
            if field_code in record:
                filtered[field_code] = record[field_code]
        return filtered

    @staticmethod
    def _is_subtable_dict(field_data: Any) -> bool:
        return isinstance(field_data, dict) and field_data.get("type") == "SUBTABLE"

    @staticmethod
    def _looks_like_subtable_rows(value: Any) -> bool:
        if not isinstance(value, list):
            return False
        return any(isinstance(row, dict) and "value" in row for row in value)

    def _extract_records_array(self, payload: Any) -> Optional[List[Dict[str, Any]]]:
        """Walk through nested structures to find the actual records array."""
        if payload is None:
            return []

        if isinstance(payload, list):
            for element in payload:
                candidate = self._extract_records_array(element)
                if candidate is not None:
                    return candidate
            return payload if self._looks_like_records_list(payload) else None

        if isinstance(payload, dict):
            records_value = payload.get("records")
            if isinstance(records_value, list):
                return records_value

            for key in ("json", "data", "result", "results", "response", "payload"):
                if key in payload:
                    candidate = self._extract_records_array(payload.get(key))
                    if candidate is not None:
                        return candidate
            return None

        return None

    @staticmethod
    def _looks_like_records_list(payload: List[Any]) -> bool:
        if not payload:
            return True

        score = 0
        for element in payload:
            if not isinstance(element, dict):
                return False
            for value in element.values():
                if isinstance(value, dict) and (
                    "value" in value or "type" in value
                ):
                    score += 1
                    break
        return score > 0

    @staticmethod
    def _normalize_subtable_field_code(field_code: Any) -> Optional[str]:
        if field_code is None:
            return None
        if not isinstance(field_code, str):
            raise ValueError("subtable_field_code には文字列を指定してください。")
        normalized = field_code.strip()
        if not normalized:
            return None
        if "," in normalized:
            raise ValueError("subtable_field_code には単一のフィールドコードのみ指定できます。")
        return normalized

    @staticmethod
    def _normalize_fields_param(fields_param: Any) -> Optional[List[str]]:
        if fields_param is None:
            return None
        if not isinstance(fields_param, str):
            raise ValueError("fields にはカンマ区切りの文字列を指定してください。")
        parts = [part.strip() for part in fields_param.split(",")]
        fields: List[str] = []
        seen = set()
        for part in parts:
            if not part:
                continue
            if part in seen:
                continue
            seen.add(part)
            fields.append(part)
        return fields or None
