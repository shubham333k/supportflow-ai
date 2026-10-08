# Billing Cycles & Failed Payment Handling

## Billing Cycle Overview
SupportFlow supports both monthly and annual billing cycles:
- **Monthly subscriptions:** Automatically billed every 30 days starting on your sign-up date.
- **Annual subscriptions:** Billed once per calendar year with an automatic 20% discount applied to all user seats.

## Failed Payment Retry Schedule
If a scheduled renewal payment fails due to insufficient funds, an expired card, or bank security blocks:
1. **Day 1 (Immediate notification):** An automated notification email is dispatched with a secure link to update your payment method.
2. **Day 3 (Second retry):** Our billing gateway re-attempts the transaction automatically.
3. **Day 5 (Third retry):** A final attempt is made, accompanied by an urgent account warning.
4. **Day 7 (Grace period expiration):** If payment has not succeeded by Day 7, workspace access transitions to read-only status. Data is preserved for 60 days before archival.

## Updating Payment Methods
Account owners and billing admins can update credit card details anytime:
Navigate to **Settings > Billing > Payment Methods**, click **Add New Card**, enter valid credentials, and select **Set as Default**.
