"""Evaluation job dispatching and worker execution layer.

Decouples the FastAPI HTTP request handler from the ML evaluation worker.
The API creates and persists a QUEUED run in PostgreSQL/SQLite and hands the
run_id to a JobDispatcher. The worker loads the run configuration from the database,
transitions status safely, executes the evaluator, and persists the report.
"""
from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.app.contracts import EvalConfig, EvaluationReport
from backend.app.database import DatabaseUnavailableError, RunDatabase
from backend.app.evaluation_adapter import get_evaluator

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobDispatcher(Protocol):
    """Abstract interface for submitting evaluation runs for processing."""

    def submit_evaluation(self, run_id: str) -> None:
        """Enqueue or dispatch an evaluation job for the given run_id."""
        ...


class ExecutionResult:
    """Outcome of a worker job execution."""

    def __init__(self, run_id: str, success: bool, status: str, error_message: str | None = None) -> None:
        self.run_id = run_id
        self.success = success
        self.status = status
        self.error_message = error_message

    def __repr__(self) -> str:
        return f"<ExecutionResult run_id={self.run_id} success={self.success} status={self.status}>"


class _HeartbeatManager:
    """Periodically sends heartbeats to the database while a long-running evaluation executes."""

    def __init__(
        self,
        database: RunDatabase,
        run_id: str,
        worker_id: str | None,
        attempt_count: int | None = None,
        interval: float = 10.0,
    ) -> None:
        self.database = database
        self.run_id = run_id
        self.worker_id = worker_id
        self.attempt_count = attempt_count
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def _loop() -> None:
            while not self._stop_event.wait(self.interval):
                try:
                    success = self.database.heartbeat_run(
                        self.run_id,
                        utc_now(),
                        worker_id=self.worker_id,
                        attempt_count=self.attempt_count,
                    )
                    if not success:
                        logger.warning(
                            "Heartbeat rejected for run %s (worker=%s, attempt=%s): lease expired or reclaimed",
                            self.run_id,
                            self.worker_id,
                            self.attempt_count,
                        )
                except Exception:
                    logger.debug("Failed to record heartbeat for run %s", self.run_id)

        self._thread = threading.Thread(target=_loop, daemon=True, name=f"heartbeat-{self.run_id}")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


def execute_evaluation_job(
    run_id: str,
    database: RunDatabase,
    evaluator: Callable[..., EvaluationReport] | None = None,
    worker_id: str | None = None,
    heartbeat_interval: float = 10.0,
) -> ExecutionResult:
    """Execute a single evaluation job by run_id using the configured database.

    1. Checks if run exists and is in QUEUED state (prevents duplicate execution).
    2. Atomically marks the run as RUNNING and sets lease heartbeat.
    3. Runs an active heartbeat manager to keep lease valid during GPU inference.
    4. Executes the ML evaluator with the persisted config.
    5. Validates the resulting EvaluationReport.
    6. Persists the report and updates the run status to COMPLETED, PARTIAL, or FAILED.
    7. On any unexpected exception, marks the run as FAILED with a sanitized error message.
    """
    logger.info("Worker '%s' picking up evaluation job: %s", worker_id or "local", run_id)
    try:
        run = database.get_run(run_id)
    except DatabaseUnavailableError:
        logger.error("Worker database error while fetching run %s", run_id)
        return ExecutionResult(run_id, False, "DATABASE_ERROR", "Database unavailable")

    if run is None:
        logger.warning("Worker received unknown run_id: %s", run_id)
        return ExecutionResult(run_id, False, "NOT_FOUND", "Run not found")

    attempt_count: int = 1
    if run.get("status") == "QUEUED":
        now = utc_now()
        try:
            attempt_count = database.start_run(run_id, now, worker_id=worker_id)
        except (ValueError, DatabaseUnavailableError) as exc:
            logger.warning("Could not transition run %s to RUNNING: %s", run_id, exc)
            return ExecutionResult(run_id, False, "CONFLICT", str(exc))
    elif run.get("status") == "RUNNING" and worker_id is not None and run.get("worker_id") == worker_id:
        attempt_count = run.get("attempt_count") or 1
        logger.info("Run %s already claimed by worker %s (attempt %d)", run_id, worker_id, attempt_count)
    else:
        logger.info(
            "Run %s is in status '%s' (not QUEUED or claimed by %s); skipping duplicate execution",
            run_id,
            run.get("status"),
            worker_id,
        )
        return ExecutionResult(run_id, False, str(run.get("status")), "Run is not queued")

    # Parse config
    try:
        raw_config = run.get("config")
        config = EvalConfig.model_validate(raw_config)
    except Exception as exc:
        logger.error("Failed to parse config for run %s: %s", run_id, exc)
        database.fail_run(
            run_id,
            "Invalid run configuration schema",
            utc_now(),
            worker_id=worker_id,
            attempt_count=attempt_count,
        )
        return ExecutionResult(run_id, False, "FAILED", "Invalid run configuration schema")

    # Execute evaluator with active heartbeat
    evaluator_function = evaluator if evaluator is not None else get_evaluator()
    heartbeat = _HeartbeatManager(
        database,
        run_id,
        worker_id,
        attempt_count=attempt_count,
        interval=heartbeat_interval,
    )
    heartbeat.start()
    try:
        result = evaluator_function(config, run_id=run_id)
        report = EvaluationReport.model_validate(result)
        if report.run_id != run_id:
            raise ValueError(f"Evaluator report run_id '{report.run_id}' does not match requested run_id '{run_id}'")
        report_json = json.loads(report.model_dump_json())
    except Exception as exc:
        logger.exception("Evaluation failed for run %s: %s", run_id, exc)
        safe_msg = "Evaluation failed before a valid report was produced"
        try:
            database.fail_run(
                run_id,
                safe_msg,
                utc_now(),
                worker_id=worker_id,
                attempt_count=attempt_count,
            )
        except Exception:
            logger.exception("Failed to mark run %s as failed in database", run_id)
        return ExecutionResult(run_id, False, "FAILED", safe_msg)
    finally:
        heartbeat.stop()

    # Persist report
    status = report.status.value
    error_message = (
        f"Evaluation returned a {status} report; see the report for details"
        if status in {"PARTIAL", "FAILED"}
        else None
    )
    finished_at = utc_now()
    try:
        database.complete_run(
            run_id,
            report_json,
            status,
            finished_at,
            error_message,
            worker_id=worker_id,
            attempt_count=attempt_count,
        )
    except Exception as exc:
        logger.exception("Failed to persist report for run %s: %s", run_id, exc)
        return ExecutionResult(run_id, False, "DATABASE_ERROR", "Failed to persist report")

    logger.info("Evaluation job completed successfully for run %s with status %s", run_id, status)
    return ExecutionResult(run_id, True, status)


class BackgroundTasksDispatcher:
    """Dispatcher adapter that executes the worker via FastAPI's BackgroundTasks.

    Used when VISIONGUARD_DISPATCHER=background (default).
    """

    def __init__(
        self,
        database: RunDatabase,
        evaluator: Callable[..., EvaluationReport] | None = None,
        background_tasks: Any | None = None,
    ) -> None:
        self.database = database
        self.evaluator = evaluator
        self.background_tasks = background_tasks

    def submit_evaluation(self, run_id: str) -> None:
        if self.background_tasks is not None:
            self.background_tasks.add_task(
                execute_evaluation_job,
                run_id=run_id,
                database=self.database,
                evaluator=self.evaluator,
            )
        else:
            execute_evaluation_job(run_id, self.database, self.evaluator)


class WorkerCliDispatcher:
    """Dispatcher for independent worker mode (VISIONGUARD_DISPATCHER=worker).

    Leaves runs in QUEUED status in the database so external workers can claim them.
    Never initiates in-process evaluation.
    """

    def __init__(self) -> None:
        pass

    def submit_evaluation(self, run_id: str) -> None:
        logger.info(
            "Run %s queued in database; awaiting external worker pickup (VISIONGUARD_DISPATCHER=worker)",
            run_id,
        )


class RecordingDispatcher:
    """Mock dispatcher for tests that records submitted run_ids without executing them."""

    def __init__(self) -> None:
        self.submitted_run_ids: list[str] = []

    def submit_evaluation(self, run_id: str) -> None:
        self.submitted_run_ids.append(run_id)

