"""Create VisionGuard run and report tables.

Revision ID: 20261025_01
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261025_01"
down_revision = None
branch_labels = None
depends_on = None


RUN_COLUMNS = {
    "run_id",
    "status",
    "model_id",
    "dataset_id",
    "config_json",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "error_message",
}
REPORT_COLUMNS = {"report_id", "run_id", "report_json", "created_at"}


def _ensure_existing_table_compatible(
    table_name: str, required_columns: set[str]
) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    missing = required_columns - existing
    if missing:
        raise RuntimeError(
            f"Existing table '{table_name}' is incompatible with this migration; "
            f"missing required columns: {', '.join(sorted(missing))}. "
            "Back up the database and review its schema before migrating."
        )
    return True


def _column_type_is_jsonb(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    columns = inspector.get_columns(table_name)
    column = next(item for item in columns if item["name"] == column_name)
    return isinstance(column["type"], postgresql.JSONB)


def upgrade() -> None:
    if not _ensure_existing_table_compatible("runs", RUN_COLUMNS):
        op.create_table(
            "runs",
            sa.Column("run_id", sa.String(length=36), primary_key=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("model_id", sa.String(length=255), nullable=False),
            sa.Column("dataset_id", sa.String(length=255), nullable=False),
            sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.Column("error_message", sa.Text()),
            sa.CheckConstraint(
                "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED')",
                name="ck_runs_status",
            ),
        )
    else:
        run_primary_key = sa.inspect(op.get_bind()).get_pk_constraint("runs")
        run_checks = sa.inspect(op.get_bind()).get_check_constraints("runs")
        if (
            run_primary_key.get("constrained_columns") != ["run_id"]
            or not any(check.get("name") == "ck_runs_status" for check in run_checks)
            or not _column_type_is_jsonb("runs", "config_json")
        ):
            raise RuntimeError(
                "Existing 'runs' table is missing required primary-key or "
                "status constraints or JSONB config. Back up and review the "
                "schema before migrating."
            )

    if not _ensure_existing_table_compatible("reports", REPORT_COLUMNS):
        op.create_table(
            "reports",
            sa.Column("report_id", sa.String(length=36), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=36),
                sa.ForeignKey("runs.run_id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "report_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    else:
        inspector = sa.inspect(op.get_bind())
        report_primary_key = inspector.get_pk_constraint("reports")
        report_uniques = inspector.get_unique_constraints("reports")
        report_foreign_keys = inspector.get_foreign_keys("reports")
        if (
            report_primary_key.get("constrained_columns") != ["report_id"]
            or not _column_type_is_jsonb("reports", "report_json")
            or not any(
                constraint.get("column_names") == ["run_id"]
                for constraint in report_uniques
            )
            or not any(
                foreign_key.get("constrained_columns") == ["run_id"]
                and foreign_key.get("referred_table") == "runs"
                and foreign_key.get("referred_columns") == ["run_id"]
                for foreign_key in report_foreign_keys
            )
        ):
            raise RuntimeError(
                "Existing 'reports' table is missing required primary-key, "
                "unique, or foreign-key constraints or JSONB report data. Back "
                "up and review the schema before migrating."
            )

    inspector = sa.inspect(op.get_bind())
    existing_indexes = {
        table: {index["name"] for index in inspector.get_indexes(table)}
        for table in ("runs", "reports")
    }
    if "ix_runs_created_at" not in existing_indexes["runs"]:
        op.create_index("ix_runs_created_at", "runs", ["created_at"])
    if "ix_runs_status_created_at" not in existing_indexes["runs"]:
        op.create_index(
            "ix_runs_status_created_at", "runs", ["status", "created_at"]
        )
    if "ix_reports_created_at" not in existing_indexes["reports"]:
        op.create_index("ix_reports_created_at", "reports", ["created_at"])


def downgrade() -> None:
    raise RuntimeError(
        "Automatic downgrade is disabled to protect evaluation data. "
        "Use a reviewed, data-preserving migration if rollback is required."
    )
