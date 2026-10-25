import os
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    URL,
    create_engine,
    make_url,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseUnavailableError(RuntimeError):
    pass


metadata = MetaData()
json_type = JSON().with_variant(JSONB(), "postgresql")

runs = Table(
    "runs",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("status", String(16), nullable=False),
    Column("model_id", String(255), nullable=False),
    Column("dataset_id", String(255), nullable=False),
    Column("config_json", json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_message", String),
    CheckConstraint(
        "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED')",
        name="ck_runs_status",
    ),
)
Index("ix_runs_created_at", runs.c.created_at)
Index("ix_runs_status_created_at", runs.c.status, runs.c.created_at)

reports = Table(
    "reports",
    metadata,
    Column("report_id", String(36), primary_key=True),
    Column(
        "run_id",
        String(36),
        ForeignKey("runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("report_json", json_type, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_reports_created_at", reports.c.created_at)

TERMINAL_STATUSES = {"COMPLETED", "PARTIAL", "FAILED"}
RUN_STATUSES = {"QUEUED", "RUNNING", *TERMINAL_STATUSES}


def _require_postgres_tls(url: URL) -> URL:
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    sslmode = url.query.get("sslmode", "").lower()
    if sslmode and sslmode not in {"require", "verify-ca", "verify-full"}:
        raise DatabaseConfigurationError(
            "PostgreSQL DATABASE_URL must require TLS; use sslmode=require or stronger."
        )
    if not sslmode:
        url = url.update_query_dict({"sslmode": "require"})
    return url


def database_url_from_environment(
    environment: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> URL:
    if environment is None:
        if dotenv_path is None:
            load_dotenv()
        else:
            load_dotenv(dotenv_path=dotenv_path)
        environment = os.environ

    raw_url = environment.get("DATABASE_URL", "").strip()
    if not raw_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is required. Configure it in the environment or local .env file."
        )

    try:
        url = make_url(raw_url)
    except (TypeError, ValueError) as error:
        raise DatabaseConfigurationError(
            "DATABASE_URL is invalid; check its scheme and syntax."
        ) from error

    if url.get_backend_name() == "postgresql":
        url = _require_postgres_tls(url)
    else:
        raise DatabaseConfigurationError(
            "DATABASE_URL must use PostgreSQL. SQLite is reserved for isolated tests."
        )
    return url


class RunDatabase:
    def __init__(self, database_url: str | URL | None = None) -> None:
        if database_url is None:
            url = database_url_from_environment()
        else:
            try:
                url = make_url(database_url) if isinstance(database_url, str) else database_url
            except (TypeError, ValueError) as error:
                raise DatabaseConfigurationError(
                    "Database URL is invalid; check its scheme and syntax."
                ) from error
            if url.get_backend_name() == "postgresql":
                url = _require_postgres_tls(url)

        engine_options: dict[str, Any] = {"pool_pre_ping": True}
        if url.get_backend_name() == "postgresql":
            engine_options.update(
                pool_size=5,
                max_overflow=10,
                pool_recycle=300,
                connect_args={"connect_timeout": 5},
            )
        elif url.database in {None, "", ":memory:"}:
            from sqlalchemy.pool import StaticPool

            engine_options["poolclass"] = StaticPool
            engine_options["connect_args"] = {"check_same_thread": False}

        try:
            self.engine: Engine = create_engine(url, **engine_options)
        except (SQLAlchemyError, TypeError, ValueError) as error:
            raise DatabaseConfigurationError(
                "Could not initialize the configured database driver."
            ) from error

    @classmethod
    def from_environment(cls) -> "RunDatabase":
        return cls(database_url_from_environment())

    @contextmanager
    def connection(self) -> Generator[Connection, None, None]:
        try:
            with self.engine.begin() as connection:
                yield connection
        except SQLAlchemyError as error:
            raise DatabaseUnavailableError(
                "Database operation failed; verify database availability and migrations."
            ) from error

    def check_connection(self) -> None:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise DatabaseUnavailableError(
                "Database connectivity check failed."
            ) from error

    def dispose(self) -> None:
        self.engine.dispose()

    def fail_incomplete_runs(self, finished_at: Any) -> None:
        with self.connection() as connection:
            connection.execute(
                update(runs)
                .where(runs.c.status.in_(("QUEUED", "RUNNING")))
                .values(
                    status="FAILED",
                    finished_at=finished_at,
                    updated_at=finished_at,
                    error_message=(
                        "Backend restarted before evaluation completed"
                    ),
                )
            )

    def create_run(self, run: dict[str, Any]) -> None:
        if run["status"] not in RUN_STATUSES:
            raise ValueError(f"Invalid run status: {run['status']}")
        with self.connection() as connection:
            connection.execute(
                runs.insert().values(
                    run_id=run["run_id"],
                    status=run["status"],
                    model_id=run["model_id"],
                    dataset_id=run["dataset_id"],
                    config_json=run["config"],
                    created_at=run["created_at"],
                    updated_at=run.get("updated_at", run["created_at"]),
                )
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                select(runs).where(runs.c.run_id == run_id)
            ).mappings().first()
        if row is None:
            return None
        result = dict(row)
        result["config"] = result.pop("config_json")
        return result

    def list_runs(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        with self.connection() as connection:
            total = connection.execute(
                select(text("count(*)")).select_from(runs)
            ).scalar_one()
            rows = connection.execute(
                select(runs)
                .order_by(runs.c.created_at.desc(), runs.c.run_id.desc())
                .limit(limit)
                .offset(offset)
            ).mappings().all()
        return [dict(row) for row in rows], total

    def start_run(self, run_id: str, started_at: Any) -> None:
        with self.connection() as connection:
            result = connection.execute(
                update(runs)
                .where(runs.c.run_id == run_id, runs.c.status == "QUEUED")
                .values(
                    status="RUNNING",
                    started_at=started_at,
                    updated_at=started_at,
                )
            )
            if result.rowcount != 1:
                raise ValueError(f"Run '{run_id}' is not queued")

    def complete_run(
        self,
        run_id: str,
        report: dict[str, Any],
        status: str,
        finished_at: Any,
        error_message: str | None = None,
        report_id: str | None = None,
    ) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Invalid terminal run status: {status}")
        with self.connection() as connection:
            result = connection.execute(
                update(runs)
                .where(runs.c.run_id == run_id, runs.c.status == "RUNNING")
                .values(
                    status=status,
                    finished_at=finished_at,
                    updated_at=finished_at,
                    error_message=error_message,
                )
            )
            if result.rowcount != 1:
                raise ValueError(f"Run '{run_id}' is not running")
            connection.execute(
                reports.insert().values(
                    report_id=report_id or str(uuid4()),
                    run_id=run_id,
                    report_json=report,
                    created_at=finished_at,
                )
            )

    def fail_run(self, run_id: str, message: str, finished_at: Any) -> None:
        with self.connection() as connection:
            result = connection.execute(
                update(runs)
                .where(
                    runs.c.run_id == run_id,
                    runs.c.status.in_(("QUEUED", "RUNNING")),
                )
                .values(
                    status="FAILED",
                    finished_at=finished_at,
                    updated_at=finished_at,
                    error_message=message,
                )
            )
            if result.rowcount != 1:
                raise ValueError(f"Run '{run_id}' is not active")

    def get_report(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                select(reports).where(reports.c.run_id == run_id)
            ).mappings().first()
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "report": row["report_json"],
        }
