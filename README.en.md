# kintone_integration

**Author:** r3-yamauchi
**Version:** 0.0.6
**Type:** tool

## Description

This is a plugin for interacting with [kintone](https://kintone.cybozu.co.jp/) apps. By using this plugin, you can easily access and manage the information stored in your kintone app.

The source code for this plugin is available in the [GitHub repository](https://github.com/r3-yamauchi/dify-kintone-plugin).

## Features

- Retrieve records by specifying the kintone domain and app ID.
- Filter records by passing a query string to retrieve only specific records.
- Limit the retrieved fields to avoid unnecessary data collection.
- Fetch field definitions so you can inspect field codes and types before building requests.
- Access the full kintone query language specification directly from the plugin.
- Add new records to your kintone app with custom field values.
- Update or insert multiple records at once (upsert) to your kintone app with custom field values.
- Download files from your kintone app using file keys.

## Prerequisites

- An API token with appropriate permissions for the target kintone app:
  - View permissions for retrieving records
  - Add permissions for adding new records
  - Update permissions for updating existing records

## Configuration

This plugin has no configuration settings.

## Usage Examples

### 1. kintone Query

#### 1. Retrieve all records from the specified kintone app:

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz"
}
```

#### 2. Retrieve only records where the value of `field1` is 100 or higher:

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "query": "field1 >= 100"
}
```

#### 3. Retrieve only the values of the specified fields:

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "fields": "field1, field2, field3"
}
```

### 2. kintone Add Record

#### 1. Add a new record to the kintone app:

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

### 3. kintone Upsert Records

#### 1. Add multiple new records to the kintone app:

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

#### 2. Update existing records using updateKey:

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

#### 3. Mix of updates and additions in a single request:

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
          "value": "existing_value"
        },
        "record": {
          "text_field": {"value": "更新されたテキスト"},
          "number_field": {"value": "300"}
        }
      },
      {
        "record": {
          "key_field": {"value": "new_value"},
          "text_field": {"value": "新規テキスト"},
          "number_field": {"value": "400"}
        }
      }
    ]
  }
}
```

### 4. kintone Get Fields

#### 1. Retrieve field definitions for the target app (basic mode):

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz"
}
```

The tool responds with a JSON summary for every field, including `code`, `type`, `required`, `unique`, and `options`, excluding structural fields of types `GROUP`, `RECORD_NUMBER`, and `REFERENCE_TABLE`. This is the default (`detail_level` = `basic`).

#### 2. Retrieve full field definitions:

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "detail_level": "full"
}
```

Setting `detail_level` to `full` returns the complete field metadata exactly as provided by kintone.

### 5. kintone Query Docs

#### 1. Retrieve the query language specification bundled with the plugin:

```json
{}
```

This tool returns the complete kintone query grammar documentation embedded in the plugin. Use it when you need to confirm available operators, functions, or best practices while building queries.

## Field Format for Adding Records

When adding records using the `kintone_add_record` tool, you need to follow kintone's field format. Here are some common field types and their formats:

### Text Field (SINGLE_LINE_TEXT, MULTI_LINE_TEXT)
```json
"field_code": {"value": "テキスト値"}
```

### Number Field (NUMBER)
```json
"field_code": {"value": "123"}
```

### Date Field (DATE)
```json
"field_code": {"value": "2025-03-09"}
```

### Time Field (TIME)
```json
"field_code": {"value": "12:34"}
```

### Datetime Field (DATETIME)
```json
"field_code": {"value": "2025-03-09T12:34:56Z"}
```

### Checkbox Field (CHECK_BOX)
```json
"field_code": {"value": ["選択肢1", "選択肢2"]}
```

### Radio Button Field (RADIO_BUTTON)
```json
"field_code": {"value": "選択肢1"}
```

### Dropdown Field (DROP_DOWN)
```json
"field_code": {"value": "選択肢1"}
```

### Multi-select Field (MULTI_SELECT)
```json
"field_code": {"value": ["選択肢1", "選択肢2"]}
```

### User Selection Field (USER_SELECT)
```json
"field_code": {"value": [{"code": "user1", "type": "USER"}]}
```

### Department Selection Field (ORGANIZATION_SELECT)
```json
"field_code": {"value": [{"code": "dept1", "type": "ORGANIZATION"}]}
```

### Group Selection Field (GROUP_SELECT)
```json
"field_code": {"value": [{"code": "group1", "type": "GROUP"}]}
```

### 6. kintone Download File

#### 1. Download a file from kintone using file key:

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "file_key": "20250301010101E3C4F3D8871A4BA28360BA3F798D0455165"
}
```

#### File Key Retrieval

To get the file key:
1. Use the `kintone_query` tool to retrieve records with attachment fields
2. Look for the attachment field value in the response (e.g., `"添付ファイル": [{"fileKey": "xxxxxxxx"}]`)
3. Use the `fileKey` value as the `file_key` parameter for this tool

## Privacy Policy

This plugin only collects the following necessary information for interacting with kintone:

1. kintone domain, app ID, and API token with appropriate permissions
2. User-provided query parameters for filtering records and selecting fields
3. User-provided record data for adding or updating records

This information is used solely for retrieving records from the specified kintone app and will not be used for other purposes or shared with third parties.

Data retrieval uses kintone's official REST API. For related privacy policies, please refer to: [cybozu.com Terms of Use](https://www.cybozu.com/jp/terms/).

## Support

If you encounter any issues or have questions, please:

1. Raise an issue on the GitHub repository
2. Contact the plugin author
