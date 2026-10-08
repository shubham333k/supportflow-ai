# Spike C: Gmail Trigger & OAuth Lifetime Verification

## 1. The OAuth 7-Day Expiry Problem
When configuring Google Cloud OAuth 2.0 Client credentials:
- If your Google Cloud OAuth Consent Screen is in **"Testing"** publishing status, refresh tokens automatically expire after **7 days**.
- When tokens expire, n8n's Gmail Trigger polling silently halts with `400 invalid_grant: Token has been expired or revoked`.

## 2. Recommended Resolutions

### Option A: Set Consent Screen to "In Production" (Personal / External)
1. Go to Google Cloud Console → **APIs & Services** → **OAuth consent screen**.
2. Click **Publish App** to switch status from *Testing* to *In Production*.
3. Even without undergoing Google verification, an unverified production app allows personal accounts or a dedicated test account to maintain persistent refresh tokens that do not expire after 7 days.

### Option B: IMAP / SMTP with Google App Password (Fastest & Most Reliable for Dev)
If OAuth verification or app publishing is undesirable:
1. Enable 2-Step Verification on the dedicated support Gmail account.
2. Go to **Security** → **App passwords**.
3. Generate an App Password for "Mail".
4. In n8n, use the **Email Read (IMAP)** node instead of the OAuth Gmail node:
   - Host: `imap.gmail.com`
   - Port: `993` (SSL/TLS)
   - User: `your-support-bot@gmail.com`
   - Password: `<16-character-app-password>`
5. This credential never expires automatically and avoids OAuth consent popups.

## 3. n8n Gmail Node Configuration
- Filter: `label:support is:unread`
- Download Attachments: False (V1 scope)
- Poll interval: 1 minute
- Idempotency guard: Map `id` / `threadId` to `external_message_id` and `thread_id` in the API payload.
