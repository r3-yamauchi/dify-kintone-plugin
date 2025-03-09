# dify-kintone-plugin

**Author:** r3-yamauchi
**Version:** 0.0.4
**Type:** tool

## Description

これは [kintone](https://kintone.cybozu.co.jp/) アプリのレコードを取得するために使用できる [Dify](https://dify.ai/jp) プラグインです。

使用時のイメージを [ブログ](https://www.r3it.com/blog/dify-kintone-20250305-yamauchi) で紹介しています。

## Features

- kintoneのドメインとアプリIDを指定してレコードを取得
- kintoneのドメインとアプリIDを指定してレコードを1件新規追加

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

### 2. kintone Add Record

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


** 「kintone」はサイボウズ株式会社の登録商標です。

ここに記載している内容は情報提供を目的としており、個別のサポートはできません。
設定内容についてのご質問やご自身の環境で動作しないといったお問い合わせをいただいても対応はできませんので、ご了承ください。
