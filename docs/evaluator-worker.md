# VisionGuard Evaluator Worker

## Overview

The evaluation worker executes deep learning model inference and corruption benchmarking independently from the FastAPI web server.

```
+----------------+          INSERT run          +-------------------+
|  FastAPI App   | ---------------------------> |  PostgreSQL/Neon  |
|                |                              |   (status=QUEUED) |
+-------+--------+                              +---------+---------+
        |                                                 |
        | submits run_id                                  |
        v                                                 |
+----------------+      SELECT WHERE status=QUEUED        |
| Evaluation     | <--------------------------------------+
| Worker         |
|                | ---- UPDATE status=RUNNING ---------> [Database]
|                | ---- Run ML pipeline (PyTorch) -----> [GPU / CUDA]
|                | ---- INSERT report -----------------> [Database]
|                | ---- UPDATE status=COMPLETED -------> [Database]
+----------------+
```

---

## Worker Responsibilities

1. **State Isolation:** Decouples memory-intensive PyTorch GPU models from the lightweight HTTP server process.
2. **Atomic Run Claiming:**
   - Worker uses an atomic conditional update:
     `UPDATE runs SET status='RUNNING', started_at=:now WHERE run_id=:id AND status='QUEUED'`
   - Ensures that exactly one worker acquires the run even under concurrent execution.
3. **Execution & Evaluation:**
   - Hydrates run configuration from database JSON.
   - Executes `evaluate_run()` from `backend.visionguard.core.pipeline`.
4. **Resilient Failure Handling:**
   - If evaluation throws an exception, the worker transitions the run status to `FAILED`.
   - Records sanitized error diagnostics in `runs.error_message` without leaking environment paths or secrets.
   - Prevents runs from remaining perpetually in `RUNNING` status.

---

## Worker CLI Usage

### Process a Single Run
```powershell
python -m backend.app.worker <run_id>
```
Exits with:
- `0`: Run successfully executed and marked `COMPLETED`.
- `1`: Run failed, was already claimed, or encountered an unhandled exception.

### Run in Continuous Polling Mode
```powershell
python -m backend.app.worker --poll --interval 2.0
```
- Checks the database every `interval` seconds for `QUEUED` runs.
- Executes them sequentially.
- Gracefully terminates on `Ctrl+C` (SIGINT/SIGTERM).

---

## Future Queue & Distributed Worker Evolution

The current implementation uses a database-backed state machine with `JobDispatcher` protocol. This provides a clean upgrade path without altering API contracts or evaluator logic:

1. **Phase 1 (Current):** Database-backed job queue with `BackgroundTasksDispatcher` or CLI worker polling.
2. **Phase 2 (Cloud GPU Worker):** Replace polling with a distributed message broker (e.g. AWS SQS, Celery, or Redis Streams). The API dispatcher simply pushes `{run_id}` to the message queue, and the remote GPU worker invokes `execute_evaluation_job(run_id)`.
3. **Zero Frontend Impact:** Because the frontend polls `GET /api/v1/runs/{run_id}` against the shared PostgreSQL database, worker architecture changes are completely transparent to clients.
