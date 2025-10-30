# kintone_integration

**Author:** r3-yamauchi
**Version:** 0.0.8
**Type:** tool

English | [Japanese](https://github.com/r3-yamauchi/dify-kintone-plugin/blob/main/readme/README_ja_JP.md)

## Description

This is a plugin for interacting with [kintone](https://kintone.cybozu.co.jp/) apps. By using this plugin, you can easily access and manage the information stored in your kintone app.

The source code of this plugin is available in the [GitHub repository](https://github.com/r3-yamauchi/dify-kintone-plugin).

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/dify-kintone-plugin)

## Features

- Retrieve records by specifying the kintone domain and app ID
- Fetch field definitions by specifying the kintone domain and app ID
- Obtain the reference text for the kintone query syntax
- Retrieve the `record_data` syntax reference for `kintone_add_record`
- Validate `record_data` with a dedicated tool before adding records
- Add a single record by specifying the kintone domain and app ID
- Upsert (bulk insert/update) multiple records by specifying the kintone domain and app ID
- Download files from kintone
- Upload files received by Dify to kintone and obtain the fileKey

## Prerequisites

- An API token with appropriate permissions for the target kintone app:
  - View permissions for retrieving records
  - Add permissions for adding new records
  - Update permissions for updating existing records

## Configuration

This plugin has no configuration settings.

## Usage Examples

### 1. kintone Query

#### 1. Retrieve all records in the specified kintone app

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz"
}
```

#### 2. Retrieve only records where `field1` is 100 or greater

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "query": "field1 >= 100"
}
```

#### 3. Retrieve only the specified fields

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "fields": "field1, field2, field3"
}
```

Optional parameter: specify `request_timeout` (seconds) to adjust the API timeout (default 30 seconds).

### 2. kintone Get Fields

#### 1. Retrieve basic field definitions for the target app

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz"
}
```

Returns basic information such as field codes and field types. Information about related records is not included.

#### 2. Retrieve the full field definitions

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "detail_level": true
}
```

When `detail_level` is `true`, the tool returns the complete field definition as provided by kintone. When omitted or set to `false`, only the primary information is returned.

### 3. kintone Query Docs

#### 1. Retrieve the bundled documentation for the query syntax

Returns documentation explaining the kintone query syntax.

### 4. kintone Add Record

#### 1. Add a single new record

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "record_data": {
    "text_field": {"value": "Sample text"},
    "number_field": {"value": "100"},
    "date_field": {"value": "2025-03-09"}
  }
}
```

Optional parameter: specify `request_timeout` (seconds) to adjust the API timeout (default 10 seconds).

### 5. kintone Validate Record Data

Validate the `record_data` JSON string that will be passed to `kintone_add_record`, based on the field definitions of the app.

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "record_data": "{\"text_field\": {\"value\": \"Sample text\"}, \"number_field\": {\"value\": 100}}"
}
```

If the structure and types pass validation, the tool returns formatted JSON that can be reused in the subsequent `kintone_add_record` call. If validation fails, the tool returns a message describing the errors.

### 6. kintone Record Data Docs

Returns a JSON syntax guide for the `record_data` used by `kintone_add_record`. No parameters are required. The response contains sample structures, rules by field type, the plugin’s internal validation rules, and a list of common errors.

### 7. kintone Upsert Records

#### 1. Add multiple records at once

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "records_data": {
    "records": [
      {
        "record": {
          "text_field": {"value": "Sample text 1"},
          "number_field": {"value": "100"},
          "date_field": {"value": "2025-03-09"}
        }
      },
      {
        "record": {
          "text_field": {"value": "Sample text 2"},
          "number_field": {"value": "200"},
          "date_field": {"value": "2025-03-10"}
        }
      }
    ]
  }
}
```

#### 2. Update existing records using `updateKey`

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
          "text_field": {"value": "Updated text 1"},
          "number_field": {"value": "150"}
        }
      },
      {
        "updateKey": {
          "field": "key_field",
          "value": "unique_value_2"
        },
        "record": {
          "text_field": {"value": "Updated text 2"},
          "number_field": {"value": "250"}
        }
      }
    ]
  }
}
```

### 8. kintone Download File

#### 1. Download a file from kintone by specifying the file key

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "file_key": "20250301010101E3C4F3D8871A4BA28360BA3F798D0455165"
}
```

#### How to obtain the file key

1. Use the `kintone_query` tool to retrieve records that include the attachment field.
2. Check the attachment field in the response (for example: `"Attachment": [{"fileKey": "xxxxxxxx"}]`).
3. Pass the `fileKey` value to the `file_key` parameter of this tool.

### 9. kintone Upload File

#### 1. Upload attachments and obtain file keys

Specify one or more files via `upload_file`. Dify automatically supplies the file data, so you do not need to provide it in JSON. You can optionally specify `request_timeout`.

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "abcdefghijklmnopqrstuvwxyz",
  "file_names": "report.pdf"
}
```

The response always contains the `uploaded_files` variable, a list of objects that hold the returned `fileKey` values.

- Single file example: `uploaded_files = [{"fileKey": "202510301234ABCD"}]`
- Multiple files example: `uploaded_files = [{"fileKey": "20251030AAA"}, {"fileKey": "20251030BBB"}]`

Standard outputs are populated as follows:

- `json`: when `records_mapping` is omitted, it contains `{"uploaded_files": [...]}`; when provided, it contains `{"records_data": {...}}` so you can pass it straight to `kintone_upsert_records`.
- `text`: mirrors the JSON payload above (either the uploaded-files list or the `records_data` JSON string).
- `uploaded_files` / `records_data` variable messages continue to be emitted for backward compatibility.

Key parameters:

- `upload_file` (required, files): one or more files to upload.
- `file_names` (optional, string or JSON array): overrides the filenames sent to kintone. Provide a string for a single file, or a JSON array (e.g. `["a.pdf", "b.pdf"]`) with the same length as the number of files.
- `records_mapping` (optional, string or JSON object): supply mapping instructions to auto-build the `records` payload for `kintone_upsert_records` (see below).
- `request_timeout` (optional, number): timeout in seconds for the kintone API request (default 30 seconds).

When `records_mapping` is supplied, the tool also outputs `records_data`, a JSON string that can be passed directly to `kintone_upsert_records`.

If you provide `file_names`, you can override the filenames sent to kintone. Supply a single string for one file, or a JSON array (for example `["a.pdf", "b.pdf"]`) with the same number of entries as the files you upload.


Example `records_mapping` payload (single record; if multiple files are uploaded, they are all attached to the same record):

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

If multiple records are listed, the number of entries must match the number of uploaded files so each record receives one file key. When only a single record is provided, all uploaded file keys are added to that record’s attachment field regardless of the file count.

If you prefer not to use `records_mapping`, you can build `records_data` manually with standard Dify nodes:

1. **for-each node** – iterate over `nodes.upload_file_to_kintone.outputs.json.uploaded_files` and capture each `fileKey` (alongside any known `updateKey` information such as record IDs). Example:
   ```yaml
   - id: loop_records
     type: loop
     loop_variable: "{{ nodes.upload_file_to_kintone.outputs.json.uploaded_files }}"
     parameters:
       update_key_field: "{{ inputs.update_key_field }}"
       update_key_values: "{{ inputs.update_key_values }}"  # e.g., comma-separated list → split inside the loop
   ```
2. **Template node (JSON mode)** – compose the final `{ "records": [...] }` payload by inserting the collected file keys into the attachment field structure (`{"value": [{"fileKey": ...}]}`) required by `kintone_upsert_records`.
3. **Template or “Collection → Template”** – optionally use a Collection node to gather file keys or update keys into arrays before the final template step if you want to aggregate multiple keys into one record.
4. **kintone_upsert_records** – pass the template output as `records_data`.

This loop + template pattern lets you control how file keys are grouped across records—for example, gather all keys and attach them to a single record, or map each key to a different record using the loop index—without enabling `records_mapping`.

If you prefer a Python script node, you can assemble the payload in code and emit `records_data` directly. The snippet below reads from the JSON output and writes back a JSON string:

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

Using `records_mapping` bypasses all of these extra nodes/scripts so the workflow can simply be `kintone_upload_file → kintone_upsert_records` by selecting `nodes.upload_file_to_kintone.outputs.json.records_data` for the `records_data` parameter (or `text` if you prefer the raw JSON string).

A text message describing the upload is also returned. For a single file you’ll see, for example, `Uploaded file 'report.pdf' successfully. fileKey: 202510301234ABCD`; for multiple files the message lists the count plus the filenames and file keys (`Uploaded 2 files. Files: report1.pdf, report2.pdf / fileKeys: ...`).

Optional parameter: specify `request_timeout` (seconds) to set the timeout for bulk requests (default 30 seconds).

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

**"kintone" is a registered trademark of Cybozu, Inc.**

The information provided here is for reference only. Support is not available for individual environments. We are unable to respond to inquiries about configuration details or cases where the plugin does not work in your environment.
