# Privacy

The kintone plugin respects user privacy and handles data with care. Here's what you need to know about data collection and usage:

## Data Collection

- **kintone Domain/App ID/API Token:** The required credentials are your kintone domain, kintone app ID, and an API token with granted view permissions.
- **Request Destination:** kintone REST API: `https://{kintone-domain}/k/v1/records.json`
- **Request Content:** A query string specifying filtering conditions for kintone records and the fields to retrieve. Both are optional; if not specified, all records and all fields in the target app will be retrieved.
- **No Personal Data Collection:** We do not collect or store any personal user data.

## Data Usage

- The kintone domain, app ID, and API token are used solely for sending requests to [the kintone REST API to retrieve multiple specified kintone records](https://kintone.dev/en/docs/kintone/rest-api/records/get-records/) .
- Message content is only used for delivery and is not stored or logged.
- All communication is done through kintone's official API endpoints.

## Data Storage

- No data is permanently stored by this plugin.
- Credentials are stored securely by the Dify platform.
- Message content is transmitted only and not retained.

## Third-party Services

- This plugin only interacts with kintone's official API service.
- No other third-party services are used.

## Security

- All communication with kintone API is done via HTTPS.
- Error messages are sanitized to prevent sensitive information leakage.

For any privacy concerns or questions, please contact the plugin author or raise an issue on the GitHub repository.
