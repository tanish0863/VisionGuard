import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator


class RunDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
        self.fail_incomplete_runs()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error_message TEXT
                );
                CREATE TABLE IF NOT EXISTS reports (
                    run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def fail_incomplete_runs(self) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'FAILED',
                    finished_at = ?,
                    error_message = 'Backend restarted before evaluation completed'
                WHERE status IN ('QUEUED', 'RUNNING')
                """,
                (finished_at,),
            )

    def create_run(self, run: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, status, model_id, dataset_id, config_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run["run_id"],
                    run["status"],
                    run["model_id"],
                    run["dataset_id"],
                    json.dumps(run["config"], allow_nan=False),
                    run["created_at"],
                ),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        run = dict(row)
        run["config"] = json.loads(run.pop("config_json"))
        return run

    def list_runs(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        with self.connection() as connection:
            total = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            rows = connection.execute(
                """
                SELECT * FROM runs
                ORDER BY created_at DESC, run_id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows], total

    def start_run(self, run_id: str, started_at: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs SET status = 'RUNNING', started_at = ?
                WHERE run_id = ? AND status = 'QUEUED'
                """,
                (started_at, run_id),
            )

    def complete_run(
        self, run_id: str, report: dict[str, Any], finished_at: str
    ) -> None:
        report_json = json.dumps(report, allow_nan=False)
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO reports (run_id, report_json, created_at) VALUES (?, ?, ?)",
                (run_id, report_json, finished_at),
            )
            connection.execute(
                """
                UPDATE runs SET status = 'COMPLETED', finished_at = ?
                WHERE run_id = ? AND status = 'RUNNING'
                """,
                (finished_at, run_id),
            )

    def fail_run(self, run_id: str, message: str, finished_at: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runs SET status = 'FAILED', finished_at = ?, error_message = ?
                WHERE run_id = ?
                """,
                (finished_at, message, run_id),
            )

    def get_report(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM reports WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "report": json.loads(row["report_json"]),
        }
