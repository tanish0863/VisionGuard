"""Add worker lease, heartbeat, and retry columns to runs table.

Revision ID: 20261026_02
Revises: 20261025_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_02"
down_revision = "20261025_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("runs")}

    # Add worker_id column if missing
    if "worker_id" not in existing_columns:
        op.add_column("runs", sa.Column("worker_id", sa.String(length=64), nullable=True))

    # Add heartbeat_at column if missing
    if "heartbeat_at" not in existing_columns:
        op.add_column("runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    # Add attempt_count column if missing
    if "attempt_count" not in existing_columns:
        op.add_column(
            "runs",
            sa.Column(
                "attempt_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )

    # Add index on (status, heartbeat_at) for efficient stale lease queries
    existing_indices = {idx["name"] for idx in inspector.get_indexes("runs")}
    if "ix_runs_status_heartbeat" not in existing_indices:
        op.create_index(
            "ix_runs_status_heartbeat",
            "runs",
            ["status", "heartbeat_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indices = {idx["name"] for idx in inspector.get_indexes("runs")}
    if "ix_runs_status_heartbeat" in existing_indices:
        op.drop_index("ix_runs_status_heartbeat", table_name="runs")

    existing_columns = {col["name"] for col in inspector.get_columns("runs")}
    if "attempt_count" in existing_columns:
        op.drop_column("runs", "attempt_count")
    if "heartbeat_at" in existing_columns:
        op.drop_column("runs", "heartbeat_at")
    if "worker_id" in existing_columns:
        op.drop_column("runs", "worker_id")
