# kintone_integration_unofficial

**Author:** r3-yamauchi
**Version:** 0.1.5
**Type:** tool

## Description

これは [kintone](https://kintone.cybozu.co.jp/) アプリのレコードを読み書きしたり、添付ファイルをアップロード/ダウンロードする際に便利な機能を提供する、**非公式**の [Dify](https://dify.ai/jp) 用ツール・プラグインです。

ソースコードを [GitHub リポジトリ](https://github.com/r3-yamauchi/dify-kintone-plugin) で公開しています。

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/dify-kintone-plugin)

## Features

- kintoneのドメインとアプリIDを指定してレコードを取得
- kintoneのドメインとアプリIDを指定してフィールド定義を取得
- kintoneのクエリ構文仕様文字列を取得
- kintone_add_record向け`record_data`構文のリファレンスを取得
- kintone_add_record向け`record_data`の内容を検証
- kintoneのドメインとアプリIDを指定してレコードを1件新規追加
- kintoneレコードのコメント欄へ（メンション付きで）投稿
- kintoneのドメインとアプリIDを指定して複数レコードを一括追加・更新（upsert）
- JSON文字列または配列からupdateKey付きのupsert用`records_data`を生成
- JSON文字列または配列からkintoneテーブル(SUBTABLE)行構造を生成
- fileKeyを指定してkintoneからファイルをダウンロード
- ファイルをkintoneへアップロードし、一時的なfileKeyを取得

## Prerequisites

- 対象のkintoneアプリを閲覧する権限を持つAPIトークン

APIトークン以外の認証方式に対応していません。 Basic認証や SAML認証にも対応していません。

## 設定

1. プラグインのプロバイダー設定画面で `kintone_domain` と `kintone_api_token` の値を入力できます。APIトークンはカンマ区切り形式（例: `token1,token2`）で最大9個まで指定でき、10個以上を指定するとエラーになります。
2. 各ツールでも APIトークンを指定できます。各ツールで指定しない場合はプロバイダー設定値が使われ、指定するとその値が上書き使用されます（プロバイダー設定したAPIトークンは使用されません）

## Usage Examples

### 1. kintone Query

#### 1. 指定したkintoneアプリのすべてのレコードを取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92"
}
```

#### 2. `field1` の値が100以上のレコードのみ取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "query": "field1 >= 100"
}
```

#### 3. 指定したフィールドの値のみを取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "fields": "field1, field2, field3"
}
```

任意パラメータ: `request_timeout`（秒）を指定するとAPIタイムアウトを調整できます（既定値30秒）。

`output_mode` パラメータを指定すると、出力形式を選べます。

| 値 | 挙動 |
| --- | --- |
| `text_only` | テキストのみ |
| `json_stream` | JSON をページ単位で逐次返却（テキストは省略） |
| `both` (既定) | テキストと JSON をまとめて返却 |

レスポンス例は次の通りです。

```
Text:
取得したレコード件数: 12
顧客名: ACME株式会社
担当者: 山田
---
顧客名: ベータ商事
担当者: 佐藤
...

JSON:
{
  "summary": {
    "total_records": 12,
    "requests_made": 3,
    "request_limit": 500,
    "initial_offset": 0,
    "final_offset": 1000,
    "used_pagination": true,
    "fields": ["顧客名", "担当者"],
    "effective_query": "Status = \"完了\" order by 更新日時 desc",
    "user_defined_limit": null,
    "user_defined_offset": null
  },
  "records": [
    {
      "顧客名": {"type": "SINGLE_LINE_TEXT", "value": "ACME株式会社"},
      "担当者": {"type": "SINGLE_LINE_TEXT", "value": "山田"}
    },
    {
      "顧客名": {"type": "SINGLE_LINE_TEXT", "value": "ベータ商事"},
      "担当者": {"type": "SINGLE_LINE_TEXT", "value": "佐藤"}
    },
    ...
  ]
}
```

### 2. kintone Get Fields

#### 1. 対象アプリのフィールド定義を取得する（ただし基本的な情報のみ）

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92"
}
```

フィールドコードやフィールドタイプといった基本的な情報を返します。
関連レコードの情報は返しません。

#### 2. フル情報を取得する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "detail_level": true
}
```

`detail_level` を `true` にすると、kintone が返すフィールド定義を全てそのまま返します。
省略または `false` の場合は主要情報のみです。

### 3. kintone Query Docs

#### 1. バンドルされているクエリ構文ドキュメントを取得する

kintoneのクエリ構文に関する説明文書を返します。

### 4. kintone Add Record

#### 1. レコードを 1件新規追加する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "record_data": {
    "text_field": {"value": "サンプルテキスト"},
    "number_field": {"value": "100"},
    "date_field": {"value": "2025-03-09"}
  }
}
```

任意パラメータ: `request_timeout`（秒）でAPIタイムアウトを変更できます。既定値は10秒です。

### 5. kintone Validate Record Data

`kintone_add_record` に渡すための `record_data` JSON 文字列を、アプリのフィールド定義に基づいて検証します。

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "record_data": "{\"text_field\": {\"value\": \"サンプルテキスト\"}, \"number_field\": {\"value\": 100}}"
}
```

構造および型チェックを通過すると、整形済みの JSON をそのまま返します。検証に失敗した場合は、具体的なエラー内容をメッセージとして返します。

### 6. kintone Record Data Docs

`kintone_add_record` で利用する `record_data` のJSON構文ガイドを返します。引数は不要で、サンプル構造、フィールドタイプ別ルール、プラグイン内部のバリデーション仕様、よくあるエラーを含む文章を返します。

### 7. kintone Add Record Comment

#### 1. レコードコメントを投稿する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "record_id": 456,
  "comment_text": "見積書を更新しました。ご確認ください。",
  "mentions": "[{\"code\": \"sales-team\", \"type\": \"GROUP\"}]"
}
```

`comment_text` には最大 10,000 文字までのテキストを指定できます。`mentions` は任意で、`[{"code":"user1","type":"USER"}]` のような JSON 配列を渡すと、コメントにメンションを追加できます。`type` には `USER` / `GROUP` / `ORGANIZATION` を指定でき、最大10件までメンション可能です。

成功時には以下の情報が得られます。

- 変数 `comment_id`: 追加されたコメントID
- 変数 `response`: kintoneが返したJSON（作成者やタイムスタンプを含む）
- `json` 出力: `comment_id`, `record_id`, `app_id`, `mentions_count`, `created_at` をまとめたサマリー
- `text` 出力: 投稿結果のメッセージ

任意パラメータ: `request_timeout`（秒）でコメント投稿APIのタイムアウトを変更できます（既定値10秒）。

### 8. kintone Upsert Records

#### 1. 複数のレコードを一度に追加する

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
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
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
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

### 9. kintone Build Records Data

JSON文字列または配列のオブジェクトから、`kintone_upsert_records` が期待する `records_data` を生成し、指定した `updateKey` を自動で付与します。

```json
{
  "records_source": "[{\"コード\": \"A-001\", \"名称\": \"初期データ\"}, {\"コード\": \"A-002\", \"名称\": \"2件目\"}]",
  "updateKey": "コード"
}
```

レスポンス例:

```json
{
  "records_data": {
    "records": [
      {
        "updateKey": {"field": "コード", "value": "A-001"},
        "record": {
          "コード": {"value": "A-001"},
          "名称": {"value": "初期データ"}
        }
      },
      {
        "updateKey": {"field": "コード", "value": "A-002"},
        "record": {
          "コード": {"value": "A-002"},
          "名称": {"value": "2件目"}
        }
      }
    ]
  }
}
```

### 10. kintone Build Subtable Rows

JSON文字列または配列を、kintoneテーブル(SUBTABLE)フィールドが受け付ける `rows` 形式に変換します。

```json
{
  "subtable_source": "[{\"セッションID\": \"D1-101\", \"タイトル\": \"Example\"}]"
}
```

レスポンス例:

```json
{
  "rows": [
    {
      "value": {
        "セッションID": {"value": "D1-101"},
        "タイトル": {"value": "Example"}
      }
    }
  ]
}
```

配列をそのまま渡すことも可能です。

```json
{
  "subtable_source": [
    {"セッションID": "D1-101", "タイトル": "Example"},
    {"セッションID": "D1-102", "タイトル": "Another"}
  ]
}
```

### 11. kintone Download File

#### 1. ファイルキーを指定してkintoneからファイルをダウンロードする

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "file_key": "20250301010101E3C4F3D8871A4BA28360BA3F798D0455165"
}
```

#### ファイルキーの取得方法

ファイルキーを取得するには：
1. `kintone_query` ツールを使用して添付ファイルフィールドを含むレコードを取得
2. レスポンス内の添付ファイルフィールド値を確認（例：`"添付ファイル": [{"fileKey": "xxxxxxxx"}]`）
3. `fileKey` の値を、このツールの `file_key` パラメータとして使用

### 12. kintone Upload File

#### 1. 添付ファイルをアップロードして fileKey を取得する

`upload_file` には 1件以上のファイルを指定できます。任意で `request_timeout` を指定できます。

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "file_names": "report.pdf"
}
```

応答では変数 `uploaded_files` が常に返り、`fileKey` の入ったオブジェクトのリストとして利用できます。

- 単一ファイル例: `uploaded_files = [{"fileKey": "c15b3870-7505-4ab6-9d8d-b9bdbc74f5d6"}]`
- 複数ファイル例: `uploaded_files = [{"fileKey": "c15b3870-7505-4ab6-9d8d-b9bdbc74f5d6"}, {"fileKey": "a12b3456-7890-1ab2-3d4d-b5bdbc67f8d9"}]`

ファイルをアップロードすると kintone内の一時保管領域にファイルが保存され、一時保管領域用の `fileKey` が発行されます。この `fileKey` を使用して kintoneレコードの添付ファイルフィールドにファイルを添付できます。レコードに添付しない場合、一時保管領域のファイルは 3日間で削除されます。

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

あわせて、アップロード結果を説明するテキストメッセージが返ります。単一ファイルの場合は例: `ファイル 'report.pdf' のアップロードに成功しました。fileKey: c15b3870-7505-4ab6-9d8d-b9bdbc74f5d6`、複数ファイルの場合は `2件のファイルをアップロードしました。ファイル: report1.pdf, report2.pdf / fileKeys: ...` のように件数とファイル名／fileKey の一覧が通知されます。

任意パラメータ: `request_timeout`（秒）で一括リクエストのタイムアウトを設定できます（既定値30秒）。

** 「kintone」はサイボウズ株式会社の登録商標です。

ここに記載している内容は情報提供を目的としており、個別のサポートはできません。
設定内容についてのご質問やご自身の環境で動作しないといったお問い合わせをいただいても対応はできませんので、ご了承ください。
