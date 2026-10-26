"""Create artifacts metadata table for distributed object storage.

Revision ID: 20261026_03
Revises: 20261026_02
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_03"
down_revision = "20261026_02"
branch_labels = None
depends_on = None

ARTIFACT_COLUMNS = {
    "artifact_id",
    "run_id",
    "artifact_type",
    "file_name",
    "object_key",
    "content_type",
    "size_bytes",
    "created_at",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "artifacts" not in tables:
        op.create_table(
            "artifacts",
            sa.Column("artifact_id", sa.String(length=36), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=36),
                sa.ForeignKey("runs.run_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("artifact_type", sa.String(length=64), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("object_key", sa.String(length=1024), nullable=False, unique=True),
            sa.Column("content_type", sa.String(length=128), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"], unique=False)
        op.create_index("ix_artifacts_created_at", "artifacts", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "artifacts" in tables:
        existing_indices = {idx["name"] for idx in inspector.get_indexes("artifacts")}
        if "ix_artifacts_created_at" in existing_indices:
            op.drop_index("ix_artifacts_created_at", table_name="artifacts")
        if "ix_artifacts_run_id" in existing_indices:
            op.drop_index("ix_artifacts_run_id", table_name="artifacts")
        op.drop_table("artifacts")
