"""
Settings Page — Service Health, Read-Only Escalation Weights & Hard Rule Manifest.
"""

from pathlib import Path

import streamlit as st
import yaml

from dashboard.api_client import api
from dashboard.ui_components import load_custom_css, render_sidebar_status

st.set_page_config(page_title="Settings — SupportFlow AI", page_icon="⚙️", layout="wide")
load_custom_css()
health = api.get_health()
render_sidebar_status(health)

st.title("⚙️ Engine Configuration & Health")
st.caption("Inspect live service dependencies, active scoring weights from escalation.yaml, and hard safety rules.")

# 1. Service Health Monitor
st.markdown("### ⚡ Live System Integrations")
c_db, c_llm, c_crm, c_n8n = st.columns(4)

with c_db:
    db_ok = health.get("db", False)
    db_status = "Connected" if db_ok else "In-Memory / SQLite"
    db_color = "#34D399" if db_ok else "#FBBF24"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Database & Vectors</div>
            <div class="metric-value" style="font-size:1.3rem; color:{db_color};">{db_status}</div>
            <div class="metric-sub">PostgreSQL + pgvector (768d)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c_llm:
    llm_ok = health.get("llm", False)
    llm_status = "Active" if llm_ok else "Mock / Configured"
    llm_color = "#34D399" if llm_ok else "#38BDF8"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">LLM & Embeddings</div>
            <div class="metric-value" style="font-size:1.3rem; color:{llm_color};">{llm_status}</div>
            <div class="metric-sub">Gemini 2.5 Flash / embedding-001</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c_crm:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-label">HubSpot CRM</div>
            <div class="metric-value" style="font-size:1.3rem; color:#6366F1;">Active Writer</div>
            <div class="metric-sub">Single writer (FastAPI) · ≤6 props</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c_n8n:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-label">Orchestrator</div>
            <div class="metric-value" style="font-size:1.3rem; color:#38BDF8;">n8n Ready</div>
            <div class="metric-sub">Webhook triggers & scheduling</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

# 2. Config-Driven Escalation Weights (Read-Only)
st.markdown("### 🎛️ Escalation Scoring Weights (`api/config/escalation.yaml`)")
st.caption("Deterministic weights driving the 0–100 triage score. Edits live strictly in git, never in Python code.")

config_path = Path("api/config/escalation.yaml")
if config_path.exists():
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        tab1, tab2, tab3 = st.tabs(["Factor Weights", "Tier Boundaries & SLAs", "Full YAML Source"])

        with tab1:
            weights = cfg.get("weights", {})
            w_col1, w_col2 = st.columns(2)

            with w_col1:
                st.markdown("##### 🚨 Urgency Points (Max 25)")
                st.json(weights.get("urgency", {}))

                st.markdown("##### 😠 Sentiment Points (Max 15)")
                st.json(weights.get("sentiment", {}))

                st.markdown("##### 💼 Customer Value Points (Max 10)")
                st.json(weights.get("customer_tier", {}))

            with w_col2:
                st.markdown("##### ⚡ Issue Severity Points (Max 20)")
                st.json(weights.get("issue", {}))

                st.markdown("##### 📜 Prior Unresolved Failure (Max 15)")
                st.json(weights.get("prior", {}))

                st.markdown("##### ⏱️ SLA Risk Factor (Max 10)")
                st.json(weights.get("sla", {}))

        with tab2:
            st.markdown("##### Priority Tier Thresholds & Deadlines")
            st.table(
                [
                    {"Tier": "Immediate", "Min Score": "≥ 80", "SLA Target": "1 Hour", "Routing": "Templated Ack + Slack Alert + Agent Draft"},
                    {"Tier": "Priority", "Min Score": "60–79", "SLA Target": "4 Hours", "Routing": "Ack Sent + Human Approval Queue in Dashboard"},
                    {"Tier": "AI Assisted", "Min Score": "30–59", "SLA Target": "24 Hours", "Routing": "Auto-send only if RAG Gate + Verifier pass"},
                    {"Tier": "Automated", "Min Score": "< 30", "SLA Target": "48 Hours", "Routing": "Auto-send answer + CSAT follow-up"},
                ]
            )

        with tab3:
            st.code(yaml.dump(cfg, sort_keys=False), language="yaml")

    except Exception as e:
        st.error(f"Error loading escalation.yaml: {e}")
else:
    st.warning("api/config/escalation.yaml not found.")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

# 3. Hard Safety Rules Reference
st.markdown("### 🛡️ Safety Hard-Rules Manifest")
st.caption("Hard rules override scores to enforce mandatory human review or instant escalation.")

rules_data = [
    {"Rule ID": "HR1", "Trigger Condition": "intent = security_issue OR security_signal", "Enforced Tier": "≥ immediate", "Rationale": "Zero-latency escalation for compromised credentials or attacks."},
    {"Rule ID": "HR2", "Trigger Condition": "intent ∈ {refund_request, billing_issue} OR legal_signal", "Enforced Tier": "≥ priority", "Rationale": "Financial disputes and legal threats must always have human oversight."},
    {"Rule ID": "HR3", "Trigger Condition": "requires_human = true", "Enforced Tier": "≥ priority", "Rationale": "Customer explicitly requested human agent or complex edge case."},
    {"Rule ID": "HR4", "Trigger Condition": "Classifier validation failure OR confidence < 0.5", "Enforced Tier": "≥ priority (needs_manual_review)", "Rationale": "Fail safe, never fail open. Ambiguous input routes to human."},
    {"Rule ID": "HR5", "Trigger Condition": "RAG similarity gate failed OR unanswerable", "Enforced Tier": "≥ priority (handoff)", "Rationale": "Never hallucinate unsupported company policy. Pass to specialist."},
    {"Rule ID": "HR6", "Trigger Condition": "Sender exceeded auto-reply cap (5 replies / 24h)", "Enforced Tier": "Human-only", "Rationale": "Loop guard preventing auto-reply ping-pong spirals."},
]

st.table(rules_data)
