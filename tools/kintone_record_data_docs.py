"""
# where: kintone_integration/tools/kintone_record_data_docs.py
# what: kintone_add_recordツール用のrecord_data構文リファレンスを返す。
# why: ユーザーが正しいJSON構造でレコード追加リクエストを組み立てられるようにするため。
"""
from collections.abc import Generator
from typing import Any, Dict

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


# record_dataパラメータの仕様を説明するドキュメント文字列
RECORD_DATA_DOCUMENT = r"""
# record_data構文ガイド

## 概要
`kintone_add_record` ツールに渡す `record_data` は **JSON文字列** です。解析後は1つの辞書（オブジェクト）になり、各kintoneフィールドコードをキーとして指定します。値は必ず `{"value": <値>}` という内側の辞書に入れてください。

```json
{
  "文字列フィールド": {"value": "サンプル"},
  "数値フィールド": {"value": 123},
  "日付フィールド": {"value": "2024-01-01"}
}
```

## 基本ルール
- JSONとして正しく構文が閉じていること。
- フィールドコード（キー）は文字列で指定すること。
- 各フィールドの値は必ず辞書型で、`value` キーを含めること。
- 未使用の値は `"value": ""` または `null` を設定可能（フィールドタイプにより挙動が異なります）。
- 添付ファイルのような特殊値は現時点でサポート対象外です。

## フィールドタイプ別の入力例

### 文字列・リンク
```json
"顧客名": {"value": "サイボウズ"}
```
- 文字列は必ずダブルクォートで囲む。

### 数値・計算
```json
"売上": {"value": 1000}
```
- 数値は数値型/文字列どちらでも可ですが、数値型を推奨。

### 日付 (DATE)
```json
"受注日": {"value": "2024-01-01"}
```
- 形式は `YYYY-MM-DD`。

### 時刻 (TIME)
```json
"対応開始時刻": {"value": "09:30"}
```
- 形式は `HH:MM`（24時間表記）。

### 日時 (DATETIME)
```json
"最終更新日時": {"value": "2024-01-01T12:00:00Z"}
```
- 形式は `YYYY-MM-DDThh:mm:ssZ`。末尾の `Z` は省略可（UTC以外の場合はオフセット付きで指定してください）。

### 複数選択 (CHECK_BOX / MULTI_SELECT)
```json
"対応ステータス": {"value": ["未対応", "対応中"]}
```
- 配列（リスト）で値を指定。文字列以外を含めないでください。

### ユーザー/組織/グループ選択
```json
"担当者": {
  "value": [
    {"code": "user01", "type": "USER"},
    {"code": "sales", "type": "ORGANIZATION"}
  ]
}
```
- 各要素は `code` と `type` を持つ辞書。
- `type` は `USER` `ORGANIZATION` `GROUP` のいずれか。

## バリデーション仕様（ツール内部）
- 数値は浮動小数点として評価可能であること。
- 日付/時刻/日時は上記パターン正規表現に合致すること。
- 配列型フィールドは必ずリストで提供すること。
- ユーザー/組織/グループ選択は各項目に `code` と `type` が含まれること。

## よくあるエラー
1. `value` キーの欠落 → `"フィールド 'field_code' に 'value' キーがありません"`
2. JSONパース失敗 → `record_data` をエスケープせずに入力している可能性があります。
3. 不正な日付形式 → `YYYY-MM-DD` など指定フォーマットに合わせてください。
4. 配列が文字列で渡されている → `[]` で括られたJSONリストに修正してください。

## 送信前チェックリスト
- JSONとして構文エラーが無いかを検証しましたか？
- 各フィールドがkintoneアプリ側で有効なフィールドコードと一致していますか？
- 日付/時刻/日時のフォーマット、配列/辞書構造は指定の形式に合致していますか？
"""


class KintoneRecordDataDocTool(Tool):
    """record_data構文ドキュメントを返すユーティリティツール。"""

    def _invoke(self, tool_parameters: Dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        # パラメータは受け取らず、定義済みドキュメントを返すだけ。
        yield self.create_text_message(RECORD_DATA_DOCUMENT)

