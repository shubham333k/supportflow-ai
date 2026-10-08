"""
Tickets Page — Human-in-the-Loop Triage, Transparent Escalation & Approval Workbench.
"""

from datetime import UTC, datetime

import streamlit as st

from dashboard.api_client import api
from dashboard.ui_components import (
    format_status_badge,
    format_tier_badge,
    load_custom_css,
    render_score_breakdown,
    render_sidebar_status,
)

st.set_page_config(page_title="Tickets — SupportFlow AI", page_icon="📬", layout="wide")
load_custom_css()
health = api.get_health()
render_sidebar_status(health)

st.title("📬 Triage & Approval Workbench")
st.caption("Inspect AI classification, escalation score factors, cited knowledge sources, and approve replies.")

# 1. Filter Ribbon
f_c1, f_c2, f_c3, f_c4 = st.columns([1, 1, 1.2, 0.8])
with f_c1:
    tier_filter = st.selectbox(
        "Priority Tier",
        ["all", "immediate", "priority", "ai_assisted", "automated"],
        index=0,
    )
with f_c2:
    status_filter = st.selectbox(
        "Status",
        ["all", "pending_approval", "escalated", "new", "waiting_customer", "resolved", "closed"],
        index=0,
    )
with f_c3:
    intent_filter = st.selectbox(
        "Intent",
        [
            "all",
            "billing_issue",
            "refund_request",
            "account_access",
            "subscription_change",
            "technical_issue",
            "product_question",
            "feature_request",
            "complaint",
            "sales_question",
            "security_issue",
            "general_question",
            "other",
        ],
        index=0,
    )
with f_c4:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# 2. Fetch Tickets Matching Filters
tickets = api.get_tickets(tier=tier_filter, status=status_filter, intent=intent_filter, limit=50)

if not tickets:
    st.info("No tickets match the selected filters.")
    st.stop()

# 3. Ticket Selector
ticket_options = {
    str(t["id"]): f"[{(t.get('tier') or 'unclassified').upper()}] {t.get('subject') or 'No Subject'} — {t.get('status') or 'open'} ({str(t['id'])[:8]})"
    for t in tickets
}

selected_id = st.selectbox(
    "Select a Ticket to Review:",
    options=list(ticket_options.keys()),
    format_func=lambda x: ticket_options[x],
)

if not selected_id:
    st.stop()

# 4. Fetch Deep Enriched Ticket Detail
detail = api.get_ticket_detail(selected_id)
if not detail:
    st.error(f"Could not load details for ticket {selected_id}")
    st.stop()

customer = detail.get("customer") or {}
analysis = detail.get("latest_analysis") or {}
draft = detail.get("latest_draft") or {}
sla = detail.get("sla_timer") or {}
messages = detail.get("messages") or []

st.markdown("---")

# 5. Ticket Header & Customer Profile
h_col1, h_col2 = st.columns([3, 1])

with h_col1:
    st.markdown(f"### {detail.get('subject') or 'No Subject'}")
    c_name = customer.get("name") or "Unknown Customer"
    c_email = customer.get("email") or "No email"
    c_tier = (customer.get("tier") or "standard").upper()
    c_id = customer.get("crm_contact_id") or "Pending CRM sync"
    st.markdown(
        f"""
        <div style="display:flex; gap:16px; align-items:center; color:#CBD5E1; font-size:0.9rem; margin-top:4px;">
            <span>👤 <b>{c_name}</b> ({c_email})</span>
            <span>🏷️ CRM Tier: <b>{c_tier}</b></span>
            <span>🔗 HubSpot Contact: <code>{c_id}</code></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with h_col2:
    st.markdown(
        f"""
        <div style="text-align:right;">
            <div>{format_tier_badge(detail.get('tier'))}</div>
            <div style="margin-top:6px;">{format_status_badge(detail.get('status'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# 6. Two-Column Layout: Left (Thread & AI Draft) | Right (Scorecard, SLA, Sources)
col_left, col_right = st.columns([1.1, 0.9])

with col_left:
    # ── Conversation Thread ──
    st.markdown("#### 💬 Conversation Thread")
    if messages:
        for m in messages:
            direction = m.get("direction", "inbound")
            sender = m.get("sender") or ("Customer" if direction == "inbound" else "SupportFlow AI")
            created_at = (m.get("created_at") or "")[:19].replace("T", " ")
            css_class = "msg-inbound" if direction == "inbound" else "msg-outbound"
            badge = "📥 Inbound Message" if direction == "inbound" else "📤 Outbound Reply"

            st.markdown(
                f"""
                <div class="{css_class}">
                    <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:0.75rem; color:#94A3B8;">
                        <b>{badge} — {sender}</b>
                        <span>{created_at}</span>
                    </div>
                    <div style="white-space: pre-wrap; font-size:0.88rem; line-height:1.5;">{m.get("body", "")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No message records found.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── AI Suggested Draft & Human Approval ──
    st.markdown("#### ✍️ AI Suggested Draft & Human Approval")
    if draft:
        send_mode = draft.get("send_mode", "approval")
        verifier_ok = draft.get("verifier_passed", False)
        answerable = draft.get("answerable", False)

        badge_color = "#34D399" if verifier_ok else "#FBBF24"
        verif_label = "✅ Grounded & Verified" if verifier_ok else "⚠️ Needs Review / Handoff"

        st.markdown(
            f"""
            <div style="display:flex; gap:12px; margin-bottom:10px; font-size:0.8rem;">
                <span style="background:rgba(99,102,241,0.2); color:#818CF8; padding:3px 8px; border-radius:4px;">Mode: <b>{(send_mode or 'approval').upper()}</b></span>
                <span style="background:rgba(255,255,255,0.06); color:{badge_color}; padding:3px 8px; border-radius:4px;">{verif_label}</span>
                <span style="background:rgba(255,255,255,0.06); color:#CBD5E1; padding:3px 8px; border-radius:4px;">Status: <b>{draft.get('status', 'pending')}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        reply_content = draft.get("reply") or "No suggested reply available (Handoff mode triggered)."

        edited_reply = st.text_area(
            "Draft Content (Edit before sending):",
            value=reply_content,
            height=180,
            key=f"draft_{selected_id}",
        )

        btn_c1, btn_c2, btn_c3 = st.columns([1.2, 1, 1])
        with btn_c1:
            if st.button("🟢 Approve & Send Reply", use_container_width=True, key=f"appr_{selected_id}"):
                with st.spinner("Recording approval and sending reply..."):
                    try:
                        res_app = api.approve_draft(selected_id, edited_body=edited_reply)
                        st.success("Draft approved and sent successfully!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Approval failed: {ex}")

        with btn_c2:
            if st.button("🟡 Escalate Ticket", use_container_width=True, key=f"esc_{selected_id}"):
                with st.spinner("Escalating to Immediate tier..."):
                    try:
                        api.escalate_ticket(selected_id, reason="dashboard_manual")
                        st.warning("Ticket escalated to Immediate tier!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Escalation failed: {ex}")

        with btn_c3:
            if st.button("🔵 Mark Resolved", use_container_width=True, key=f"res_{selected_id}"):
                with st.spinner("Resolving ticket..."):
                    try:
                        api.resolve_ticket(selected_id)
                        st.info("Ticket marked as resolved.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Resolve failed: {ex}")
    else:
        st.info("No AI draft has been generated for this ticket yet.")
        if st.button("⚡ Generate AI Draft Now", key=f"gen_{selected_id}"):
            with st.spinner("Running RAG retrieval and drafting..."):
                try:
                    api.trigger_draft(selected_id)
                    st.success("Draft generated!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Draft generation failed: {ex}")

with col_right:
    # ── SLA Countdown Timer ──
    st.markdown("#### ⏱️ SLA Countdown")
    if sla and sla.get("due_at"):
        due_str = sla.get("due_at", "")
        # Parse due date
        try:
            due_clean = due_str.replace("Z", "+00:00")
            due_dt = datetime.fromisoformat(due_clean)
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=UTC)
            now_dt = datetime.now(UTC)
            remaining_seconds = int((due_dt - now_dt).total_seconds())

            if sla.get("stopped_at"):
                timer_display = "RESOLVED / STOPPED"
                timer_color = "#34D399"
                sub_status = "SLA timer stopped"
            elif remaining_seconds <= 0:
                timer_display = "BREACHED"
                timer_color = "#EF4444"
                sub_status = f"Breached by {abs(remaining_seconds) // 60}m"
            else:
                hrs = remaining_seconds // 3600
                mins = (remaining_seconds % 3600) // 60
                secs = remaining_seconds % 60
                timer_display = f"{hrs:02d}h {mins:02d}m {secs:02d}s"
                timer_color = "#F59E0B" if remaining_seconds < 1800 else "#38BDF8"
                sub_status = f"Target tier: {(sla.get('tier') or 'standard').upper()}"
        except Exception:
            timer_display = "Active"
            timer_color = "#38BDF8"
            sub_status = "Timer running"

        st.markdown(
            f"""
            <div class="sla-box">
                <div class="metric-label">Time Remaining</div>
                <div class="sla-timer-text" style="color:{timer_color};">{timer_display}</div>
                <div class="metric-sub">{sub_status}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("No active SLA timer configured.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Transparent Escalation Breakdown ──
    st.markdown("#### 🎯 Escalation Engine Breakdown")
    if analysis:
        breakdown = analysis.get("score_breakdown") or {}
        score = analysis.get("score", 0)
        tier = analysis.get("tier", "automated")
        rules = analysis.get("hard_rule_hits") or []

        render_score_breakdown(breakdown, score, tier, rules)

        with st.expander("🔍 Raw Classifier Analysis", expanded=False):
            st.json(analysis.get("analysis", {}))
    else:
        st.info("No AI analysis record found for this ticket.")
        if st.button("⚡ Run AI Analysis Now", key=f"run_an_{selected_id}"):
            with st.spinner("Analyzing message..."):
                try:
                    api.trigger_analyze(selected_id)
                    st.success("Analysis complete!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Analysis failed: {ex}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Grounded Knowledge Sources ──
    st.markdown("#### 📖 Cited Knowledge Sources")
    sources = draft.get("sources") or []
    if sources:
        for idx, src in enumerate(sources, 1):
            doc = src.get("doc") or src.get("title") or "Article"
            heading = src.get("heading") or src.get("heading_path") or "Section"
            sim = src.get("similarity", 0.0)
            sim_pct = round(sim * 100, 1) if sim else 0.0

            st.markdown(
                f"""
                <div class="kb-card">
                    <div class="kb-title">[{idx}] {doc}</div>
                    <div class="kb-meta">Heading: <code>{heading}</code> · Cosine Match: <b style="color:#38BDF8;">{sim_pct}%</b></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("No external knowledge sources cited.")
