"""Widen artifact_id to VARCHAR(255) and configure composite primary key (run_id, artifact_id).

Revision ID: 20261026_04
Revises: 20261026_03
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_04"
down_revision = "20261026_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "artifacts" in tables:
        dialect_name = bind.dialect.name
        if dialect_name == "postgresql":
            # Widen artifact_id column to 255 chars
            op.alter_column(
                "artifacts",
                "artifact_id",
                type_=sa.String(length=255),
                existing_type=sa.String(length=36),
                existing_nullable=False,
            )
            # Replace single-column PK with composite PK (run_id, artifact_id)
            pk_constraint = inspector.get_pk_constraint("artifacts")
            pk_name = (pk_constraint or {}).get("name") or "artifacts_pkey"
            try:
                op.drop_constraint(pk_name, "artifacts", type_="primary")
            except Exception:
                pass
            op.create_primary_key("artifacts_pkey", "artifacts", ["run_id", "artifact_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "artifacts" in tables:
        dialect_name = bind.dialect.name
        if dialect_name == "postgresql":
            try:
                op.drop_constraint("artifacts_pkey", "artifacts", type_="primary")
            except Exception:
                pass
            op.create_primary_key("artifacts_pkey", "artifacts", ["artifact_id"])
            op.alter_column(
                "artifacts",
                "artifact_id",
                type_=sa.String(length=36),
                existing_type=sa.String(length=255),
                existing_nullable=False,
            )
