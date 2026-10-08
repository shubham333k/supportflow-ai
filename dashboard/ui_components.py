"""
Shared UI components and styling utilities for SupportFlow AI dashboard.
"""

from pathlib import Path

import streamlit as st


def load_custom_css():
    """Load the design system CSS."""
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_sidebar_status(api_health: dict):
    """Render consistent branding and live system status in the sidebar."""
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 10px 0 20px 0;">
                <h3 style="margin:0; font-weight:700; color:#F8FAFC; display:flex; align-items:center; gap:8px;">
                    <span>🛡️</span> SupportFlow <span style="color:#6366F1;">AI</span>
                </h3>
                <p style="margin:4px 0 0 0; font-size:0.75rem; color:#94A3B8;">Ops Console & Triage Engine</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("##### ⚡ Service Status")

        status_color = "#34D399" if api_health.get("status") == "healthy" or api_health.get("ok") else "#EF4444"
        status_text = "Online" if api_health.get("status") != "offline" else "Offline"

        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span style="height:9px; width:9px; background-color:{status_color}; border-radius:50%; display:inline-block; box-shadow:0 0 8px {status_color};"></span>
                <span style="font-size:0.85rem; font-weight:600; color:#F8FAFC;">API Backend: {status_text}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        db_ok = api_health.get("db", False)
        llm_ok = api_health.get("llm", False)
        st.caption(f"DB (pgvector): {'🟢 Connected' if db_ok else '🟡 SQLite/Mock'}")
        st.caption(f"LLM (Gemini): {'🟢 Active' if llm_ok else '🟡 Configured'}")
        st.markdown("---")


def format_tier_badge(tier: str | None) -> str:
    """Return HTML badge for priority tier."""
    t = (tier or "unknown").lower()
    return f'<span class="tier-badge tier-{t}">{t}</span>'


def format_status_badge(status: str | None) -> str:
    """Return HTML badge for ticket status."""
    s = (status or "new").lower()
    return f'<span class="status-badge status-{s}">{s}</span>'


def render_score_breakdown(breakdown: dict, total_score: int, tier: str, hard_rule_hits: list[str]):
    """Render the 7-factor horizontal progress bars and hard rule chips."""
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div style="font-size:1.1rem; font-weight:700;">
                Escalation Score: <span style="color:#6366F1; font-family:'JetBrains Mono'; font-size:1.3rem;">{total_score}/100</span>
            </div>
            <div>{format_tier_badge(tier)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if hard_rule_hits:
        if isinstance(hard_rule_hits, str):
            import json, ast
            try:
                parsed_hits = json.loads(hard_rule_hits)
            except Exception:
                try:
                    parsed_hits = ast.literal_eval(hard_rule_hits)
                except Exception:
                    parsed_hits = [hard_rule_hits]
            hard_rule_hits = parsed_hits if isinstance(parsed_hits, list) else [str(parsed_hits)]

        st.markdown("##### 🚨 Hard-Rule Overrides Triggered")
        chips = "".join([f'<span class="rule-pill">⚠️ {hit}</span>' for hit in hard_rule_hits if hit])
        st.markdown(f'<div style="margin-bottom:14px;">{chips}</div>', unsafe_allow_html=True)

    factor_limits = {
        "urgency": ("Urgency", 25),
        "sentiment": ("Sentiment", 15),
        "customer": ("Customer Tier", 10),
        "issue": ("Issue Severity", 20),
        "prior_failed": ("Prior Unresolved History", 15),
        "sla_risk": ("SLA Exposure Risk", 10),
        "threat": ("Churn / Legal Threat", 5),
    }

    for key, (label, max_val) in factor_limits.items():
        pts = breakdown.get(key, 0)
        pct = min(100, int((pts / max_val) * 100)) if max_val > 0 else 0
        st.markdown(
            f"""
            <div class="factor-row">
                <div class="factor-header">
                    <span class="factor-name">{label}</span>
                    <span class="factor-pts">{pts} / {max_val} pts</span>
                </div>
                <div class="progress-bg">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
