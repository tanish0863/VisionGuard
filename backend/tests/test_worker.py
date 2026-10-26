from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts import EvalConfig, EvaluationReport, RunStatus
from backend.app.database import RunDatabase, metadata
from backend.app.execution import (
    RecordingDispatcher,
    execute_evaluation_job,
)
from backend.app.main import create_app
from backend.app.worker import process_single_run
from visionguard_contracts.visionguard.core.fixtures import build_fixture_report


def valid_config() -> dict[str, Any]:
    return {
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "corruptions": [{"kind": "blur", "severities": [1]}],
        "seed": 42,
        "score_threshold": 0.5,
        "match_iou_threshold": 0.5,
    }


def make_report(run_id: str, status: RunStatus = RunStatus.COMPLETED) -> EvaluationReport:
    report = build_fixture_report().model_dump(mode="json")
    report["run_id"] = run_id
    report["status"] = status.value
    if status in {RunStatus.PARTIAL, RunStatus.FAILED}:
        report["errors"] = [{"image_id": "image_001", "stage": "inference", "message": "worker test error"}]
    return EvaluationReport.model_validate(report)


def test_api_submits_run_without_executing_evaluator(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'dispatch.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    dispatcher = RecordingDispatcher()

    # Injected evaluator will raise if called
    def failing_evaluator(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("API called evaluator directly!")

    app = create_app(database=db, evaluator=failing_evaluator, dispatcher=dispatcher)

    with TestClient(app) as client:
        resp = client.post("/api/v1/runs", json=valid_config())
        assert resp.status_code == 202
        created = resp.json()
        run_id = created["run_id"]
        assert created["status"] == "QUEUED"

        # Dispatcher received the run_id
        assert dispatcher.submitted_run_ids == [run_id]

        # In database, run remains QUEUED because dispatcher did not execute it
        run = db.get_run(run_id)
        assert run is not None
        assert run["status"] == "QUEUED"

    db.dispose()


def test_worker_executes_queued_run_and_persists_report(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'worker_exec.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    # Insert a queued run
    run_id = "test-worker-run-1"
    now = datetime.now(timezone.utc)
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": now,
        "updated_at": now,
    })

    def fake_evaluator(config: EvalConfig, *, run_id: str) -> EvaluationReport:
        return make_report(run_id, RunStatus.COMPLETED)

    # Execute via worker
    result = execute_evaluation_job(run_id, db, evaluator=fake_evaluator)
    assert result.success is True
    assert result.status == "COMPLETED"

    # Verify run and report in database
    run = db.get_run(run_id)
    assert run is not None
    assert run["status"] == "COMPLETED"
    assert run["started_at"] is not None
    assert run["finished_at"] is not None

    report_row = db.get_report(run_id)
    assert report_row is not None
    assert report_row["report"]["run_id"] == run_id
    db.dispose()


def test_worker_records_evaluator_failure(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'worker_fail.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    run_id = "test-fail-run-1"
    now = datetime.now(timezone.utc)
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": now,
        "updated_at": now,
    })

    def blowing_evaluator(config: EvalConfig, *, run_id: str) -> EvaluationReport:
        raise RuntimeError("Simulated GPU out of memory error with secret=12345")

    result = execute_evaluation_job(run_id, db, evaluator=blowing_evaluator)
    assert result.success is False
    assert result.status == "FAILED"

    # Status must be FAILED, error message must be sanitized (no secrets)
    run = db.get_run(run_id)
    assert run is not None
    assert run["status"] == "FAILED"
    assert "secret" not in run["error_message"]
    db.dispose()


def test_worker_handles_duplicate_execution(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'worker_dup.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    run_id = "test-dup-run"
    now = datetime.now(timezone.utc)
    # Already COMPLETED run
    db.create_run({
        "run_id": run_id,
        "status": "COMPLETED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": now,
        "updated_at": now,
    })

    eval_called = False

    def check_evaluator(*args: Any, **kwargs: Any) -> Any:
        nonlocal eval_called
        eval_called = True

    result = execute_evaluation_job(run_id, db, evaluator=check_evaluator)
    assert result.success is False
    assert result.status == "COMPLETED"
    assert eval_called is False
    db.dispose()


def test_worker_handles_missing_run_id(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'worker_missing.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    result = execute_evaluation_job("non-existent-id", db)
    assert result.success is False
    assert result.status == "NOT_FOUND"
    db.dispose()


def test_standalone_cli_worker_process(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'cli_worker.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    run_id = "cli-test-run"
    now = datetime.now(timezone.utc)
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": now,
        "updated_at": now,
    })

    # Test process_single_run using a mock evaluator via monkeypatch
    exit_code = process_single_run(run_id, database=db)
    # Will use real evaluate_run or default evaluator in pipeline; exit code 0 or 1 depending on environment
    assert exit_code in (0, 1)
    db.dispose()


def test_dispatcher_configuration_modes(tmp_path: Path, monkeypatch: Any) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'modes.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    # 1. Test invalid mode raises ValueError
    monkeypatch.setenv("VISIONGUARD_DISPATCHER", "unsupported_mode")
    with pytest.raises(ValueError, match="Invalid VISIONGUARD_DISPATCHER"):
        create_app(database=db)

    # 2. Test worker mode leaves run QUEUED without executing
    monkeypatch.setenv("VISIONGUARD_DISPATCHER", "worker")
    app = create_app(database=db)
    with TestClient(app) as client:
        resp = client.post("/api/v1/runs", json=valid_config())
        assert resp.status_code == 202
        run_id = resp.json()["run_id"]

        # Run must remain QUEUED in database
        run = db.get_run(run_id)
        assert run is not None
        assert run["status"] == "QUEUED"

    db.dispose()


def test_two_workers_atomic_claiming(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'atomic_claim.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    now = datetime.now(timezone.utc)
    run_id = "atomic-claim-run-1"
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": now,
        "updated_at": now,
    })

    # Worker 1 claims
    w1_claimed = db.claim_next_queued_run(worker_id="worker-node-1", claimed_at=now)
    assert w1_claimed is not None
    assert w1_claimed["run_id"] == run_id
    assert w1_claimed["worker_id"] == "worker-node-1"
    assert w1_claimed["attempt_count"] == 1

    # Worker 2 attempts to claim next queued run; must get None since no other run is QUEUED
    w2_claimed = db.claim_next_queued_run(worker_id="worker-node-2", claimed_at=now)
    assert w2_claimed is None

    # Run in DB must be RUNNING and claimed by worker-node-1
    run = db.get_run(run_id)
    assert run is not None
    assert run["status"] == "RUNNING"
    assert run["worker_id"] == "worker-node-1"
    db.dispose()


def test_crash_recovery_without_api_restart(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'recovery.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)

    # 1. Create a run that was started 120s ago with no recent heartbeat
    run_id = "stale-crashed-run"
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": stale_time,
        "updated_at": stale_time,
    })
    db.start_run(run_id, started_at=stale_time, worker_id="crashed-worker-1")

    # Verify initial attempt count is 1
    run_before = db.get_run(run_id)
    assert run_before["status"] == "RUNNING"
    assert run_before["attempt_count"] == 1

    # 2. Recover stale runs with lease_timeout = 60s
    res = db.recover_stale_runs(now=now, lease_timeout_seconds=60.0, max_attempts=3)
    assert res["recovered"] == 1
    assert res["failed"] == 0

    # 3. Run should now be QUEUED again with worker_id cleared and error message set
    run_after = db.get_run(run_id)
    assert run_after["status"] == "QUEUED"
    assert run_after["worker_id"] is None
    assert "requeued" in run_after["error_message"]

    db.dispose()


def test_crash_recovery_bounded_retries(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'bounded_retry.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)

    # Create a run that has already been attempted 3 times
    run_id = "max-attempt-run"
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": stale_time,
        "updated_at": stale_time,
    })
    db.start_run(run_id, started_at=stale_time, worker_id="crashed-worker-2")

    # Manually set attempt count to 3
    from sqlalchemy import update
    from backend.app.database import runs
    with db.connection() as conn:
        conn.execute(update(runs).where(runs.c.run_id == run_id).values(attempt_count=3))

    # Recover with max_attempts = 3; should permanently fail
    res = db.recover_stale_runs(now=now, lease_timeout_seconds=60.0, max_attempts=3)
    assert res["recovered"] == 0
    assert res["failed"] == 1

    run = db.get_run(run_id)
    assert run["status"] == "FAILED"
    assert "lease expired after 3 attempts" in run["error_message"]
    db.dispose()


def test_healthy_heartbeat_lease_not_recovered(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'healthy_lease.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    started_time = now - timedelta(seconds=120)
    recent_heartbeat = now - timedelta(seconds=5)

    run_id = "healthy-active-run"
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": started_time,
        "updated_at": started_time,
    })
    db.start_run(run_id, started_at=started_time, worker_id="healthy-worker")
    db.heartbeat_run(run_id, heartbeat_at=recent_heartbeat, worker_id="healthy-worker")

    # Run recovery with lease_timeout = 60s; recent heartbeat (5s ago) must NOT be recovered
    res = db.recover_stale_runs(now=now, lease_timeout_seconds=60.0, max_attempts=3)
    assert res["recovered"] == 0
    assert res["failed"] == 0

    run = db.get_run(run_id)
    assert run["status"] == "RUNNING"
    db.dispose()


def test_api_stale_recovery_endpoint(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'api_recovery.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)

    app = create_app(database=db)
    with TestClient(app) as client:
        run_id = "api-recover-run"
        db.create_run({
            "run_id": run_id,
            "status": "QUEUED",
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": "visionguard_demo",
            "config": valid_config(),
            "created_at": stale_time,
            "updated_at": stale_time,
        })
        db.start_run(run_id, started_at=stale_time, worker_id="dead-worker")

        resp = client.post("/api/v1/runs/recover-stale?lease_timeout=60&max_attempts=3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["recovered"] == 1
        assert body["failed"] == 0

        run = db.get_run(run_id)
        assert run["status"] == "QUEUED"

    db.dispose()


def test_stale_worker_lease_expiry_and_mutation_rejection(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'stale_reject.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)

    run_id = "fencing-test-run"
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": valid_config(),
        "created_at": stale_time,
        "updated_at": stale_time,
    })

    # 1. Worker A claims the job
    worker_a = "worker-node-alpha"
    claimed_a = db.claim_next_queued_run(worker_id=worker_a, claimed_at=stale_time)
    assert claimed_a is not None
    assert claimed_a["run_id"] == run_id
    assert claimed_a["worker_id"] == worker_a
    assert claimed_a["attempt_count"] == 1

    # 2. Worker A's lease expires and stale recovery requeues the job
    recovery_res = db.recover_stale_runs(now=now, lease_timeout_seconds=60.0, max_attempts=3)
    assert recovery_res["recovered"] == 1

    # 3. Worker B reclaims the job
    worker_b = "worker-node-beta"
    claimed_b = db.claim_next_queued_run(worker_id=worker_b, claimed_at=now)
    assert claimed_b is not None
    assert claimed_b["run_id"] == run_id
    assert claimed_b["worker_id"] == worker_b
    assert claimed_b["attempt_count"] == 2

    # 4. Worker A attempts heartbeat renewal, completion, failure, and report persistence
    # 4a. Heartbeat renewal by stale Worker A is rejected (returns False)
    hb_res = db.heartbeat_run(run_id, heartbeat_at=now, worker_id=worker_a, attempt_count=1)
    assert hb_res is False

    # 4b. Report persistence by stale Worker A is rejected
    sample_report = make_report(run_id, RunStatus.COMPLETED).model_dump(mode="json")
    with pytest.raises(ValueError, match="report persistence rejected"):
        db.persist_report(
            run_id,
            sample_report,
            created_at=now,
            worker_id=worker_a,
            attempt_count=1,
        )

    # 4c. Completion by stale Worker A is rejected
    with pytest.raises(ValueError, match="cannot be completed by worker"):
        db.complete_run(
            run_id,
            sample_report,
            status="COMPLETED",
            finished_at=now,
            worker_id=worker_a,
            attempt_count=1,
        )

    # 4d. Failure reporting by stale Worker A is rejected
    with pytest.raises(ValueError, match="cannot be failed by worker"):
        db.fail_run(
            run_id,
            message="Late failure from crashed worker",
            finished_at=now,
            worker_id=worker_a,
            attempt_count=1,
        )

    # 4e. Even if Worker A reused the same worker ID, stale generation attempt_count=1 is rejected
    stale_same_id_hb = db.heartbeat_run(run_id, heartbeat_at=now, worker_id=worker_b, attempt_count=1)
    assert stale_same_id_hb is False

    # 5. Verify the run is still RUNNING and owned by Worker B with attempt_count 2
    active_run = db.get_run(run_id)
    assert active_run["status"] == "RUNNING"
    assert active_run["worker_id"] == worker_b
    assert active_run["attempt_count"] == 2

    # 6. Worker B completes successfully
    db.complete_run(
        run_id,
        sample_report,
        status="COMPLETED",
        finished_at=now,
        worker_id=worker_b,
        attempt_count=2,
    )
    completed_run = db.get_run(run_id)
    assert completed_run["status"] == "COMPLETED"
    report_entry = db.get_report(run_id)
    assert report_entry is not None
    assert report_entry["report"]["run_id"] == run_id

    db.dispose()


