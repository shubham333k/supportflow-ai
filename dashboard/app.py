"""
SupportFlow AI — Operations Console Home
"""

import streamlit as st

from dashboard.api_client import api
from dashboard.ui_components import load_custom_css, render_sidebar_status

st.set_page_config(
    page_title="SupportFlow AI — Ops Console",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_custom_css()
health = api.get_health()
render_sidebar_status(health)

st.markdown(
    """
    <div style="background: linear-gradient(90deg, #1D212C, #171A23); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 28px 32px; margin-bottom: 24px;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800; color: #F8FAFC;">
            SupportFlow <span style="background: linear-gradient(90deg, #6366F1, #38BDF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">AI</span>
        </h1>
        <p style="margin: 8px 0 0 0; font-size: 1.05rem; color: #94A3B8; max-width: 800px;">
            Autonomous Customer Support Triage, 7-Factor Escalation Scoring, pgvector RAG Knowledge Base & HubSpot CRM Sync.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Overview metrics ribbon
ov = api.get_analytics_overview()
c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Total Volume</div>
            <div class="metric-value">{ov.get('total_tickets', 0)}</div>
            <div class="metric-sub">All-time inbound</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Open Queue</div>
            <div class="metric-value">{ov.get('open_tickets', 0)}</div>
            <div class="metric-sub">Active triage</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Escalated (Immediate)</div>
            <div class="metric-value" style="color: #F87171;">{ov.get('escalated_tickets', 0)}</div>
            <div class="metric-sub">Senior attention</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">AI Resolved</div>
            <div class="metric-value" style="color: #34D399;">{ov.get('ai_resolved_tickets', 0)}</div>
            <div class="metric-sub">Autonomous deflection</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c5:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">SLA At Risk</div>
            <div class="metric-value" style="color: #FBBF24;">{ov.get('sla_at_risk_count', 0)}</div>
            <div class="metric-sub">>50% elapsed</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c6:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">Avg 1st Response</div>
            <div class="metric-value">{ov.get('avg_first_response_min', 0.0)}m</div>
            <div class="metric-sub">Inbound to reply</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# Quick navigation tiles
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown(
        """
        <div class="metric-card">
            <h3 style="margin-top:0; color:#F8FAFC;">📬 Live Triage & Human-in-the-Loop</h3>
            <p style="color:#CBD5E1; font-size:0.9rem;">
                Review incoming customer inquiries, inspect transparent 7-factor escalation scoring,
                evaluate cited RAG knowledge sources, and approve or edit AI drafts before sending.
            </p>
            <p style="color:#94A3B8; font-size:0.85rem;">
                👉 Open <b>Tickets</b> in the sidebar to access the approval workbench.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_right:
    st.markdown(
        """
        <div class="metric-card">
            <h3 style="margin-top:0; color:#F8FAFC;">📚 Knowledge Base & Semantic Search</h3>
            <p style="color:#CBD5E1; font-size:0.9rem;">
                Inspect indexed company support documentation, trigger automated heading-based chunking & embedding,
                and test semantic search with live cosine similarity scoring.
            </p>
            <p style="color:#94A3B8; font-size:0.85rem;">
                👉 Open <b>Knowledge Base</b> in the sidebar to test retrieval.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
