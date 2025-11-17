# kintone_integration

**Author:** r3-yamauchi
**Version:** 0.1.8
**Type:** tool

English | [Japanese](https://github.com/r3-yamauchi/dify-kintone-plugin/blob/main/readme/README_ja_JP.md)

## Description

This is an **unofficial** plugin for interacting with [kintone](https://kintone.cybozu.co.jp/) apps. By using this plugin, you can easily access and manage the information stored in your kintone app.

> ⚠️ **Note: This is an unofficial plugin**  
> This plugin is not developed or maintained by Cybozu, the provider of kintone. It is a community-developed plugin created by independent developers. Use at your own discretion.

The source code of this plugin is available in the [GitHub repository](https://github.com/r3-yamauchi/dify-kintone-plugin).

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/r3-yamauchi/dify-kintone-plugin)

## Features

- Retrieve records by specifying the kintone domain and app ID
- Fetch field definitions by specifying the kintone domain and app ID
- Obtain the reference text for the kintone query syntax
- Flatten raw kintone record JSON with the `kintone_flatten_json` tool.
- Retrieve the `record_data` syntax reference for `kintone_add_record`
- Validate `record_data` with a dedicated tool before adding records
- Add a single record by specifying the kintone domain and app ID
- Post comments to an existing record with optional mentions
- Upsert (bulk insert/update) multiple records by specifying the kintone domain and app ID
- Build kintone upsert `records_data` payloads from a JSON string or array input with automatic `updateKey`
- Build kintone subtable rows (`value` array) from a JSON string or array input
- Download files from kintone
- Upload files received by Dify to kintone and obtain the fileKey

## Prerequisites

- An API token with appropriate permissions for the target kintone app:
  - View permissions for retrieving records
  - Add permissions for adding new records
  - Update permissions for updating existing records

## Configuration

1. In the provider settings, you can supply values for `kintone_domain` and `kintone_api_token`. The token accepts up to nine comma-separated entries (e.g., `token1,token2`); providing ten or more triggers a validation error.
2. Each tool also allows you to specify an API token. When left unset, the provider-level token is used; when provided, the tool-level value takes precedence.

## Usage Examples

### 1. kintone Query

#### 1. Retrieve all records in the specified kintone app

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92"
}
```

#### 2. Retrieve only records where `field1` is 100 or greater

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "query": "field1 >= 100"
}
```

#### 3. Retrieve only the specified fields

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "fields": "field1, field2, field3"
}
```

Optional parameter: specify `request_timeout` (seconds) to adjust the API timeout (default 30 seconds).

You can also use the optional `output_mode` parameter to choose the response format.

| Value | Behavior |
| --- | --- |
| `text_only` | Returns only the text output. |
| `json_stream` | Streams the JSON payload page by page without the text output. |
| `both` (default) | Returns both the text summary and the aggregated JSON payload. |

A typical response looks like:

```
Text:
取得したレコード件数: 12
CustomerName: ACME Inc.
Representative: Yamada
---
CustomerName: Beta Trading
Representative: Sato
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
    "fields": ["CustomerName", "Representative"],
    "effective_query": "Status = \"完了\" order by 更新日時 desc",
    "user_defined_limit": null,
    "user_defined_offset": null
  },
  "records": [
    {
      "CustomerName": {"type": "SINGLE_LINE_TEXT", "value": "ACME Inc."},
      "Representative": {"type": "SINGLE_LINE_TEXT", "value": "Yamada"}
    },
    {
      "CustomerName": {"type": "SINGLE_LINE_TEXT", "value": "Beta Trading"},
      "Representative": {"type": "SINGLE_LINE_TEXT", "value": "Sato"}
    },
    ...
  ]
}
```

### 2. kintone Get Fields

#### 1. Retrieve basic field definitions for the target app

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92"
}
```

Returns basic information such as field codes and field types. Information about related records is not included.

#### 2. Retrieve the full field definitions

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "detail_level": true
}
```

When `detail_level` is `true`, the tool returns the complete field definition as provided by kintone. When omitted or set to `false`, only the primary information is returned.

### 3. kintone Query Docs

#### 1. Retrieve the bundled documentation for the query syntax

Returns documentation explaining the kintone query syntax.

### 4. kintone Flatten JSON

Convert the raw record array (typically the JSON returned by `kintone_query`) into flattened objects.

#### 1. Flatten the entire record array

```json
{
  "records_json": [
    {
      "$id": {"value": "2"},
      "TXT1": {"value": "eee"},
      "NUM1": {"value": "123"},
      "TABLE1": {
        "type": "SUBTABLE",
        "value": [
          {
            "id": "166884",
            "value": {
              "TXT11": {"value": "ooo"},
              "NUM2": {"value": "456"}
            }
          }
        ]
      }
    }
  ]
}
```

Response (text output mirrors the JSON message):

```json
[
  {
    "$id": "2",
    "NUM1": "123",
    "TABLE1": [
      { "id": "166884", "NUM2": "456", "TXT11": "ooo" }
    ],
    "TXT1": "eee"
  }
]
```

#### 2. Extract a specific subtable with a field filter

```json
{
  "records_json": [
    {
      "$id": {"value": "2"},
      "TXT1": {"value": "eee"},
      "NUM1": {"value": "123"},
      "TABLE1": {
        "type": "SUBTABLE",
        "value": [
          {
            "id": "166884",
            "value": {
              "TXT11": {"value": "ooo"},
              "NUM2": {"value": "456"}
            }
          }
        ]
      }
    }
  ],
  "subtable_field_code": "TABLE1",
  "fields": "TXT1,NUM1,TXT11"
}
```

Response:

```json
[
  { "TXT1": "eee", "NUM1": "123", "TXT11": "ooo" }
]
```

`subtable_field_code` limits the output to the specified SUBTABLE rows, while `fields` (comma separated) keeps only the requested field codes and copies parent-level fields into each subtable row.

### 5. kintone Add Record

#### 1. Add a single new record

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "record_data": {
    "text_field": {"value": "Sample text"},
    "number_field": {"value": "100"},
    "date_field": {"value": "2025-03-09"}
  }
}
```

Optional parameter: specify `request_timeout` (seconds) to adjust the API timeout (default 10 seconds).

### 6. kintone Validate Record Data

Validate the `record_data` JSON string that will be passed to `kintone_add_record`, based on the field definitions of the app.

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "record_data": "{\"text_field\": {\"value\": \"Sample text\"}, \"number_field\": {\"value\": 100}}"
}
```

If the structure and types pass validation, the tool returns formatted JSON that can be reused in the subsequent `kintone_add_record` call. If validation fails, the tool returns a message describing the errors.

### 7. kintone Record Data Docs

Returns a JSON syntax guide for the `record_data` used by `kintone_add_record`. No parameters are required. The response contains sample structures, rules by field type, the plugin’s internal validation rules, and a list of common errors.

### 8. kintone Add Record Comment

#### 1. Post a comment to an existing record

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "record_id": 456,
  "comment_text": "Please review the updated quote.",
  "mentions": "[{\"code\": \"sales-team\", \"type\": \"GROUP\"}]"
}
```

The tool posts plain-text comments to the record’s discussion thread. `comment_text` accepts up to 10,000 characters. Use the optional `mentions` parameter to highlight users, groups, or departments by supplying a JSON array with objects such as `{ "code": "user01", "type": "USER" }`. Supported `type` values are `USER`, `GROUP`, and `ORGANIZATION`. Up to ten mentions can be specified per comment.

When the call succeeds, the response includes:

- `comment_id` variable pointing to the newly created comment
- `response` variable with the raw JSON from kintone (creator info, timestamps, etc.)
- `json` message summarizing `comment_id`, `record_id`, `app_id`, `mentions_count`, and `created_at`

Optional parameter: `request_timeout` (seconds) to override the default 10-second timeout.

### 9. kintone Upsert Records

#### 1. Add multiple records at once

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_app_id": 123,
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
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
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
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

### 10. kintone Build Records Data

Convert a JSON string or array of objects into the `records_data` payload expected by `kintone_upsert_records`, automatically populating the `updateKey`.

```json
{
  "records_source": "[{\"コード\": \"A-001\", \"名称\": \"初期データ\"}, {\"コード\": \"A-002\", \"名称\": \"2件目\"}]",
  "updateKey": "コード"
}
```

Response example:

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

### 11. kintone Build Subtable Rows

Transform a JSON string or array into the `value` array required by a kintone subtable field.

```json
{
  "subtable_source": "[{\"セッションID\": \"D1-101\", \"タイトル\": \"Example\"}]"
}
```

Response example:

```json
{
  "value": [
    {
      "value": {
        "セッションID": {"value": "D1-101"},
        "タイトル": {"value": "Example"}
      }
    }
  ]
}
```

You can also submit an array directly:

```json
{
  "subtable_source": [
    {"セッションID": "D1-101", "タイトル": "Example"},
    {"セッションID": "D1-102", "タイトル": "Another"}
  ]
}
```

### 12. kintone Download File

#### 1. Download a file from kintone by specifying the file key

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "file_key": "20250301010101E3C4F3D8871A4BA28360BA3F798D0455165"
}
```

#### How to obtain the file key

1. Use the `kintone_query` tool to retrieve records that include the attachment field.
2. Check the attachment field in the response (for example: `"Attachment": [{"fileKey": "xxxxxxxx"}]`).
3. Pass the `fileKey` value to the `file_key` parameter of this tool.

### 13. kintone Upload File

#### 1. Upload attachments and obtain file keys

Specify one or more files via `upload_file`. Dify automatically supplies the file data, so you do not need to provide it in JSON. You can optionally specify `request_timeout`.

```json
{
  "kintone_domain": "dev-demo.cybozu.com",
  "kintone_api_token": "BuBNIwbRRaUvr33nWXcfUZ5VhaFsJxN0xH4NPN92",
  "file_names": "report.pdf"
}
```

The response always contains the `uploaded_files` variable, a list of objects that hold the returned `fileKey` values.

- Single file example: `uploaded_files = [{"fileKey": "c15b3870-7505-4ab6-9d8d-b9bdbc74f5d6"}]`
- Multiple files example: `uploaded_files = [{"fileKey": "c15b3870-7505-4ab6-9d8d-b9bdbc74f5d6"}, {"fileKey": "a12b3456-7890-1ab2-3d4d-b5bdbc67f8d9"}]`

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

A text message describing the upload is also returned. For a single file you’ll see, for example, `Uploaded file 'report.pdf' successfully. fileKey: c15b3870-7505-4ab6-9d8d-b9bdbc74f5d6`; for multiple files the message lists the count plus the filenames and file keys (`Uploaded 2 files. Files: report1.pdf, report2.pdf / fileKeys: ...`).

Optional parameter: specify `request_timeout` (seconds) to set the timeout for bulk requests (default 30 seconds).

## Privacy Policy

The **kintone_integration** plugin respects user privacy and keeps the exchanged data limited to what is strictly necessary for each tool.

## Data Collection

- **kintone credentials:** Each tool requires a kintone domain, app ID, and at least one API token with the appropriate permissions (view/add/update/upload/download). These values are supplied by you or your workspace administrator.
- **Record payloads:** Tools that create or update records receive the JSON payloads (`record_data`, `records`, `updateKey`, etc.) that you provide.
- **Query parameters:** Search tools receive the query string, optional field lists, pagination controls, and timeout values you enter.
- **File content:** The upload/download tools may handle file binaries that you submit or retrieve from kintone.
- **No additional identifiers:** The plugin does not collect personal information beyond what is present inside the payloads you explicitly pass in.

## Data Usage

- **kintone REST API only:** All collected inputs are sent exclusively to the official kintone REST endpoints (records, file upload/download, etc.) in order to fulfill your requested action (query, validate, add, upsert, upload, or download data).
- **Transient processing:** Record payloads, query results, and file streams are processed in memory and relayed back through Dify. They are not repurposed for analytics or profiling.
- **Logging:** Operational logs intentionally mask API tokens and truncate oversized values to avoid leaking sensitive data.

## Data Storage

- **No permanent storage:** The plugin itself does not write any credentials, record content, or files to disk or an external database.
- **Platform handling:** Credentials you configure are kept within Dify’s secure credential store. Uploaded files flow directly from Dify to kintone and are not retained after the request completes.
- **Result retention:** Any responses are streamed back to Dify and handled according to your workspace’s retention settings.

## Third-party Services

- The plugin communicates only with kintone’s official API servers (`*.cybozu.com` domains).
- No other third-party processors or analytics services are used.

## Security

- All outbound requests use HTTPS and the standard kintone authentication headers.
- API tokens are masked in logs, and error messages redact potentially sensitive details.
- The plugin keeps dependencies minimal and relies on Dify’s runtime isolation for additional protection.

All plugin operations—record queries, validation, creation/upsert, and file upload/download—use kintone's official REST APIs. For kintone-side privacy policies, please refer to: [cybozu.com Terms of Use](https://www.cybozu.com/jp/terms/).

For privacy-related questions, please contact the repository maintainers via GitHub issues.

## Support

If you encounter any issues or have questions, please:

1. Raise an issue on the GitHub repository
2. Contact the plugin author

**"kintone" is a registered trademark of Cybozu, Inc.**

The information provided here is for reference only. Support is not available for individual environments. We are unable to respond to inquiries about configuration details or cases where the plugin does not work in your environment.
