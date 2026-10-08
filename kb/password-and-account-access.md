# Password and Account Access Procedures

## Password Reset Workflow
If you forget your account password:
1. Navigate to the login page at `https://app.supportflow.ai/login`.
2. Click **Forgot Password?** below the login form.
3. Enter your registered work email address.
4. Check your inbox for a secure one-time password reset link (valid for 15 minutes).
5. Enter a new password containing at least 12 characters, including one uppercase letter, one number, and one special symbol.

## Two-Factor Authentication (2FA) Recovery
SupportFlow enforces TOTP-based two-factor authentication (Authenticator apps like Google Authenticator or 1Password):
- **Recovery Codes:** When enabling 2FA, you received 10 emergency recovery codes. If you lost access to your device, enter any unused recovery code at login.
- **Lost Recovery Codes:** If you have lost both your 2FA device and your recovery codes, an organization Workspace Admin must reset your 2FA status from **Settings > Team Management > Users**.

## Account Lockout Policy
To prevent brute-force attacks, accounts are automatically locked after 10 consecutive failed password attempts. The lockout lasts for 30 minutes, after which you can re-attempt login or initiate a password reset.
