# VisionGuard — Computer Vision Model Reliability & Benchmarking Platform

VisionGuard evaluates computer vision models against synthetic real-world corruptions (e.g., weather, optical, sensor noise), computing mAP retention, detection failure diagnostics, and confusion matrices.

---

## 1. Architecture Overview

- **Frontend:** React 19, TanStack Start, Tailwind CSS, Lucide icons, Recharts (`frontend/`)
- **Backend API Gateway:** FastAPI, Pydantic, SQLAlchemy 2.0 (`backend/app/main.py`)
- **Evaluation Worker:** PyTorch 2.6.0+cu124, Torchvision, CUDA 12.4, Faster R-CNN (`backend/app/worker.py`)
- **Database:** PostgreSQL (Neon) with atomic `SKIP LOCKED` job claiming and lease fencing
- **Artifact Storage:** Backblaze B2 (S3-compatible) distributed object storage
- **Container Infrastructure:** Multi-service Docker Compose (`docker-compose.yml`), dedicated GPU worker Dockerfile (`Dockerfile.worker`)

---

## 2. Frontend Application & Pages

- `/` — Interactive animated 3D landing page with VisionGuard branding and feature highlights
- `/login` & `/signup` — Authentication and user profile management
- `/dashboard` — Model Reliability Overview, recent runs, gate verdicts, and mean retention metrics
- `/new` — Evaluation configuration, corruption parameter selection, live image preview, and run submission
- `/runs/$id` — Run details, status polling, mAP degradation curves, metrics breakdown, and artifact downloads
- `/runs/$id/failures` — Visual failure inspection and missed detection diagnostics
- `/settings` — System configuration, preset thresholds, and metric glossary

---

## 3. Quick Start

### Option A: Docker Compose (Recommended)
Run the complete stack (Frontend, API, and Worker):
```powershell
docker compose up -d
```
- **Web App:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

### Option B: Local Development

#### 1. Backend & Worker (Python 3.12)
```powershell
pip install -r backend/requirements.txt -r backend/requirements-ml.txt
uvicorn backend.app.main:app --reload --port 8000
python -m backend.app.worker --poll --interval 2.0
```

#### 2. Frontend (Node / Bun)
```powershell
cd frontend
npm install
npm run dev
```

---

## 4. Testing & Verification

- **Backend Unit & Artifact Tests:** `pytest backend/tests/test_api.py backend/tests/test_artifacts.py`
- **PostgreSQL Integration Tests:** `pytest backend/tests/test_postgres_integration.py`
- **Frontend Tests:** `npm test` (inside `frontend/`)
