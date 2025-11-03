"""
# where: kintone_integration/tools/kintone_build_records_data.py
# what: kintone_upsert_records向けrecords_dataペイロードを生成するDifyツールを提供する。
# why: シンプルなJSON/配列入力から一貫したレコード構造とupdateKeyを自動付与し、アップサート処理を容易にするため。
"""

from __future__ import annotations

import json
from copy import deepcopy
from collections.abc import Generator, Mapping
from typing import Any, Dict, List

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .common import log_parameters, log_response


class KintoneBuildRecordsDataTool(Tool):
    """kintone_upsert_records用のrecords_dataを組み立てるツール。"""

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        raw_source = tool_parameters.get("records_source")
        if raw_source is None:
            raw_source = tool_parameters.get("subtable_source")
        if raw_source is None:
            yield self.create_text_message(
                "records_source パラメータが見つかりません。文字列または配列で入力してください。"
            )
            return

        update_key_field = tool_parameters.get("updateKey")
        if not isinstance(update_key_field, str) or not update_key_field.strip():
            yield self.create_text_message("updateKey パラメータにはフィールドコードを文字列で指定してください。")
            return
        update_key_field = update_key_field.strip()

        yield log_parameters(
            self,
            {
                "source_type": type(raw_source).__name__,
                "update_key_field": update_key_field,
            },
        )

        try:
            records = self._normalize_records(raw_source)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            composed_records = self._build_records(records, update_key_field)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        payload = {"records": composed_records}
        payload_json = json.dumps(payload, ensure_ascii=False)

        yield self.create_variable_message("records_data", payload_json)
        yield self.create_json_message({"records_data": payload})
        yield log_response(
            self,
            "kintone upsert records payload built",
            {
                "records_count": len(composed_records),
                "update_key_field": update_key_field,
            },
        )

    def _normalize_records(self, source: Any) -> List[Mapping[str, Any]]:
        """入力値からrecords配列を抽出する。"""

        if isinstance(source, str):
            text = source.strip()
            if not text:
                raise ValueError("records_data用の入力が空文字列です。JSON文字列または配列を指定してください。")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"records_data用入力のJSON解析に失敗しました: {exc.msg}") from exc
        elif isinstance(source, list):
            parsed = source
        else:
            raise ValueError(
                f"records_data用入力は文字列または配列を受け付けます（現在の型: {type(source).__name__}）。"
            )

        if not isinstance(parsed, list):
            raise ValueError("records_data用入力は配列(JSON Array)として解釈される必要があります。")

        normalized: List[Mapping[str, Any]] = []
        for index, item in enumerate(parsed):
            if not isinstance(item, Mapping):
                raise ValueError(f"{index} 番目の要素がオブジェクトではありません。各レコードは辞書型で指定してください。")
            normalized.append(item)

        if not normalized:
            raise ValueError("records_data用のレコードが1件もありません。1件以上のオブジェクトを含む配列を指定してください。")

        return normalized

    def _build_records(self, records: List[Mapping[str, Any]], update_key_field: str) -> List[Dict[str, Any]]:
        """kintone upsert records API向けrecords配列を構築する。"""

        result: List[Dict[str, Any]] = []

        for index, record_source in enumerate(records):
            if update_key_field not in record_source:
                raise ValueError(
                    f"{index} 番目のレコードに updateKey 用フィールド '{update_key_field}' が存在しません。"
                )

            update_value_raw = record_source[update_key_field]
            update_value = self._stringify_update_value(update_value_raw, index, update_key_field)

            record_fields: Dict[str, Dict[str, Any]] = {}
            for field_code, field_value in record_source.items():
                if not isinstance(field_code, str) or not field_code:
                    raise ValueError(
                        f"{index} 番目のレコードに非文字列のフィールドコードがあります: {field_code!r}"
                    )
                record_fields[field_code] = {
                    "value": self._normalize_field_value(field_value),
                }

            result.append(
                {
                    "updateKey": {
                        "field": update_key_field,
                        "value": update_value,
                    },
                    "record": record_fields,
                }
            )

        return result

    def _normalize_field_value(self, value: Any) -> Any:
        """フィールド値をAPIに送信可能な形式へ整形する。"""

        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, dict)):
            return deepcopy(value)
        return str(value)

    def _stringify_update_value(self, value: Any, index: int, field_code: str) -> str:
        """updateKeyの値を文字列に正規化する。"""

        if value is None:
            raise ValueError(f"{index} 番目のレコードの updateKey '{field_code}' の値が未設定です。")

        text = str(value).strip()
        if not text:
            raise ValueError(f"{index} 番目のレコードの updateKey '{field_code}' の値が空です。")
        return text

