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

## Shared evaluation contract

The backend imports the shared models and evaluator from
`visionguard_contracts\visionguard`. Run the API from the repository root so
the shared package is available. It calls
`visionguard.core.api:evaluate_run(config, run_id=...)`; `VISIONGUARD_EVALUATOR`
can override that import target if needed.

The shared evaluator currently returns a **fixture/demo report**. It validates
the `EvalConfig` but intentionally ignores most configuration values and
returns demo data; it is not a real model evaluation. Its report sets
`is_fixture: true`, which clients should display as demo data. The API validates
the returned value against `EvaluationReport`, requires the report's `run_id`
to match the backend-generated ID, and stores its JSON-compatible form.

`VISIONGUARD_SUPPORTED_MODELS` optionally provides comma-separated model IDs
for API-side validation. With no model registry configured, `/api/v1/models`
returns an empty list and no API-side model allowlist is applied.

## API contract

All routes except `/` and `/health` use the `/api/v1` prefix.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/api/v1/models` | Configured model IDs |
| `POST` | `/api/v1/runs` | Validate, persist, and queue an evaluation |
| `GET` | `/api/v1/runs` | List runs (`limit` 1-100, `offset` >= 0) |
| `GET` | `/api/v1/runs/{run_id}` | Run status and failure details |
| `GET` | `/api/v1/runs/{run_id}/report` | Valid terminal report JSON |

Create a run:

```http
POST /api/v1/runs
Content-Type: application/json
```

```json
{
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "corruptions": [
    {"kind": "blur", "severities": [2]},
    {"kind": "low_light", "severities": [2]}
  ],
  "seed": 42,
  "score_threshold": 0.5,
  "match_iou_threshold": 0.5,
  "max_images": null
}
```

The response is `202 Accepted` with the run's initial state:

```json
{
  "run_id": "a5aaf889-1cbd-4a8c-a36c-d3353649ee3c",
  "status": "QUEUED",
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "validation",
  "created_at": "2026-10-24T12:10:00+00:00",
  "started_at": null,
  "finished_at": null,
  "error_message": null
}
```

Poll `GET /api/v1/runs/{run_id}` for `QUEUED`, `RUNNING`, `COMPLETED`,
`PARTIAL`, or `FAILED`. Reports with any terminal status are stored and
retrievable, including valid `PARTIAL` and `FAILED` reports. An evaluator
exception or invalid report produces a `FAILED` run without a report. In that
case the report endpoint returns `409`. A report response is shown below as an abbreviated excerpt; the actual response contains the full `EvaluationReport` contract:

```json
{
  "run_id": "a5aaf889-1cbd-4a8c-a36c-d3353649ee3c",
  "created_at": "2026-10-24T12:10:03+00:00",
  "report": {
    "is_fixture": true,
    "run_id": "a5aaf889-1cbd-4a8c-a36c-d3353649ee3c",
    "status": "COMPLETED"
  }
}
```

Invalid bodies and unsupported configured model IDs return `422`. Unknown run
IDs return `404`. A report requested before a terminal report is available
returns `409`. Safe run-level error messages summarize evaluation failures;
structured details from valid partial/failed reports are available in the
report response. Reports are stored as JSON in SQLite.
On application startup, runs left queued or running by a previous process are
marked `FAILED`; their error message indicates that the backend restarted.

## Tests

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m pytest .\visionguard_contracts\tests .\backend\tests -v
```

Tests inject mocked evaluator results and use temporary SQLite databases; they
do not download models or require GPU access.
