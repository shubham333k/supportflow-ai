"""initial schema - 9 tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # customers
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text()),
        sa.Column("company", sa.Text()),
        sa.Column("tier", sa.Text(), nullable=False, server_default="standard"),
        sa.Column("ltv_cents", sa.Integer(), server_default="0"),
        sa.Column("crm_contact_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # tickets
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), unique=True),
        sa.Column("subject", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("intent", sa.Text()),
        sa.Column("sub_intent", sa.Text()),
        sa.Column("sentiment", sa.Text()),
        sa.Column("urgency", sa.Text()),
        sa.Column("priority_score", sa.Integer()),
        sa.Column("tier", sa.Text()),
        sa.Column("hard_rule_hits", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("assigned_to", sa.Text()),
        sa.Column("crm_ticket_id", sa.Text()),
        sa.Column("crm_sync_status", sa.Text(), server_default="pending"),
        sa.Column("needs_manual_review", sa.Boolean(), server_default="false"),
        sa.Column("reopened_count", sa.Integer(), server_default="0"),
        sa.Column("first_response_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("csat_due_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tickets_status_tier", "tickets", ["status", "tier"])
    op.create_index("ix_tickets_customer_created", "tickets", ["customer_id", "created_at"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("external_message_id", sa.Text(), unique=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("sender", sa.Text()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("ai_generated", sa.Boolean(), server_default="false"),
        sa.Column("approved_by", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_ticket_created", "messages", ["ticket_id", "created_at"])

    # ai_analyses
    op.create_table(
        "ai_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id")),
        sa.Column("model", sa.Text()),
        sa.Column("prompt_version", sa.Text()),
        sa.Column("analysis", postgresql.JSONB(), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("tier", sa.Text()),
        sa.Column("score_breakdown", postgresql.JSONB()),
        sa.Column("hard_rule_hits", postgresql.ARRAY(sa.Text())),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # drafts
    op.create_table(
        "drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("reply", sa.Text()),
        sa.Column("sources", postgresql.JSONB()),
        sa.Column("top_similarity", sa.Float()),
        sa.Column("answerable", sa.Boolean()),
        sa.Column("verifier_passed", sa.Boolean()),
        sa.Column("send_mode", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # kb_documents
    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("filename", sa.Text(), unique=True, nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("doc_type", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("content_hash", sa.Text()),
        sa.Column("chunk_count", sa.Integer()),
        sa.Column("status", sa.Text(), server_default="ready"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # kb_chunks
    op.create_table(
        "kb_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_documents.id", ondelete="CASCADE")),
        sa.Column("chunk_index", sa.Integer()),
        sa.Column("heading_path", sa.Text()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
    )

    # sla_timers
    op.create_table(
        "sla_timers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("tier", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warned_50_at", sa.DateTime(timezone=True)),
        sa.Column("warned_90_at", sa.DateTime(timezone=True)),
        sa.Column("breached_at", sa.DateTime(timezone=True)),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_sla_timers_due_active", "sla_timers", ["due_at"],
        postgresql_where=sa.text("stopped_at IS NULL"),
    )

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id")),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text()),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("n8n_execution_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_events_ticket_created", "audit_events", ["ticket_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("sla_timers")
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("drafts")
    op.drop_table("ai_analyses")
    op.drop_table("messages")
    op.drop_table("tickets")
    op.drop_table("customers")
    op.execute("DROP EXTENSION IF EXISTS vector")
