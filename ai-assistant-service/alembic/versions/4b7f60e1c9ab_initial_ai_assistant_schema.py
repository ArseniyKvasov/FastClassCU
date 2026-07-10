"""initial ai assistant schema

Revision ID: 4b7f60e1c9ab
Revises: 
Create Date: 2026-07-09 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4b7f60e1c9ab"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_assistant_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_assistant_events_event_type"), "ai_assistant_events", ["event_type"], unique=False)

    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generation_jobs_intent"), "generation_jobs", ["intent"], unique=False)
    op.create_index(op.f("ix_generation_jobs_requester_id"), "generation_jobs", ["requester_id"], unique=False)
    op.create_index(op.f("ix_generation_jobs_status"), "generation_jobs", ["status"], unique=False)

    op.create_table(
        "memory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_items_kind"), "memory_items", ["kind"], unique=False)
    op.create_index(op.f("ix_memory_items_user_id"), "memory_items", ["user_id"], unique=False)

    op.create_table(
        "style_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_lesson_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "generation_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("content_service_file_id", sa.Uuid(), nullable=True),
        sa.Column("lesson_id", sa.Uuid(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generation_artifacts_job_id"), "generation_artifacts", ["job_id"], unique=False)

    op.create_table(
        "provider_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_calls_job_id"), "provider_calls", ["job_id"], unique=False)
    op.create_index(op.f("ix_provider_calls_provider_name"), "provider_calls", ["provider_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_assistant_events_event_type"), table_name="ai_assistant_events")
    op.drop_table("ai_assistant_events")
    op.drop_index(op.f("ix_provider_calls_provider_name"), table_name="provider_calls")
    op.drop_index(op.f("ix_provider_calls_job_id"), table_name="provider_calls")
    op.drop_table("provider_calls")
    op.drop_index(op.f("ix_generation_artifacts_job_id"), table_name="generation_artifacts")
    op.drop_table("generation_artifacts")
    op.drop_table("style_profiles")
    op.drop_index(op.f("ix_memory_items_user_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_kind"), table_name="memory_items")
    op.drop_table("memory_items")
    op.drop_index(op.f("ix_generation_jobs_status"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_requester_id"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_intent"), table_name="generation_jobs")
    op.drop_table("generation_jobs")
