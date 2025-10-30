# dify-kintone-plugin

**Author:** r3-yamauchi
**Version:** 0.0.8
**Type:** tool

## Description

これは [kintone](https://kintone.cybozu.co.jp/) アプリのレコードを取得するために使用できる [Dify](https://dify.ai/jp) プラグインです。

このプラグインのソースコードは [GitHub リポジトリ](https://github.com/r3-yamauchi/dify-kintone-plugin) で公開しています。

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/dify-kintone-plugin)

## Features

- kintoneのドメインとアプリIDを指定してレコードを取得
- kintoneのドメインとアプリIDを指定してフィールド定義を取得
- kintoneのクエリ構文仕様文字列を取得
- kintone_add_record向け`record_data`構文リファレンスを取得
- 専用ツールで `record_data` を事前検証してからレコード追加を実行
- kintoneのドメインとアプリIDを指定してレコードを1件新規追加
- kintoneのドメインとアプリIDを指定して複数レコードを一括追加・更新（upsert）
- kintoneからファイルをダウンロード
- Difyで受け取ったファイルをkintoneへアップロードしfileKeyを取得

## Prerequisites

- 対象のkintoneアプリを閲覧する権限を持つAPIトークン

APIトークン以外の認証方式に対応していません。 Basic認証や SAML認証にも対応していません。

## Usage Examples

### 1. kintone Query

#### 1. 指定したkintoneアプリのすべてのレコードを取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz"
}
```

#### 2. `field1` の値が100以上のレコードのみ取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "query": "field1 >= 100"
}
```

#### 3. 指定したフィールドの値のみを取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "fields": "field1, field2, field3"
}
```

任意パラメータ: `request_timeout`（秒）を指定するとAPIタイムアウトを調整できます（既定値30秒）。

### 2. kintone Get Fields

#### 1. 対象アプリのフィールド定義を取得する（ただし基本的な情報のみ）

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz"
}
```

フィールドコードやフィールドタイプといった基本的な情報を返します。
また、関連レコードの情報は返しません。

#### 2. フル情報を取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "detail_level": true
}
```

`detail_level` を `true` にすると、kintone が返すフィールド定義を全てそのまま返します。省略または `false` の場合は主要情報のみです。

### 3. kintone Query Docs

#### 1. バンドルされているクエリ構文ドキュメントを取得する

kintoneのクエリ構文に関する説明文書を返します。

### 4. kintone Add Record

#### 1. レコードを 1件新規追加する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "record_data": {
    "text_field": {"value": "サンプルテキスト"},
    "number_field": {"value": "100"},
    "date_field": {"value": "2025-03-09"}
  }
}
```

任意パラメータ: `request_timeout`（秒）でAPIタイムアウトを変更できます。既定値は10秒です。

### 5. kintone Validate Record Data

`kintone_add_record` に渡す予定の `record_data` JSON 文字列を、アプリのフィールド定義に基づいて検証します。

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "record_data": "{\"text_field\": {\"value\": \"サンプルテキスト\"}, \"number_field\": {\"value\": 100}}"
}
```

構造および型チェックを通過すると、整形済みの JSON をそのまま返すため、次の `kintone_add_record` 呼び出しに再利用できます。検証に失敗した場合は、具体的なエラー内容をメッセージとして返します。

### 6. kintone Record Data Docs

`kintone_add_record` で利用する `record_data` のJSON構文ガイドを返します。引数は不要で、サンプル構造、フィールドタイプ別ルール、プラグイン内部のバリデーション仕様、よくあるエラーを含む文章を返します。

### 7. kintone Upsert Records

#### 1. 複数のレコードを一度に追加する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "records_data": {
    "records": [
      {
        "record": {
          "text_field": {"value": "サンプルテキスト1"},
          "number_field": {"value": "100"},
          "date_field": {"value": "2025-03-09"}
        }
      },
      {
        "record": {
          "text_field": {"value": "サンプルテキスト2"},
          "number_field": {"value": "200"},
          "date_field": {"value": "2025-03-10"}
        }
      }
    ]
  }
}
```

#### 2. updateKeyを使用して既存のレコードを更新する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "records_data": {
    "records": [
      {
        "updateKey": {
          "field": "key_field",
          "value": "unique_value_1"
        },
        "record": {
          "text_field": {"value": "更新テキスト1"},
          "number_field": {"value": "150"}
        }
      },
      {
        "updateKey": {
          "field": "key_field",
          "value": "unique_value_2"
        },
        "record": {
          "text_field": {"value": "更新テキスト2"},
          "number_field": {"value": "250"}
        }
      }
    ]
  }
}
```

### 8. kintone Download File

#### 1. ファイルキーを指定してkintoneからファイルをダウンロードする

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "file_key": "20250301010101E3C4F3D8871A4BA28360BA3F798D0455165"
}
```

#### ファイルキーの取得方法

ファイルキーを取得するには：
1. `kintone_query` ツールを使用して添付ファイルフィールドを含むレコードを取得
2. レスポンス内の添付ファイルフィールド値を確認（例：`"添付ファイル": [{"fileKey": "xxxxxxxx"}]`）
3. `fileKey` の値を、このツールの `file_key` パラメータとして使用

### 9. kintone Upload File

#### 1. 添付ファイルをアップロードして fileKey を取得する

`upload_file` には 1件以上のファイルを指定できます。Dify のファイル入力コンポーネントから自動的に渡されるため、JSON には記述しません。任意で `request_timeout` を指定できます。

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "file_names": "report.pdf"
}
```

応答では変数 `uploaded_files` が常に返り、`fileKey` を保持するオブジェクトのリストとして利用できます。

- 単一ファイル例: `uploaded_files = [{"fileKey": "202510301234ABCD"}]`
- 複数ファイル例: `uploaded_files = [{"fileKey": "20251030AAA"}, {"fileKey": "20251030BBB"}]`

標準出力の扱いは次のとおりです。

- `json`: `records_mapping` を指定しない場合は `{"uploaded_files": [...]}`、指定した場合は `{"records_data": {...}}` が格納されるため、そのまま `kintone_upsert_records` に渡せます。
- `text`: 上記 JSON と同じ内容を文字列として出力します。
- 互換性確保のため `uploaded_files` / `records_data` の変数メッセージも従来どおり返します。

主なパラメータ:

- `upload_file`（必須, files）: アップロードするファイル本体を1件以上指定します。
- `file_names`（任意, 文字列またはJSON配列）: kintoneへ渡すファイル名を上書きします。単一ファイル時は文字列、複数ファイル時はファイル数と同数の配列（例: `["a.pdf", "b.pdf"]`）。
- `records_mapping`（任意, 文字列またはJSONオブジェクト）: `kintone_upsert_records` 向けの `records` ペイロードを自動生成する設定を渡します（詳細は下記参照）。
- `request_timeout`（任意, 数値）: kintone API 呼び出しのタイムアウト秒数（既定値 30 秒）。

records_mapping を指定すると、`records_data` という JSON 文字列も出力され、そのまま `kintone_upsert_records` の `records_data` に渡せます。

任意パラメータ `file_names` を指定すると、kintone へ送信するファイル名を上書きできます。単一ファイル時は文字列、複数ファイル時はファイル数と同じ要素数の JSON 配列（例: `["a.pdf", "b.pdf"]`）を指定してください。


records_mapping の例（1件のレコードにファイルを添付する場合。複数ファイルをアップロードした場合は同じレコードにまとめて添付されます）:

```json
{
  "records": [
    {
      "updateKey": {"field": "顧客ID", "value": "CUST-001"},
      "attachment_field": "添付ファイル",
      "record": {
        "メモ": {"value": "最新のレポートを添付しました"}
      }
    }
  ]
}
```

複数のレコードを指定する場合、`records` の件数はアップロードしたファイル数と一致させてください（各レコードに1件の fileKey が割り当たります）。単一のレコードのみ指定した場合は、アップロードしたファイル数に関わらず全ての fileKey がそのレコードの添付フィールドに追加されます。

`records_mapping` を使用しない場合は、Dify の標準ノードを積み上げて `records_data` を構築します。例えば以下のような構成です。

1. **for-each（イテレーション）ノード** — `nodes.upload_file_to_kintone.outputs.json.uploaded_files` をループし、`loop.item.fileKey` や `loop.index` を利用して `fileKey` と対応する `updateKey` を取得します（既存レコードを特定する値は、入力フォームや前段の検索ノードから受け取ります）。
   ```yaml
   - id: loop_records
     type: loop
     loop_variable: "{{ nodes.upload_file_to_kintone.outputs.json.uploaded_files }}"
     parameters:
       update_key_field: "{{ inputs.update_key_field }}"
       update_key_values: "{{ inputs.update_key_values }}"  # 例: カンマ区切り → split して使用
   ```
2. **テンプレート（JSON）ノード** — ループ結果を使って `{"records": [...]}` を生成し、添付フィールドに `{"value": [{"fileKey": ...}]}` を差し込みます。必要に応じて `Collection → Template` を使い、複数の fileKey を 1レコードにまとめる配列を事前に作成します。
   ```yaml
   - id: build_records_data
     type: template
     format: json
     template: |
       {
         "records": [
         {% for item in nodes.loop_records.outputs %}
           {
             "updateKey": {
               "field": "{{ item.updateKey.field }}",
               "value": "{{ item.updateKey.value }}"
             },
             "record": {
               "添付ファイル": {
                 "value": [
                   {"fileKey": "{{ item.fileKey }}"}
                 ]
               }
             }
           }{% if not loop.last %},{% endif %}
         {% endfor %}
         ]
       }
   ```
3. **kintone_upsert_records ノード** — テンプレート出力を `records_data` として渡し、アップロードしたファイルを添付します。

この構成なら、`records_mapping` を使わずともファイルごとの割り当て方法（1レコードにまとめる／レコードごとに分配する等）を柔軟に制御できます。Collection ノードを併用すれば、ループで収集した fileKey の配列を 1レコードに集約することも容易です。

また、Python スクリプトノードで `records` を組み立てる方法もあります。`json` 出力から fileKey を取得し、下記のようなスクリプトで JSON 文字列を生成すれば、同じく `kintone_upsert_records` にそのまま渡せます。

```python
import json

file_keys = nodes.upload_file_to_kintone.outputs["json"]["uploaded_files"]
records = []

for fk in file_keys:
    records.append({
        "updateKey": {"field": inputs.update_key_field, "value": inputs.update_key_value},
        "record": {
            "添付ファイル": {"value": [{"fileKey": fk["fileKey"]}]}
        }
    })

outputs["records_data"] = json.dumps({"records": records}, ensure_ascii=False)
```

`records_mapping` を指定すればこれらのノード（あるいはスクリプト）を省略でき、`kintone_upload_file` → `kintone_upsert_records` を直接つなぐだけで済むため、ワークフローの簡潔さが格段に向上します。

あわせて、アップロード結果を説明するテキストメッセージが返ります。単一ファイルの場合は例: `ファイル 'report.pdf' のアップロードに成功しました。fileKey: 202510301234ABCD`、複数ファイルの場合は `2件のファイルをアップロードしました。ファイル: report1.pdf, report2.pdf / fileKeys: ...` のように件数とファイル名／fileKey の一覧が通知されます。

任意パラメータ: `request_timeout`（秒）で一括リクエストのタイムアウトを設定できます（既定値30秒）。

** 「kintone」はサイボウズ株式会社の登録商標です。

ここに記載している内容は情報提供を目的としており、個別のサポートはできません。
設定内容についてのご質問やご自身の環境で動作しないといったお問い合わせをいただいても対応はできませんので、ご了承ください。
