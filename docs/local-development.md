# VisionGuard Local Development Guide

This guide describes how to run and develop the VisionGuard backend and ML evaluator locally.

---

## Prerequisites

- **OS:** Windows 10/11 or Linux
- **Python:** Python 3.12 (e.g. 3.12.10)
- **Virtual Environment:** Recommended `.venv-gpu`
- **Hardware:**
  - GPU: NVIDIA GPU with CUDA 12.4 support (e.g. RTX 3050 6GB)
  - CPU: Can also run in CPU-only mode for development and testing

---

## 1. Environment Setup

### 1.1 Python Virtual Environment
```powershell
python -m venv .venv-gpu
.\.venv-gpu\Scripts\Activate.ps1
```

### 1.2 Core API Dependencies
```powershell
pip install -r backend/requirements.txt
```

### 1.3 ML Evaluator Dependencies
For GPU acceleration with CUDA 12.4:
```powershell
pip install -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cu124
```

For CPU-only local development:
```powershell
pip install -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

---

## 2. Environment Configuration

Copy the example configuration:
```powershell
cp .env.example .env
```

Edit `.env`:
```ini
# PostgreSQL Database (e.g. Neon)
DATABASE_URL=postgresql://user:password@ep-example.neon.tech/neondb?sslmode=require

# CORS Configuration (comma-separated origins)
VISIONGUARD_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> **Security Note:** Never commit `.env` or check database credentials into Git.

---

## 3. Running the System

### Option A: Web API with In-Process Dispatcher (Default Dev Mode)
Starts the FastAPI server with in-process background worker execution:
```powershell
.\.venv-gpu\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Swagger UI will be available at `http://127.0.0.1:8000/docs`.

### Option B: Decoupled API + Independent Worker (Production Architecture)
Run the API and worker in separate terminal windows:

**Terminal 1 (API Server):**
```powershell
.\.venv-gpu\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 (Continuous Evaluation Worker):**
```powershell
.\.venv-gpu\Scripts\python -m backend.app.worker --poll --interval 2.0
```

**Run a single job manually:**
```powershell
.\.venv-gpu\Scripts\python -m backend.app.worker <RUN_ID>
```

---

## 4. Running Tests

Run the complete test suite:
```powershell
.\.venv-gpu\Scripts\pytest visionguard_contracts/tests backend/tests -v
```

Run specific test modules:
```powershell
# CORS test
.\.venv-gpu\Scripts\pytest backend/tests/test_cors.py -v

# Worker decoupling test
.\.venv-gpu\Scripts\pytest backend/tests/test_worker.py -v

# Image artifacts API test
.\.venv-gpu\Scripts\pytest backend/tests/test_artifacts.py -v

# Dataset listing API test
.\.venv-gpu\Scripts\pytest backend/tests/test_datasets.py -v
```
