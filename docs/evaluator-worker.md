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

---

## Docker Worker Specifications & Staging Verification

### Container Runtime Specification
- **Base Image:** `nvidia/cuda:12.4.1-runtime-ubuntu22.04` (with `ARG BASE_IMAGE` parameterization)
- **Python:** 3.12 (PPA `deadsnakes/ppa`)
- **PyTorch:** `torch==2.6.0+cu124`
- **Torchvision:** `torchvision==0.21.0+cu124`
- **Wheel Index:** `https://download.pytorch.org/whl/cu124`
- **Healthcheck:** Port `7860` (`curl -f http://localhost:${PORT:-7860}/health || exit 1`)
- **Execution User:** `appuser` (UID 1000, non-root)

### Dependency Separation
- Backend API dependencies (`fastapi`, `uvicorn`, `pytest`, `httpx`) are isolated in `backend/requirements.txt` and excluded from the ML worker.
- Worker ML and storage requirements are self-contained in `backend/requirements-ml.txt` (`torch`, `torchvision`, `numpy`, `pillow`, `opencv-python-headless`, `scipy`, `pydantic`, `boto3`, `botocore`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `python-dotenv`).

### Building for Staging
1. **Local Build (Reusing Cached GPU Base):**
   ```powershell
   docker build --progress=plain --build-arg BASE_IMAGE=visionguard-worker:latest -f Dockerfile.worker -t visionguard-worker:test-staging .
   ```
2. **Cloud / Hugging Face Spaces Build (From Upstream CUDA):**
   ```powershell
   docker build --progress=plain -f Dockerfile.worker -t visionguard-worker:test-staging .
   ```

### Verifying the Staging Worker Image
```powershell
# Verify image metadata and non-root user
docker image inspect visionguard-worker:test-staging --format "ID={{.Id}} Size={{.Size}} User={{.Config.User}}"

# Verify Python, PyTorch, Torchvision, and CUDA availability in isolation
docker run --rm visionguard-worker:test-staging python -c "import torch, torchvision; print('Torch:', torch.__version__, 'CUDA:', torch.version.cuda, 'Torchvision:', torchvision.__version__)"

# Verify worker entrypoint help
docker run --rm visionguard-worker:test-staging python -m backend.app.worker --help
```

### Storage & RAM Considerations
- Extracting CUDA 12.4 + PyTorch wheels unpacks ~12 GB of uncompressed binaries.
- Ensure the Docker host disk has at least 25 GB of free space and 4+ GB of free memory before performing fresh builds from `nvidia/cuda`.
- For Docker Desktop on WSL2, verify the actual WSL VHDX drive (`CustomWslDistroDir`) has sufficient free space.
