# VisionGuard Backend & ML Integration

VisionGuard is a model robustness and evaluation platform designed to systematically measure object detection performance under adverse conditions and image corruptions (such as blur, low light, and noise).

The backend is built with FastAPI, persists evaluation runs and reports to PostgreSQL (with Neon Serverless PostgreSQL recommended for production), and directly invokes the VisionGuard ML pipeline on GPU/CUDA or CPU.

---

## Architecture Overview

```
VisionGuard Repository
├── backend/
│   ├── app/                      # FastAPI application
│   │   ├── main.py               # API routes, lifecycle, background execution
│   │   ├── database.py           # SQLAlchemy engine, schema, transactional queries
│   │   ├── evaluation_adapter.py # Dynamic evaluator loader (pipeline vs test fixture)
│   │   ├── schemas.py            # API request & response schemas
│   │   └── contracts.py          # Re-exports canonical contracts
│   ├── visionguard/core/         # ML Evaluation Engine
│   │   ├── pipeline.py           # evaluate_run(), dataset loader & reporter
│   │   ├── model_adapter.py      # TorchvisionDetector (Faster R-CNN ResNet-50 FPN)
│   │   ├── corruptions.py        # Image corruption implementations
│   │   ├── matching.py           # Hungarian matching between clean and corrupted
│   │   └── metrics.py            # Metric calculation & aggregation
│   ├── demo_data/                # Bundled demo datasets (visionguard_demo)
│   ├── migrations/               # Alembic PostgreSQL database migrations
│   └── tests/                    # API and ML test suites
├── visionguard_contracts/        # Shared Pydantic data contracts
│   ├── visionguard/core/types.py # EvalConfig, EvaluationReport, MetricSet, RunStatus
│   └── tests/                    # Contract validation test suite
└── .venv-gpu/                    # PyTorch + CUDA virtual environment (local, git-ignored)
```

---

## Environment Setup

### 1. Python & GPU Environment

The recommended environment is Python 3.12 with PyTorch configured for CUDA:

```powershell
# Verify Python version and GPU availability
.\.venv-gpu\Scripts\python.exe --version
.\.venv-gpu\Scripts\python.exe -c "import torch; print('PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

Install backend dependencies:

```powershell
.\.venv-gpu\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

### 2. Required Environment Variables

Configure environment variables via `.env` in the repository root or in your environment:

```env
# Database connection (PostgreSQL with TLS required)
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require

# Evaluator entry point (defaults to real ML engine)
VISIONGUARD_EVALUATOR=backend.visionguard.core.pipeline:evaluate_run

# Optional: Supported model identifiers (comma-separated)
VISIONGUARD_SUPPORTED_MODELS=fasterrcnn_resnet50_fpn,fasterrcnn_resnet50_fpn_v2

# Optional: Dedicated read-only test database URL for postgres connectivity tests
# TEST_DATABASE_URL=postgresql+psycopg://TEST_USER:TEST_PASSWORD@TEST_HOST/TEST_DB?sslmode=require
```

> **Security Note:** Never commit `.env` or paste actual connection strings into chat, logs, or commit messages. `.env` is ignored by Git.

---

## Database Setup & Migrations

The production database is PostgreSQL (Neon Serverless PostgreSQL). SQLite is reserved exclusively for isolated automated unit tests and is never used as an automatic fallback in production.

### Running Migrations

Alembic manages migrations in `backend/migrations/versions`. Run from the repository root:

```powershell
.\.venv-gpu\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
```

- Migrations are data-preserving and transactional.
- Existing compatible tables are retained.
- Incompatible schemas will abort before altering tables.
- Before running migrations on production Neon databases, always verify connectivity and back up or branch the database in the Neon Console.

---

## Starting the FastAPI Server

Start the API with Uvicorn:

```powershell
.\.venv-gpu\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service health status string |
| `GET` | `/health` | API and database connectivity check |
| `GET` | `/api/v1/models` | List supported model IDs |
| `POST` | `/api/v1/runs` | Submit and queue an evaluation run (`202 Accepted`) |
| `GET` | `/api/v1/runs` | List evaluation runs (supports `limit` and `offset`) |
| `GET` | `/api/v1/runs/{run_id}` | Get status and metadata of a specific run |
| `GET` | `/api/v1/runs/{run_id}/report` | Retrieve the full terminal `EvaluationReport` |

---

## Running Evaluations

### Submitting a Demo Evaluation via API

Submit a run using the bundled `visionguard_demo` dataset:

```http
POST /api/v1/runs
Content-Type: application/json

{
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "corruptions": [
    {
      "kind": "blur",
      "severities": [1, 2]
    }
  ],
  "seed": 42,
  "score_threshold": 0.5,
  "match_iou_threshold": 0.5,
  "max_images": 5
}
```

Response (`202 Accepted`):
```json
{
  "run_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "QUEUED",
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "created_at": "2026-10-25T14:41:15Z"
}
```

The evaluation runs asynchronously in the background. Check `/api/v1/runs/{run_id}` until `status` transitions to `COMPLETED`, then fetch `/api/v1/runs/{run_id}/report`.

---

## Running Tests

All unit tests run without requiring a real database, model weights downloads, or GPU access:

```powershell
# Run all tests across contracts and backend
.\.venv-gpu\Scripts\python.exe -m pytest visionguard_contracts/tests backend/tests -v

# Run only contract tests
.\.venv-gpu\Scripts\python.exe -m pytest visionguard_contracts/tests -v

# Run only ML unit tests
.\.venv-gpu\Scripts\python.exe -m pytest backend/tests/test_matching.py backend/tests/test_pipeline.py backend/tests/test_edge_cases.py backend/tests/test_demo_dataset.py -v

# Run only backend API tests (uses in-memory/temp SQLite)
.\.venv-gpu\Scripts\python.exe -m pytest backend/tests/test_api.py -v
```

---

## Current Limitations & Notes

1. **Dataset Registration:**
   - The initial release supports the bundled `visionguard_demo` dataset located at `backend/demo_data/visionguard_demo`.
   - Arbitrary filesystem path ingestion via API is explicitly disabled for security.
   - Additional datasets must be registered on the server using `backend.visionguard.core.pipeline.register_dataset(dataset_id, root_path)`. Arbitrary multipart file upload for custom datasets is planned for a future release.

2. **Supported Models:**
   - Pre-trained Faster R-CNN with ResNet-50 FPN from `torchvision`:
     - `fasterrcnn_resnet50_fpn`
     - `fasterrcnn_resnet50_fpn_v2`
   - Additional architectures can be integrated by extending `backend.visionguard.core.model_adapter.DetectorAdapter`.
