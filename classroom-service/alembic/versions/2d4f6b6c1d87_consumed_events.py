"""add consumed events table

Revision ID: 2d4f6b6c1d87
Revises: 04314a8de527
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d4f6b6c1d87"
down_revision: Union[str, Sequence[str], None] = "04314a8de527"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consumed_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("consumer_name", sa.String(length=128), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "consumer_name", name="uq_consumed_event_consumer"),
    )


def downgrade() -> None:
    op.drop_table("consumed_events")
