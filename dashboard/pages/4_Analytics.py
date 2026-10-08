"""
Analytics Page — Inbound Distributions, Deflection Rates, Escalation Trends & CRM Health.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import api
from dashboard.ui_components import load_custom_css, render_sidebar_status

st.set_page_config(page_title="Analytics — SupportFlow AI", page_icon="📈", layout="wide")
load_custom_css()
health = api.get_health()
render_sidebar_status(health)

col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.title("📈 Performance & Analytics")
    st.caption("Taxonomy distribution, AI deflection rates, escalation frequency, and SLA compliance metrics.")
with col_h2:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

trends = api.get_analytics_trends()

# 1. Headline Rate Metrics
m1, m2, m3, m4 = st.columns(4)

with m1:
    esc_rate = trends.get("escalation_rate_pct", 0.0)
    color = "#F87171" if esc_rate > 50 else "#38BDF8"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Escalation Rate</div>
            <div class="metric-value" style="color:{color};">{esc_rate}%</div>
            <div class="metric-sub">Immediate + Priority Tiers</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m2:
    ai_rate = trends.get("ai_resolution_rate_pct", 0.0)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">AI Deflection Rate</div>
            <div class="metric-value" style="color:#34D399;">{ai_rate}%</div>
            <div class="metric-sub">Auto-resolved without handoff</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m3:
    sla_breach = trends.get("sla_breach_rate_pct", 0.0)
    sla_comp = round(100.0 - sla_breach, 1)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">SLA Compliance</div>
            <div class="metric-value" style="color:#38BDF8;">{sla_comp}%</div>
            <div class="metric-sub">{sla_breach}% breach rate</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with m4:
    crm_rate = trends.get("crm_sync_success_rate_pct", 100.0)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">HubSpot Sync Health</div>
            <div class="metric-value" style="color:#6366F1;">{crm_rate}%</div>
            <div class="metric-sub">Contact & Ticket sync success</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# 2. Charts: Intent Distribution & Sentiment Breakdown
ch_c1, ch_c2 = st.columns([1.2, 0.8])

with ch_c1:
    st.markdown("##### 🏷️ Intent Taxonomy Distribution (12 Fixed Labels)")
    intent_dist = trends.get("intent_distribution", {})
    if intent_dist:
        df_intent = pd.DataFrame(
            [{"Intent": k.replace("_", " ").title(), "Count": v} for k, v in intent_dist.items()]
        ).sort_values(by="Count", ascending=True)

        fig_intent = px.bar(
            df_intent,
            x="Count",
            y="Intent",
            orientation="h",
            color="Count",
            color_continuous_scale=["#6366F1", "#38BDF8"],
        )
        fig_intent.update_layout(
            paper_bgcolor="#1D212C",
            plot_bgcolor="#1D212C",
            font_color="#F8FAFC",
            margin=dict(t=20, b=20, l=20, r=20),
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_intent, use_container_width=True)
    else:
        st.info("No intent records available yet.")

with ch_c2:
    st.markdown("##### 😊 Customer Sentiment Breakdown")
    sentiment_dist = trends.get("sentiment_distribution", {})
    if sentiment_dist:
        df_sent = pd.DataFrame(
            [{"Sentiment": k.title(), "Count": v} for k, v in sentiment_dist.items()]
        )
        sent_colors = {
            "Positive": "#10B981",
            "Neutral": "#94A3B8",
            "Negative": "#F59E0B",
            "Frustrated": "#FB923C",
            "Angry": "#EF4444",
        }
        fig_sent = px.pie(
            df_sent,
            values="Count",
            names="Sentiment",
            color="Sentiment",
            color_discrete_map=sent_colors,
            hole=0.55,
        )
        fig_sent.update_layout(
            paper_bgcolor="#1D212C",
            plot_bgcolor="#1D212C",
            font_color="#F8FAFC",
            margin=dict(t=20, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig_sent, use_container_width=True)
    else:
        st.info("No sentiment records available yet.")
