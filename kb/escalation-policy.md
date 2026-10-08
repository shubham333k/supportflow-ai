# Incident Escalation Policy & Criteria

## Escalation Triggers
Tickets are routed to human escalation queues through either deterministic scoring or safety hard rules:
- **Priority Score Escalation:** Any ticket scoring ≥80 points is flagged as an `immediate` escalation, triggering an instant Slack ping with an explanation breakdown.
- **Security Escalations (Rule HR1):** Any reported unauthorized account access, compromised API keys, or security vulnerability report bypasses normal queues and escalates directly to the Security Engineering Team.
- **Financial Disputes (Rule HR2):** All refund requests and disputed billing charges require human verification before funds or credits are issued.

## Multi-Tier Escalation Levels
SupportFlow maintains a structured engineering hierarchy:
1. **Tier 1 (Automated / Support Ops):** AI-assisted triage, initial troubleshooting, and knowledge base routing.
2. **Tier 2 (Senior Support Engineers):** Bug reproduction, complex webhook configurations, and database query inspections.
3. **Tier 3 (Platform Engineering & Security Leads):** Infrastructure outages, live data recovery, and vulnerability mitigation.

## Customer Escalation Requests
Customers may request formal manager review by replying with "Request Escalation" or contacting their dedicated customer success manager.
