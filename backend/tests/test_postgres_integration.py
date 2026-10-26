"""Comprehensive PostgreSQL integration test suite.

This suite is strictly executed against a dedicated, isolated test database
configured via `TEST_DATABASE_URL`. It NEVER runs against the production
`DATABASE_URL`.
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from backend.app.database import RunDatabase, reports, runs


def get_test_db_url() -> str:
    test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not test_url:
        pytest.skip("Set TEST_DATABASE_URL to opt into dedicated PostgreSQL integration tests")
    prod_url = os.environ.get("DATABASE_URL", "").strip()
    if prod_url and test_url == prod_url:
        pytest.fail("SAFETY GUARD: TEST_DATABASE_URL must never match the production DATABASE_URL")
    return test_url


@pytest.fixture(scope="module")
def postgres_db():
    url = get_test_db_url()
    database = RunDatabase(url)
    try:
        database.check_connection()
    except Exception as exc:
        database.dispose()
        pytest.skip(f"Could not connect to TEST_DATABASE_URL: {exc}")
    yield database
    database.dispose()


@pytest.fixture(scope="module")
def migrated_postgres(postgres_db):
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    os.environ["ALEMBIC_DATABASE_URL"] = get_test_db_url()
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
    return postgres_db


def test_dedicated_postgres_database_connectivity(postgres_db) -> None:
    """Verifies that the dedicated test PostgreSQL instance is reachable."""
    postgres_db.check_connection()


def test_postgres_schema_and_migrations(migrated_postgres) -> None:
    """Verifies that all migrations run cleanly and create expected columns/indexes."""
    inspector = inspect(migrated_postgres.engine)
    table_names = inspector.get_table_names()
    assert "runs" in table_names, "Table 'runs' must exist"
    assert "reports" in table_names, "Table 'reports' must exist"

    run_cols = {col["name"]: col for col in inspector.get_columns("runs")}
    assert "run_id" in run_cols
    assert "status" in run_cols
    assert "worker_id" in run_cols
    assert "heartbeat_at" in run_cols
    assert "attempt_count" in run_cols
    assert "config_json" in run_cols

    run_indices = {idx["name"] for idx in inspector.get_indexes("runs")}
    assert "ix_runs_created_at" in run_indices
    assert "ix_runs_status_created_at" in run_indices
    assert "ix_runs_status_heartbeat" in run_indices

    report_cols = {col["name"]: col for col in inspector.get_columns("reports")}
    assert "report_id" in report_cols
    assert "run_id" in report_cols
    assert "report_json" in report_cols


def test_postgres_run_lifecycle_and_claiming(migrated_postgres) -> None:
    """Verifies atomic run creation, claiming, and heartbeat updates in PostgreSQL."""
    run_id = f"test-pg-run-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    migrated_postgres.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": {"corruptions": [{"kind": "blur", "severity": 1}]},
        "created_at": now,
        "updated_at": now,
    })

    record = migrated_postgres.get_run(run_id)
    assert record is not None
    assert record["status"] == "QUEUED"
    assert record["attempt_count"] == 0

    # Atomic claim
    worker_id = f"worker-{uuid.uuid4().hex[:6]}"
    claimed = migrated_postgres.claim_next_queued_run(worker_id=worker_id, claimed_at=now)
    assert claimed is not None

    # Heartbeat
    hb_time = datetime.now(timezone.utc)
    migrated_postgres.heartbeat_run(claimed["run_id"], heartbeat_at=hb_time, worker_id=worker_id)
    updated = migrated_postgres.get_run(claimed["run_id"])
    assert updated["heartbeat_at"] is not None


def test_postgres_report_persistence_and_restart(migrated_postgres) -> None:
    """Verifies JSONB report persistence and verification across database reconnects."""
    run_id = f"test-pg-report-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    migrated_postgres.create_run({
        "run_id": run_id,
        "status": "RUNNING",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": {"corruptions": [{"kind": "blur", "severity": 1}]},
        "created_at": now,
        "updated_at": now,
    })

    sample_report = {
        "run_id": run_id,
        "status": "COMPLETED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "created_at": now.isoformat(),
        "summary": {
            "retention": 0.92,
            "class_consistency": 0.98,
            "mean_iou": 0.85,
        },
        "conditions": [
            {
                "kind": "blur",
                "severity": 1,
                "retention": 0.92,
                "class_consistency": 0.98,
                "mean_iou": 0.85,
            }
        ],
        "metric_definitions": {
            "retention": "Ratio of matched corrupted detections to clean detections",
            "class_consistency": "Ratio of matched detections with same class",
            "mean_iou": "Mean intersection over union across matched boxes",
        },
        "limitations": [
            "Evaluated on synthetic corruption conditions without ground-truth annotations.",
        ],
    }

    report_id = migrated_postgres.persist_report(run_id, sample_report, now)
    assert report_id is not None

    migrated_postgres.update_run_status(run_id, "COMPLETED", now)

    # Simulate API restart: dispose existing engine and reconnect
    url = get_test_db_url()
    restarted_db = RunDatabase(url)
    try:
        retrieved_run = restarted_db.get_run(run_id)
        assert retrieved_run["status"] == "COMPLETED"

        retrieved_report = restarted_db.get_report(run_id)
        assert retrieved_report is not None
        assert retrieved_report["report_json"]["summary"]["retention"] == 0.92
        assert retrieved_report["report_json"]["summary"]["class_consistency"] == 0.98
        assert len(retrieved_report["report_json"]["conditions"]) == 1
    finally:
        restarted_db.dispose()


def test_postgres_multi_worker_concurrency_skip_locked(migrated_postgres) -> None:
    """Verifies that concurrent workers claiming jobs with FOR UPDATE SKIP LOCKED do not collide."""
    import concurrent.futures

    now = datetime.now(timezone.utc)
    num_runs = 5
    run_ids = [f"test-pg-concurrent-{uuid.uuid4().hex[:8]}" for _ in range(num_runs)]

    # Queue runs
    for r_id in run_ids:
        migrated_postgres.create_run({
            "run_id": r_id,
            "status": "QUEUED",
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": "visionguard_demo",
            "config": {"corruptions": [{"kind": "blur", "severity": 1}]},
            "created_at": now,
            "updated_at": now,
        })

    # Concurrently claim with 5 workers
    claimed_results: list[dict[str, Any]] = []

    def worker_claim(worker_num: int) -> dict[str, Any] | None:
        wid = f"pg-worker-{worker_num}-{uuid.uuid4().hex[:4]}"
        return migrated_postgres.claim_next_queued_run(worker_id=wid, claimed_at=datetime.now(timezone.utc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_runs) as executor:
        futures = [executor.submit(worker_claim, i) for i in range(num_runs)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                claimed_results.append(res)

    assert len(claimed_results) == num_runs, f"Expected {num_runs} claims, got {len(claimed_results)}"
    claimed_run_ids = {r["run_id"] for r in claimed_results}
    assert claimed_run_ids == set(run_ids), "All queued runs must be claimed exactly once"

    # All worker IDs must be unique
    claimed_workers = {r["worker_id"] for r in claimed_results}
    assert len(claimed_workers) == num_runs, "Each worker must claim a distinct job"

    # Further claims return None
    extra_claim = migrated_postgres.claim_next_queued_run(worker_id="extra-worker", claimed_at=now)
    assert extra_claim is None


def test_postgres_stale_worker_fencing_rejection(migrated_postgres) -> None:
    """Verifies that PostgreSQL enforces fencing generations when leases expire and jobs are reclaimed."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)
    run_id = f"test-pg-fence-{uuid.uuid4().hex[:8]}"

    migrated_postgres.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": {"corruptions": [{"kind": "blur", "severity": 1}]},
        "created_at": stale_time,
        "updated_at": stale_time,
    })

    # Worker A claims
    worker_a = f"worker-a-{uuid.uuid4().hex[:4]}"
    claimed_a = migrated_postgres.claim_next_queued_run(worker_id=worker_a, claimed_at=stale_time)
    assert claimed_a is not None
    assert claimed_a["attempt_count"] == 1

    # Lease expires, recovery requeues
    rec = migrated_postgres.recover_stale_runs(now=now, lease_timeout_seconds=60.0, max_attempts=3)
    assert rec["recovered"] == 1

    # Worker B claims
    worker_b = f"worker-b-{uuid.uuid4().hex[:4]}"
    claimed_b = migrated_postgres.claim_next_queued_run(worker_id=worker_b, claimed_at=now)
    assert claimed_b is not None
    assert claimed_b["attempt_count"] == 2

    # Worker A mutations must fail
    assert migrated_postgres.heartbeat_run(run_id, heartbeat_at=now, worker_id=worker_a, attempt_count=1) is False

    dummy_report = {
        "run_id": run_id,
        "status": "COMPLETED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "created_at": now.isoformat(),
        "summary": {},
        "conditions": [],
        "metric_definitions": {},
        "limitations": [],
    }
    with pytest.raises(ValueError, match="report persistence rejected"):
        migrated_postgres.persist_report(run_id, dummy_report, now, worker_id=worker_a, attempt_count=1)

    with pytest.raises(ValueError, match="cannot be completed by worker"):
        migrated_postgres.complete_run(run_id, dummy_report, "COMPLETED", now, worker_id=worker_a, attempt_count=1)

    with pytest.raises(ValueError, match="cannot be failed by worker"):
        migrated_postgres.fail_run(run_id, "Stale worker failure", now, worker_id=worker_a, attempt_count=1)

    # Worker B completes cleanly
    migrated_postgres.complete_run(run_id, dummy_report, "COMPLETED", now, worker_id=worker_b, attempt_count=2)
    fin = migrated_postgres.get_run(run_id)
    assert fin["status"] == "COMPLETED"

