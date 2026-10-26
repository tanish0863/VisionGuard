# VisionGuard Production Deployment Guide

## 1. Production Architecture Overview

The VisionGuard production architecture separates the client interface, API gateway, ML inference workers, database store, and artifact storage:

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT TIER                                      |
|   React 19 + TanStack Router SPA (Vercel / Cloudflare Pages / AWS S3 + CloudFront)|
+-----------------------------------------------------------------------------------+
                                         |
                                         | HTTPS / REST (JSON)
                                         v
+-----------------------------------------------------------------------------------+
|                                  API GATEWAY                                      |
|   FastAPI on Python 3.12 (AWS ECS / GCP Cloud Run / Render / Fly.io)              |
|   Config: VISIONGUARD_DISPATCHER=worker, pool_pre_ping=True                       |
+-----------------------------------------------------------------------------------+
                    |                                         |
         JSON / SQL | (TLS sslmode=require)        Persistent | Read / Stream
                    v                               Artifacts | (PNG / JPG)
+----------------------------------------+                    v
|           DATABASE TIER                |     +------------------------------------+
|  Neon Serverless PostgreSQL            |     |        ARTIFACT STORE              |
|  Tables: runs, reports (JSONB)         |     |  AWS S3 / Cloudflare R2 / Disk     |
+----------------------------------------+     +------------------------------------+
                    ^                                         ^
                    | (Job Lease & Heartbeat)                 | Write Corrupted Images
+-----------------------------------------------------------------------------------+
|                                ML WORKER TIER                                     |
|   GPU-enabled Worker Process (RunPod / Lambda Labs / AWS EC2 g5 / GCP A2)         |
|   Hardware: NVIDIA GPU (CUDA 12.4+, >=6GB VRAM, e.g. T4, RTX 3050/4090, A10G)     |
|   Command: python -m backend.app.worker --poll --interval 2.0                     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Infrastructure Requirements & Estimated Costs

> **Note:** Infrastructure costs are estimates based on standard on-demand cloud pricing as of 2026.

| Tier | Component | Recommended Provider | Specs | Estimated Cost |
|---|---|---|---|---|
| **Frontend** | Static SPA | Cloudflare Pages / Vercel | Global CDN, Edge SSR | $0 - $20 / month |
| **API Server** | FastAPI Gateway | GCP Cloud Run / AWS ECS Fargate | 1-2 vCPU, 2GB RAM | $15 - $40 / month |
| **Database** | PostgreSQL | Neon Serverless | Autoscale 0.25 - 1 CU, TLS | $0 - $30 / month |
| **GPU Worker** | ML Evaluator | RunPod / Lambda Labs / AWS EC2 g5 | 1x NVIDIA GPU (8-16GB VRAM) | ~$0.20 - $0.70 / hour (spot/on-demand) |
| **Storage** | Image Artifacts | Cloudflare R2 / AWS S3 | Standard object storage | ~$0.015 / GB-month |

---

## 3. Environment Variables Reference

### Backend & Worker
- `DATABASE_URL`: PostgreSQL connection string with `sslmode=require` (e.g. `postgresql+psycopg://user:password@ep-xyz.neon.tech/neondb?sslmode=require`).
- `VISIONGUARD_DISPATCHER`: Execution mode. Set to `worker` for production, `background` for local development.
- `VISIONGUARD_CORS_ORIGINS`: Comma-separated allowed frontend domains (e.g. `https://visionguard.example.com`).
- `VISIONGUARD_LEASE_TIMEOUT_SECONDS`: Lease expiration duration before stale worker recovery (default `60`).
- `VISIONGUARD_MAX_ATTEMPTS`: Maximum bounded retry attempts for failed or crashed evaluations (default `3`).
- `VISIONGUARD_SUPPORTED_MODELS`: Comma-separated list of model architectures (e.g. `fasterrcnn_resnet50_fpn,fasterrcnn_resnet50_fpn_v2`).

### Frontend
- `VITE_API_BASE_URL`: Public HTTPS URL of the FastAPI gateway (e.g. `https://api.visionguard.example.com`).

---

## 4. Operational Checklist & Step-by-Step Runbook

### Step 1: Database Setup
1. Create a production branch on Neon PostgreSQL.
2. Configure `DATABASE_URL` in the secrets manager.
3. Apply database migrations to the latest revision:
   ```bash
   alembic -c backend/alembic.ini upgrade head
   ```

### Step 2: Deploy API Gateway
1. Build `Dockerfile.api`.
2. Configure environment variables (`DATABASE_URL`, `VISIONGUARD_DISPATCHER=worker`, `VISIONGUARD_CORS_ORIGINS`).
3. Verify readiness probe: `GET /health` returns `{"status":"healthy","database":"connected"}`.

### Step 3: Deploy GPU Evaluation Worker
1. Build `Dockerfile.worker` on a machine with NVIDIA Container Toolkit.
2. Start continuous worker daemon:
   ```bash
   python -m backend.app.worker --poll --interval 2.0
   ```
3. Verify GPU access via `nvidia-smi` within container.

### Step 4: Build & Deploy Frontend
1. Build static assets:
   ```bash
   cd frontend
   npm run build
   ```
2. Deploy `.output/public` to CDN / hosting provider.
3. Verify browser loads dashboard, connects to backend, and displays catalog.

---

## 5. Rollback Procedures
- **Frontend:** Instant rollback to previous immutable release hash on Cloudflare Pages / Vercel.
- **Backend API:** Revert container image tag to previous stable build.
- **Database:** Downward schema migrations are deliberately guarded to prevent accidental deletion of evaluation evidence. If a schema rollback is required, perform a reviewed non-destructive forward migration.
