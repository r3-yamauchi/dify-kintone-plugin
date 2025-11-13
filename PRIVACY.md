# Privacy

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

For privacy-related questions, please contact the repository maintainers via GitHub issues.

All plugin operations—record queries, validation, creation/upsert, and file upload/download—use kintone's official REST APIs. For kintone-side privacy policies, please refer to: [cybozu.com Terms of Use](https://www.cybozu.com/jp/terms/).
