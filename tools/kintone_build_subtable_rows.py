"""
# where: kintone_integration/tools/kintone_build_subtable_rows.py
# what: kintoneテーブル(SUBTABLE)行のJSON配列を生成するDifyツールを提供する。
# why: kintone向けフローで文字列または配列入力から一貫した行構造を構築するため。
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any, Dict, List, Mapping

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .common import log_parameters, log_response


class KintoneBuildSubtableRowsTool(Tool):
    """kintoneテーブル(SUBTABLE)行を構築するツール。"""

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        raw_source = tool_parameters.get("subtable_source")
        if raw_source is None:
            yield self.create_text_message(
                "subtable_source パラメータが見つかりません。文字列または配列で入力してください。"
            )
            return

        yield log_parameters(
            self,
            {
                "source_type": type(raw_source).__name__,
            },
        )

        try:
            records = self._normalize_records(raw_source)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        try:
            subtable_rows = self._build_subtable_rows(records)
        except ValueError as error:
            yield self.create_text_message(str(error))
            return

        yield self.create_json_message({"value": subtable_rows})
        yield log_response(
            self,
            "kintone subtable rows built",
            {
                "row_count": len(subtable_rows),
            },
        )

    def _normalize_records(self, source: Any) -> List[Mapping[str, Any]]:
        """入力値からテーブル(SUBTABLE)行に変換可能なレコード配列を抽出する。"""

        if isinstance(source, str):
            text = source.strip()
            if not text:
                raise ValueError("テーブル(SUBTABLE)用データが空文字列です。JSON文字列または配列を指定してください。")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"テーブル(SUBTABLE)用データのJSON解析に失敗しました: {exc.msg}") from exc
        elif isinstance(source, list):
            parsed = source
        else:
            raise ValueError(
                f"テーブル(SUBTABLE)用データは文字列または配列を受け付けます（現在の型: {type(source).__name__}）。"
            )

        if not isinstance(parsed, list):
            raise ValueError("テーブル(SUBTABLE)用データは配列(JSON Array)として解釈される必要があります。")

        normalized: List[Mapping[str, Any]] = []
        for index, item in enumerate(parsed):
            if not isinstance(item, Mapping):
                raise ValueError(f"{index} 番目の要素がオブジェクトではありません。各行は辞書型で指定してください。")
            normalized.append(item)

        if not normalized:
            raise ValueError("テーブル(SUBTABLE)行が1件もありません。1件以上のオブジェクトを含む配列を指定してください。")

        return normalized

    def _build_subtable_rows(self, records: List[Mapping[str, Any]]) -> List[Dict[str, Dict[str, str]]]:
        """kintoneテーブル(SUBTABLE)row配列を構築する。"""

        result: List[Dict[str, Dict[str, str]]] = []
        for index, row_data in enumerate(records):
            row_fields: Dict[str, Dict[str, str]] = {}
            for field_code, field_value in row_data.items():
                if not isinstance(field_code, str):
                    raise ValueError(
                        f"{index} 番目の行に非文字列のフィールドコードがあります: {field_code!r}"
                    )
                row_fields[field_code] = {
                    "value": "" if field_value is None else str(field_value),
                }
            result.append({"value": row_fields})

        return result
