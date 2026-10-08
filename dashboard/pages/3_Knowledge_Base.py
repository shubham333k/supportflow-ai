"""
Knowledge Base Page — Document Inventory, Ingestion Pipeline & Semantic Retrieval Sandbox.
"""

import pandas as pd
import streamlit as st

from dashboard.api_client import api
from dashboard.ui_components import load_custom_css, render_sidebar_status

st.set_page_config(page_title="Knowledge Base — SupportFlow AI", page_icon="📚", layout="wide")
load_custom_css()
health = api.get_health()
render_sidebar_status(health)

col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.title("📚 Knowledge Base & Retrieval")
    st.caption("Manage markdown knowledge corpus, heading-based vector chunks, and test cosine semantic search.")
with col_h2:
    if st.button("🔄 Trigger Ingestion", use_container_width=True):
        with st.spinner("Indexing markdown corpus and generating 768-dim embeddings..."):
            try:
                res = api.trigger_kb_ingest()
                st.success(f"Ingested {res.get('indexed_files', 0)} files ({res.get('total_chunks', 0)} chunks)!")
                st.rerun()
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

st.markdown("---")

# 1. Document Inventory
st.markdown("### 📑 Indexed Document Library")
docs = api.get_kb_documents()

if docs:
    rows = []
    total_chunks = 0
    for d in docs:
        total_chunks += d.get("chunk_count", 0)
        rows.append(
            {
                "Filename": d.get("filename"),
                "Title": d.get("title") or "Untitled",
                "Type": d.get("doc_type", "policy"),
                "Version": f"v{d.get('version', 1)}",
                "Chunks": d.get("chunk_count", 0),
                "Status": (d.get("status") or "ready").upper(),
                "Last Updated": (d.get("updated_at") or "")[:19].replace("T", " "),
            }
        )

    # Summary cards
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Corpus Documents</div><div class="metric-value">{len(docs)}</div><div class="metric-sub">Markdown policy files</div></div>',
            unsafe_allow_html=True,
        )
    with sc2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Vector Chunks</div><div class="metric-value" style="color:#6366F1;">{total_chunks}</div><div class="metric-sub">H2/H3 semantic segments</div></div>',
            unsafe_allow_html=True,
        )
    with sc3:
        st.markdown(
            '<div class="metric-card"><div class="metric-label">Embedding Model</div><div class="metric-value" style="font-size:1.4rem; color:#38BDF8;">gemini-embedding-001</div><div class="metric-sub">768 dimensions, L2 normalized</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    df_docs = pd.DataFrame(rows)
    st.dataframe(
        df_docs,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Filename": st.column_config.TextColumn("File Path", width="medium"),
            "Title": st.column_config.TextColumn("Document Title", width="large"),
            "Chunks": st.column_config.NumberColumn("Chunks", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Last Updated": st.column_config.TextColumn("Updated", width="medium"),
        },
    )
else:
    st.info("No documents currently indexed. Click 'Trigger Ingestion' above to index the 12 seed markdown files.")

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

# 2. Semantic Search Sandbox
st.markdown("### 🔍 Semantic Retrieval Sandbox")
st.caption("Test how the RAG retriever matches customer inquiries against knowledge base chunks.")

query = st.text_input(
    "Enter a test question or customer message:",
    value="How does your 14-day refund policy work for annual subscriptions?",
)

if query:
    with st.spinner("Embedding query and executing cosine distance search..."):
        results = api.search_kb(query, limit=4)

    if results:
        st.markdown(f"##### Top {len(results)} Retrieved Passages")
        for i, r in enumerate(results, 1):
            sim = r.get("similarity", 0.0)
            sim_pct = round(sim * 100, 1)
            color = "#10B981" if sim_pct >= 60 else "#F59E0B" if sim_pct >= 40 else "#EF4444"

            st.markdown(
                f"""
                <div class="kb-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span class="kb-title">#{i} {r.get('document_title') or r.get('doc') or 'Document'}</span>
                        <span style="font-family:'JetBrains Mono'; font-weight:700; color:{color}; font-size:0.9rem;">Cosine Match: {sim_pct}%</span>
                    </div>
                    <div class="kb-meta">Heading Path: <code>{r.get('heading_path') or r.get('heading') or 'root'}</code></div>
                    <div class="kb-snippet" style="background:rgba(0,0,0,0.25); padding:10px 12px; border-radius:6px; margin-top:8px;">
                        {r.get('content', '')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No matching chunks found above the similarity threshold.")
