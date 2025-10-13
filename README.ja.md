# dify-kintone-plugin

**Author:** r3-yamauchi
**Version:** 0.0.6
**Type:** tool

## Description

これは [kintone](https://kintone.cybozu.co.jp/) アプリのレコードを取得するために使用できる [Dify](https://dify.ai/jp) プラグインです。

このプラグインのソースコードは [GitHub リポジトリ](https://github.com/r3-yamauchi/dify-kintone-plugin) で公開しています。

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/dify-kintone-plugin)

## Features

- kintoneのドメインとアプリIDを指定してレコードを取得
- kintoneのドメインとアプリIDを指定してフィールド定義を取得
- kintoneのクエリ構文仕様文字列を取得
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
  "detail_level": "full"
}
```

`detail_level` に `full` を指定すると、kintone が返すフィールド定義を全てそのまま返します。

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

### 5. kintone Upsert Records

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

### 6. kintone Download File

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


** 「kintone」はサイボウズ株式会社の登録商標です。

ここに記載している内容は情報提供を目的としており、個別のサポートはできません。
設定内容についてのご質問やご自身の環境で動作しないといったお問い合わせをいただいても対応はできませんので、ご了承ください。
