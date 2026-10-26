"""Standalone CLI worker for VisionGuard evaluation jobs.

Allows running evaluation workers in a completely separate process or machine
from the FastAPI API server.

Usage:
    # Process a single specific run:
    python -m backend.app.worker <run_id>

    # Poll database continuously for QUEUED runs:
    python -m backend.app.worker --poll --interval 2.0
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from uuid import uuid4

from backend.app.database import RunDatabase
from backend.app.execution import execute_evaluation_job, utc_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("visionguard.worker")


def process_single_run(
    run_id: str,
    database: RunDatabase | None = None,
    worker_id: str | None = None,
) -> int:
    """Process a single run_id."""
    db = database or RunDatabase.from_environment()
    wid = worker_id or f"worker-cli-{uuid4().hex[:8]}"
    try:
        result = execute_evaluation_job(run_id, db, worker_id=wid)
        logger.info("Result for %s (worker=%s): success=%s status=%s", run_id, wid, result.success, result.status)
        return 0 if result.success else 1
    finally:
        if database is None:
            db.dispose()


def poll_and_process_runs(
    interval: float = 2.0,
    database: RunDatabase | None = None,
    worker_id: str | None = None,
    lease_timeout: float = 60.0,
    max_attempts: int = 3,
) -> None:
    """Continuously poll the database for QUEUED runs and execute them."""
    db = database or RunDatabase.from_environment()
    wid = worker_id or f"worker-poll-{uuid4().hex[:8]}"
    logger.info("Starting worker '%s' polling loop (interval=%.1fs, lease_timeout=%.1fs)... Press Ctrl+C to stop.", wid, interval, lease_timeout)
    poll_count = 0
    try:
        while True:
            poll_count += 1
            # Periodically sweep for stale runs (every 5 polls)
            if poll_count % 5 == 0:
                try:
                    recovery_res = db.recover_stale_runs(
                        now=utc_now(),
                        lease_timeout_seconds=lease_timeout,
                        max_attempts=max_attempts,
                    )
                    if recovery_res["recovered"] > 0 or recovery_res["failed"] > 0:
                        logger.info("Stale run recovery sweep: %s", recovery_res)
                except Exception:
                    logger.debug("Stale run recovery sweep encountered an exception", exc_info=True)

            try:
                claimed = db.claim_next_queued_run(worker_id=wid, claimed_at=utc_now())
                if claimed:
                    run_id = claimed["run_id"]
                    logger.info("Worker '%s' claimed queued run: %s", wid, run_id)
                    # Run execution with lease management
                    execute_evaluation_job(run_id, db, worker_id=wid)
                else:
                    time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Worker polling loop stopped by user.")
                break
            except Exception:
                logger.exception("Unexpected error in worker polling loop; retrying in %.1fs", interval)
                time.sleep(interval)
    finally:
        if database is None:
            db.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="VisionGuard Evaluation Worker")
    parser.add_argument("run_id", nargs="?", help="Specific run_id to process")
    parser.add_argument("--poll", action="store_true", help="Poll database for queued runs")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--worker-id", type=str, default=None, help="Explicit worker identifier")
    parser.add_argument("--lease-timeout", type=float, default=60.0, help="Lease timeout in seconds")

    args = parser.parse_args()

    if args.poll:
        poll_and_process_runs(
            interval=args.interval,
            worker_id=args.worker_id,
            lease_timeout=args.lease_timeout,
        )
    elif args.run_id:
        exit_code = process_single_run(args.run_id, worker_id=args.worker_id)
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

