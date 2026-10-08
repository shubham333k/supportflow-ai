"""
Overview Page — Executive KPI dashboard and operational queues.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import api
from dashboard.ui_components import load_custom_css, render_sidebar_status

st.set_page_config(page_title="Overview — SupportFlow AI", page_icon="📊", layout="wide")
load_custom_css()
health = api.get_health()
render_sidebar_status(health)

col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.title("📊 Operations Overview")
    st.caption("Live operational metrics, queue health, and priority distribution")
with col_h2:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# 1. KPI Cards Ribbon
ov = api.get_analytics_overview()
c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Total Volume</div><div class="metric-value">{ov.get("total_tickets", 0)}</div><div class="metric-sub">Inbound tickets</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Open Queue</div><div class="metric-value">{ov.get("open_tickets", 0)}</div><div class="metric-sub">Pending resolution</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Immediate Tier</div><div class="metric-value" style="color:#F87171;">{ov.get("escalated_tickets", 0)}</div><div class="metric-sub">1h SLA deadline</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">AI Resolved</div><div class="metric-value" style="color:#34D399;">{ov.get("ai_resolved_tickets", 0)}</div><div class="metric-sub">Automated handling</div></div>',
        unsafe_allow_html=True,
    )
with c5:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">SLA At Risk</div><div class="metric-value" style="color:#FBBF24;">{ov.get("sla_at_risk_count", 0)}</div><div class="metric-sub">>50% deadline</div></div>',
        unsafe_allow_html=True,
    )
with c6:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Avg 1st Response</div><div class="metric-value">{ov.get("avg_first_response_min", 0.0)}m</div><div class="metric-sub">Time to contact</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# 2. Charts: Priority Tiers and Status Breakdown
trends = api.get_analytics_trends()
col_ch1, col_ch2 = st.columns([1, 1])

with col_ch1:
    st.markdown("##### 🎯 Priority Tier Distribution")
    tier_dist = trends.get("tier_distribution", {})
    if tier_dist:
        df_tier = pd.DataFrame(
            [{"Tier": k, "Count": v} for k, v in tier_dist.items()]
        )
        color_map = {
            "immediate": "#EF4444",
            "priority": "#F59E0B",
            "ai_assisted": "#38BDF8",
            "automated": "#10B981",
        }
        fig_tier = px.pie(
            df_tier,
            values="Count",
            names="Tier",
            hole=0.6,
            color="Tier",
            color_discrete_map=color_map,
        )
        fig_tier.update_layout(
            paper_bgcolor="#1D212C",
            plot_bgcolor="#1D212C",
            font_color="#F8FAFC",
            margin=dict(t=20, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig_tier, use_container_width=True)
    else:
        st.info("No tickets classified yet.")

with col_ch2:
    st.markdown("##### 📋 Ticket Status Breakdown")
    status_dist = trends.get("status_distribution", {})
    if status_dist:
        df_status = pd.DataFrame(
            [{"Status": k, "Tickets": v} for k, v in status_dist.items()]
        )
        fig_status = px.bar(
            df_status,
            x="Status",
            y="Tickets",
            color="Status",
            color_discrete_sequence=["#6366F1", "#38BDF8", "#F59E0B", "#10B981", "#EF4444"],
        )
        fig_status.update_layout(
            paper_bgcolor="#1D212C",
            plot_bgcolor="#1D212C",
            font_color="#F8FAFC",
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
        )
        st.plotly_chart(fig_status, use_container_width=True)
    else:
        st.info("No status records yet.")

st.markdown("<br>", unsafe_allow_html=True)

# 3. Active Tickets Table
st.markdown("### 📥 Recent Inbound Tickets")
tickets = api.get_tickets(limit=15)

if tickets:
    rows = []
    for t in tickets:
        rows.append(
            {
                "ID": str(t.get("id"))[:8],
                "Subject": t.get("subject") or "No Subject",
                "Tier": t.get("tier") or "unclassified",
                "Status": t.get("status") or "new",
                "Intent": t.get("intent") or "pending",
                "Score": t.get("priority_score", "-"),
                "Channel": t.get("channel", "email"),
                "Created": t.get("created_at", "")[:19].replace("T", " "),
            }
        )
    df_t = pd.DataFrame(rows)
    st.dataframe(
        df_t,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("Ticket ID", width="small"),
            "Subject": st.column_config.TextColumn("Subject", width="large"),
            "Tier": st.column_config.TextColumn("Priority Tier", width="medium"),
            "Status": st.column_config.TextColumn("Lifecycle Status", width="medium"),
            "Score": st.column_config.NumberColumn("Score /100", width="small"),
            "Created": st.column_config.TextColumn("Received", width="medium"),
        },
    )
else:
    st.info("No inbound tickets currently in the database.")
