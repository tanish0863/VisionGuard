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
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import signal
import sys
import threading
import time
from typing import Any
from uuid import uuid4

from backend.app.database import RunDatabase
from backend.app.execution import execute_evaluation_job, utc_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("visionguard.worker")

_shutdown_requested = False


class WorkerHealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to satisfy Hugging Face Docker Spaces health checks."""

    server_version = "VisionGuardWorker/1.0"

    def do_GET(self) -> None:
        if self.path in ("/", "/health", "/healthz"):
            wid = getattr(self.server, "worker_id", "unknown")
            started_at = getattr(self.server, "started_at", None)
            uptime = time.time() - started_at if started_at else 0
            payload = {
                "status": "healthy",
                "service": "visionguard-worker",
                "worker_id": wid,
                "uptime_seconds": round(uptime, 1),
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self) -> None:
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("Worker HTTP: " + format, *args)


def start_worker_health_server(
    port: int = 7860,
    worker_id: str = "worker",
) -> HTTPServer | None:
    """Start lightweight HTTP health server in a daemon thread.

    Compatible with Hugging Face Docker Spaces on port 7860.
    """
    try:
        server = HTTPServer(("0.0.0.0", port), WorkerHealthHandler)
        setattr(server, "worker_id", worker_id)
        setattr(server, "started_at", time.time())
        thread = threading.Thread(
            target=server.serve_forever,
            name="WorkerHealthServerThread",
            daemon=True,
        )
        thread.start()
        logger.info(
            "Worker health server listening on http://0.0.0.0:%d (Hugging Face Spaces ready)",
            port,
        )
        return server
    except Exception as exc:
        logger.warning(
            "Could not start worker health server on port %d: %s", port, exc
        )
        return None



def _handle_shutdown(signum: int, frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("Shutdown signal %s received; gracefully terminating worker polling loop...", signum)


try:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
except (ValueError, AttributeError):
    # Signals might not be settable in certain non-main-thread contexts
    pass


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
    health_port: int | None = 7860,
) -> None:
    """Continuously poll the database for QUEUED runs and execute them."""
    db = database or RunDatabase.from_environment()
    wid = worker_id or f"worker-poll-{uuid4().hex[:8]}"
    health_server: HTTPServer | None = None
    if health_port and health_port > 0:
        health_server = start_worker_health_server(port=health_port, worker_id=wid)

    logger.info("Starting worker '%s' polling loop (interval=%.1fs, lease_timeout=%.1fs, max_attempts=%d)... Press Ctrl+C or send SIGTERM to stop.", wid, interval, lease_timeout, max_attempts)
    poll_count = 0
    try:
        while not _shutdown_requested:
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
                    sleep_remaining = interval
                    while sleep_remaining > 0 and not _shutdown_requested:
                        slice_time = min(0.2, sleep_remaining)
                        time.sleep(slice_time)
                        sleep_remaining -= slice_time
            except KeyboardInterrupt:
                logger.info("Worker polling loop stopped by user.")
                break
            except Exception:
                logger.exception("Unexpected error in worker polling loop; retrying in %.1fs", interval)
                time.sleep(interval)
        if _shutdown_requested:
            logger.info("Worker '%s' gracefully stopped after receiving shutdown signal.", wid)
    finally:
        if health_server is not None:
            try:
                health_server.shutdown()
            except Exception:
                pass
        if database is None:
            db.dispose()


def main() -> None:
    env_interval = float(os.getenv("VISIONGUARD_POLL_INTERVAL", "2.0"))
    env_lease_timeout = float(os.getenv("VISIONGUARD_LEASE_TIMEOUT_SECONDS", "60.0"))
    env_max_attempts = int(os.getenv("VISIONGUARD_MAX_ATTEMPTS", "3"))
    env_worker_id = os.getenv("VISIONGUARD_WORKER_ID")
    env_health_port = int(os.getenv("PORT", os.getenv("VISIONGUARD_HEALTH_PORT", "7860")))

    parser = argparse.ArgumentParser(description="VisionGuard Evaluation Worker")
    parser.add_argument("run_id", nargs="?", help="Specific run_id to process")
    parser.add_argument("--poll", action="store_true", help="Poll database for queued runs")
    parser.add_argument("--interval", type=float, default=env_interval, help="Polling interval in seconds")
    parser.add_argument("--worker-id", type=str, default=env_worker_id, help="Explicit worker identifier")
    parser.add_argument("--lease-timeout", type=float, default=env_lease_timeout, help="Lease timeout in seconds")
    parser.add_argument("--max-attempts", type=int, default=env_max_attempts, help="Max retry attempts for failed/stale runs")
    parser.add_argument("--health-port", type=int, default=env_health_port, help="HTTP health check port for Hugging Face Spaces (default: 7860 or PORT)")
    parser.add_argument("--no-health-server", action="store_true", help="Disable the background HTTP health server")

    args = parser.parse_args()

    resolved_health_port = None if args.no_health_server else args.health_port

    if args.poll:
        poll_and_process_runs(
            interval=args.interval,
            worker_id=args.worker_id,
            lease_timeout=args.lease_timeout,
            max_attempts=args.max_attempts,
            health_port=resolved_health_port,
        )
    elif args.run_id:
        exit_code = process_single_run(args.run_id, worker_id=args.worker_id)
        sys.exit(exit_code)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

