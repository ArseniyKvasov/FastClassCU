"""initial analytics schema

Revision ID: 5f8f0d55f4a1
Revises:
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5f8f0d55f4a1"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("producer", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analytics_events_event_id"), "analytics_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_analytics_events_event_type"), "analytics_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_analytics_events_producer"), "analytics_events", ["producer"], unique=False)

    op.create_table(
        "consumed_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("consumer_name", sa.String(length=128), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "consumer_name", name="uq_consumed_event_consumer"),
    )

    op.create_table(
        "assignment_dimensions",
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=True),
        sa.Column("teacher_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_classroom_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index(op.f("ix_assignment_dimensions_lesson_id"), "assignment_dimensions", ["lesson_id"], unique=False)

    op.create_table(
        "session_dimensions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_session_dimensions_assignment_id"), "session_dimensions", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_session_dimensions_student_id"), "session_dimensions", ["student_id"], unique=False)

    op.create_table(
        "user_activity_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("guests_created", sa.Integer(), nullable=False),
        sa.Column("users_created", sa.Integer(), nullable=False),
        sa.Column("lessons_created", sa.Integer(), nullable=False),
        sa.Column("classrooms_created", sa.Integer(), nullable=False),
        sa.Column("assignments_created", sa.Integer(), nullable=False),
        sa.Column("sessions_started", sa.Integer(), nullable=False),
        sa.Column("sessions_submitted", sa.Integer(), nullable=False),
        sa.Column("answers_submitted", sa.Integer(), nullable=False),
        sa.Column("feedback_submitted", sa.Integer(), nullable=False),
        sa.Column("ai_jobs_requested", sa.Integer(), nullable=False),
        sa.Column("ai_jobs_succeeded", sa.Integer(), nullable=False),
        sa.Column("ai_jobs_failed", sa.Integer(), nullable=False),
        sa.Column("ai_lessons_generated", sa.Integer(), nullable=False),
        sa.Column("ai_images_generated", sa.Integer(), nullable=False),
        sa.Column("ai_audio_generated", sa.Integer(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_date", "user_id", name="uq_user_activity_day"),
    )
    op.create_index(op.f("ix_user_activity_daily_activity_date"), "user_activity_daily", ["activity_date"], unique=False)
    op.create_index(op.f("ix_user_activity_daily_user_id"), "user_activity_daily", ["user_id"], unique=False)

    op.create_table(
        "lesson_quality_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("assignments_created", sa.Integer(), nullable=False),
        sa.Column("sessions_started", sa.Integer(), nullable=False),
        sa.Column("sessions_submitted", sa.Integer(), nullable=False),
        sa.Column("answers_scored", sa.Integer(), nullable=False),
        sa.Column("score_sum", sa.Float(), nullable=False),
        sa.Column("score_count", sa.Integer(), nullable=False),
        sa.Column("feedback_count", sa.Integer(), nullable=False),
        sa.Column("feedback_rating_sum", sa.Integer(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_date", "lesson_id", name="uq_lesson_quality_day"),
    )
    op.create_index(op.f("ix_lesson_quality_daily_activity_date"), "lesson_quality_daily", ["activity_date"], unique=False)
    op.create_index(op.f("ix_lesson_quality_daily_lesson_id"), "lesson_quality_daily", ["lesson_id"], unique=False)

    op.create_table(
        "platform_overview_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("guests_created", sa.Integer(), nullable=False),
        sa.Column("users_created", sa.Integer(), nullable=False),
        sa.Column("users_upgraded", sa.Integer(), nullable=False),
        sa.Column("lessons_created", sa.Integer(), nullable=False),
        sa.Column("classrooms_created", sa.Integer(), nullable=False),
        sa.Column("assignments_created", sa.Integer(), nullable=False),
        sa.Column("sessions_started", sa.Integer(), nullable=False),
        sa.Column("sessions_submitted", sa.Integer(), nullable=False),
        sa.Column("sessions_expired", sa.Integer(), nullable=False),
        sa.Column("answers_submitted", sa.Integer(), nullable=False),
        sa.Column("answers_scored", sa.Integer(), nullable=False),
        sa.Column("feedback_submitted", sa.Integer(), nullable=False),
        sa.Column("ai_jobs_requested", sa.Integer(), nullable=False),
        sa.Column("ai_jobs_succeeded", sa.Integer(), nullable=False),
        sa.Column("ai_jobs_failed", sa.Integer(), nullable=False),
        sa.Column("ai_lessons_generated", sa.Integer(), nullable=False),
        sa.Column("ai_images_generated", sa.Integer(), nullable=False),
        sa.Column("ai_audio_generated", sa.Integer(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_overview_daily_activity_date"), "platform_overview_daily", ["activity_date"], unique=True)

    op.create_table(
        "lesson_review_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lesson_review_flags_lesson_id"), "lesson_review_flags", ["lesson_id"], unique=False)
    op.create_index(op.f("ix_lesson_review_flags_created_by_user_id"), "lesson_review_flags", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_lesson_review_flags_status"), "lesson_review_flags", ["status"], unique=False)

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_export_jobs_export_type"), "export_jobs", ["export_type"], unique=False)
    op.create_index(op.f("ix_export_jobs_requested_by_user_id"), "export_jobs", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_export_jobs_status"), "export_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_export_jobs_status"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_requested_by_user_id"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_export_type"), table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_index(op.f("ix_lesson_review_flags_status"), table_name="lesson_review_flags")
    op.drop_index(op.f("ix_lesson_review_flags_created_by_user_id"), table_name="lesson_review_flags")
    op.drop_index(op.f("ix_lesson_review_flags_lesson_id"), table_name="lesson_review_flags")
    op.drop_table("lesson_review_flags")

    op.drop_index(op.f("ix_platform_overview_daily_activity_date"), table_name="platform_overview_daily")
    op.drop_table("platform_overview_daily")

    op.drop_index(op.f("ix_lesson_quality_daily_lesson_id"), table_name="lesson_quality_daily")
    op.drop_index(op.f("ix_lesson_quality_daily_activity_date"), table_name="lesson_quality_daily")
    op.drop_table("lesson_quality_daily")

    op.drop_index(op.f("ix_user_activity_daily_user_id"), table_name="user_activity_daily")
    op.drop_index(op.f("ix_user_activity_daily_activity_date"), table_name="user_activity_daily")
    op.drop_table("user_activity_daily")

    op.drop_index(op.f("ix_session_dimensions_student_id"), table_name="session_dimensions")
    op.drop_index(op.f("ix_session_dimensions_assignment_id"), table_name="session_dimensions")
    op.drop_table("session_dimensions")

    op.drop_index(op.f("ix_assignment_dimensions_lesson_id"), table_name="assignment_dimensions")
    op.drop_table("assignment_dimensions")

    op.drop_table("consumed_events")

    op.drop_index(op.f("ix_analytics_events_producer"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_event_type"), table_name="analytics_events")
    op.drop_index(op.f("ix_analytics_events_event_id"), table_name="analytics_events")
    op.drop_table("analytics_events")
