# VisionGuard backend

## Run locally

From the repository root, install the backend dependencies and start the API:

```powershell
python -m pip install -r backend\requirements.txt
uvicorn backend.app.main:app --reload
```

The interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.
The SQLite database defaults to `backend\visionguard.sqlite3`; override it with
`VISIONGUARD_DATABASE_PATH` only if a different location is needed.

## Evaluation integration

The API expects a synchronous Python function named `evaluate_run(config)` that
returns a JSON object. Configure its import path with
`VISIONGUARD_EVALUATOR=package.module:evaluate_run`; the default is
`ml.evaluation:evaluate_run`. The adapter imports the ML module only when a run
starts, so the API and mocked tests do not require model weights or a GPU.

`VISIONGUARD_SUPPORTED_MODELS` optionally provides a comma-separated list of
model IDs. When set, run requests are limited to those IDs. With no registry
configured, `/api/v1/models` reports an empty list and model IDs are passed to
the evaluator without an API-side allowlist.

## API contract

All routes except `/` and `/health` use the `/api/v1` prefix.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/api/v1/models` | Configured model IDs |
| `POST` | `/api/v1/runs` | Validate, persist, and queue an evaluation |
| `GET` | `/api/v1/runs` | List runs (`limit` 1-100, `offset` >= 0) |
| `GET` | `/api/v1/runs/{run_id}` | Run status and failure details |
| `GET` | `/api/v1/runs/{run_id}/report` | Completed report JSON |

Create a run:

```http
POST /api/v1/runs
Content-Type: application/json
```

```json
{
  "model_id": "yolov8n",
  "dataset_id": "validation",
  "parameters": {
    "corruption": "gaussian_blur",
    "severity": 2
  }
}
```

The response is `202 Accepted` with the run's initial state:

```json
{
  "run_id": "a5aaf889-1cbd-4a8c-a36c-d3353649ee3c",
  "status": "QUEUED",
  "model_id": "yolov8n",
  "dataset_id": "validation",
  "created_at": "2026-10-24T12:10:00+00:00",
  "started_at": null,
  "finished_at": null,
  "error_message": null
}
```

Poll `GET /api/v1/runs/{run_id}` for `QUEUED`, `RUNNING`, `COMPLETED`, or
`FAILED`. A successful report response is:

```json
{
  "run_id": "a5aaf889-1cbd-4a8c-a36c-d3353649ee3c",
  "created_at": "2026-10-24T12:10:03+00:00",
  "report": {
    "metrics": {
      "map50": 0.81
    },
    "samples": 12
  }
}
```

Invalid bodies and unsupported configured model IDs return `422`. Unknown run
IDs return `404`. A report requested before successful completion, or for a
failed run, returns `409`; the run's `error_message` explains evaluation
failures. Reports are stored as JSON in SQLite.
On application startup, runs left queued or running by a previous process are
marked `FAILED`; their error message indicates that the backend restarted.

## Tests

From the repository root, run:

```powershell
python -m pytest backend\tests
```

Tests inject a mocked evaluator and use temporary SQLite databases; they do not
download models or require GPU access.
