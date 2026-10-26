# VisionGuard Architecture

## System Overview

VisionGuard is an automated ML model reliability and robustness evaluation platform. It evaluates object detection models against systematic image corruptions (noise, blur, weather, lighting) and quantifies performance degradation against clean benchmarks.

```
                      +-----------------------------+
                      | React Frontend (Vite/TS)    |
                      | (http://localhost:5173)     |
                      +--------------+--------------+
                                     |
                                REST API
                                (CORS scoped)
                                     v
                      +-----------------------------+
                      | FastAPI Backend             |
                      | (/api/v1/...)               |
                      +--------------+--------------+
                                     |
                                     | submits run_id
                                     v
                      +-----------------------------+
                      | Job Execution Abstraction   |
                      | (JobDispatcher Interface)   |
                      +--------------+--------------+
                                     |
                  +------------------+------------------+
                  |                                     |
                  v                                     v
+----------------------------------+   +----------------------------------+
| API In-Process Dispatcher        |   | Standalone Evaluation Worker     |
| (BackgroundTasksDispatcher)      |   | (backend.app.worker / GPU node)  |
+-----------------+----------------+   +-----------------+----------------+
                  |                                     |
                  +------------------+------------------+
                                     |
                                     v
                      +-----------------------------+
                      | ML Pipeline (evaluate_run)  |
                      | - Torchvision Faster R-CNN  |
                      | - Corruption Engine         |
                      | - Metrics & Matcher Engine  |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      | Persistence Layer           |
                      | Neon PostgreSQL / SQLite    |
                      | (runs, reports tables)      |
                      +-----------------------------+
```

---

## Core Components

### 1. API Service (`backend.app`)
- **Framework:** FastAPI with Pydantic v2 schemas.
- **Role:** Handles client requests, schema validation, run submission, artifact serving, dataset listing, run status tracking, and report retrieval.
- **Decoupled Execution:** The API request handler does **not** run GPU or model inference directly. Instead, it validates requests against the registered dataset/model catalog, records the run in database status `QUEUED`, and dispatches the `run_id` via the `JobDispatcher` abstraction.

### 2. Job Dispatcher Abstraction (`backend.app.execution`)
- **Protocol:** `JobDispatcher.dispatch_run(run_id: str) -> None`
- **Default Implementation:** `BackgroundTasksDispatcher` wraps FastAPI's asynchronous background tasks for lightweight development.
- **Worker Function:** `execute_evaluation_job(run_id: str, db: RunDatabase, evaluator: Callable)` encapsulates the complete run lifecycle:
  1. Atomic transition `QUEUED -> RUNNING` (with row-level concurrency lock to prevent duplicate execution).
  2. Configuration hydration and validation from database records.
  3. Execution of the ML pipeline (`evaluate_run`).
  4. Atomic transition `RUNNING -> COMPLETED` (or `FAILED` upon exception) with report persistence and sanitized error messages.

### 3. Standalone Evaluator Worker (`backend.app.worker`)
- **CLI Entrypoint:** `python -m backend.app.worker [run_id | --poll]`
- **Modes:**
  - **Single Run:** Processes a specified `run_id` and exits with code 0 on success or 1 on failure.
  - **Polling Daemon:** Repeatedly queries the database for `QUEUED` runs and processes them sequentially with configurable polling intervals (`--interval`).
- **Future Scalability:** Enables running GPU-intensive inference on dedicated GPU worker machines separate from the web API server, reading from the same shared database without code changes.

### 4. ML Evaluation Pipeline (`backend.visionguard.core.pipeline`)
- **Models:** Torchvision Faster R-CNN ResNet-50 FPN and Faster R-CNN ResNet-50 FPN v2.
- **Registered Datasets:** `visionguard_demo` (registered with ground truth annotations in COCO format).
- **Corruptions:** Synthetic image degradations (Gaussian noise, motion blur, contrast, brightness, fog, frost).
- **Contracts:** Validated against `visionguard_contracts` specification v1.0.0.

### 5. Persistence Layer (`backend.app.database`)
- **Engines:** Neon PostgreSQL (cloud production) and SQLite (local testing / in-memory fixtures).
- **Tables:**
  - `runs`: Run metadata, configuration JSON, execution status (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`), timestamps, and error messages.
  - `reports`: Full evaluation reports stored in JSON format matching contract schema v1.0.0.
  - `alembic_version`: Tracks migration history (`20261025_01`).
