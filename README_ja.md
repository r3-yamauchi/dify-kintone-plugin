# dify-kintone-plugin

**Author:** r3-yamauchi
**Version:** 0.0.7
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

### 6. kintone Upsert Records

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

任意パラメータ: `request_timeout`（秒）で一括リクエストのタイムアウトを設定できます（既定値30秒）。

### 7. kintone Download File

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

### 8. kintone Record Data Docs

`kintone_add_record` で利用する `record_data` のJSON構文ガイドを返します。引数は不要で、サンプル構造、フィールドタイプ別ルール、プラグイン内部のバリデーション仕様、よくあるエラーを含む文章を返します。


** 「kintone」はサイボウズ株式会社の登録商標です。

ここに記載している内容は情報提供を目的としており、個別のサポートはできません。
設定内容についてのご質問やご自身の環境で動作しないといったお問い合わせをいただいても対応はできませんので、ご了承ください。
