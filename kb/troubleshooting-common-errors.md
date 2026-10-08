# Troubleshooting Common Errors & System Codes

## Error Code Reference
Below are the most frequent system error codes encountered in SupportFlow and their resolution paths:

### ERR_RATE_LIMITED (HTTP 429)
- **Cause:** Your application or API integration has exceeded the requests-per-minute quota allocated to your subscription tier.
- **Resolution:** Inspect the `Retry-After` HTTP response header. Implement exponential backoff in your client library. Consider upgrading to Pro or Enterprise if higher sustained throughput is required.

### ERR_CSV_PARSE (File Ingestion Error)
- **Cause:** An uploaded CSV file contains invalid characters, non-UTF-8 encoding, or mismatched column delimiters (such as semicolons instead of commas).
- **Resolution:** Re-save your spreadsheet exported as standard UTF-8 CSV with comma separation. Verify that column headers match the expected template schema.

### ERR_SYNC_FAILED (CRM Integration Disconnect)
- **Cause:** Your HubSpot OAuth connection or API token has expired or had its permission scopes revoked.
- **Resolution:** Navigate to **Settings > Integrations > HubSpot** and click **Reconnect**. Ensure your account role possesses Super Admin privileges in HubSpot to authorize custom property creation.
