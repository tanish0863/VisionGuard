# VisionGuard Production Deployment Runbook

Comprehensive, step-by-step operational guide for deploying VisionGuard across:
- **Neon**: PostgreSQL Database
- **Backblaze B2** (Primary) / **Cloudflare R2** (Alternative): S3-compatible Artifact Storage
- **Render**: FastAPI Backend Gateway
- **Hugging Face Spaces**: PyTorch ML Evaluation Worker (Docker Space)
- **Vercel**: TanStack Start / React Frontend

---

## 1. Architecture & Service Topology

```
+-----------------------------------------------------------------------------------------+
|                                    VERCEL (Frontend)                                    |
|   React 19 + TanStack Start SPA/SSR                                                     |
|   Build: npm run build | Output: .output/public                                         |
|   Public Env: VITE_API_BASE_URL=https://visionguard-api.onrender.com                    |
+-----------------------------------------------------------------------------------------+
                                             |
                         HTTPS REST API      | (CORS: Strict Origin Allowlist)
                                             v
+-----------------------------------------------------------------------------------------+
|                                     RENDER (Backend API)                                |
|   FastAPI Gateway (Docker: Dockerfile.api)                                              |
|   Entrypoint: exec uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT             |
|   Health Check Path: /health                                                            |
|   Env: VISIONGUARD_DISPATCHER=worker, VISIONGUARD_CORS_ORIGINS=https://<app>.vercel.app|
+-----------------------------------------------------------------------------------------+
           |                                                      |
           | TLS SQL Queries                                      | Read / Presign URLs
           v (sslmode=require)                                    v (Direct Stream)
+----------------------------------------+     +------------------------------------------+
|          NEON (PostgreSQL)             |     |       BACKBLAZE B2 PRIVATE BUCKET        |
|  Serverless Postgres (pooled & direct) |     |  Private Bucket: visionguard-artifacts   |
|  Tables: runs, reports, artifacts      |     |  Object Keys: runs/{run_id}/...          |
+----------------------------------------+     +------------------------------------------+
           ^                                                      ^
           | Atomic FOR UPDATE SKIP LOCKED                        | Upload Evaluation
           | Lease & Generation Fencing                           | Images & JSON Metrics
+-----------------------------------------------------------------------------------------+
|                              HUGGING FACE SPACES (ML Worker)                            |
|   Docker Space (Dockerfile.worker)                                                      |
|   Hardware: CPU Basic (Free) or T4 GPU (Hardware Upgrade)                               |
|   Health Server: http://0.0.0.0:7860/health (Port 7860 Required by HF)                  |
|   Worker Command: python -m backend.app.worker --poll --interval 2.0                    |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Platform Environment Variables Matrix

| Platform | Variable Name | Required | Example / Recommended Value | Description |
|---|---|---|---|---|
| **Neon** | *(None)* | — | — | Database credentials are used by Render & HF Spaces. |
| **Render** | `DATABASE_URL` | **Yes** | `postgresql+psycopg://user:pass@ep-xyz-pooler.neon.tech/neondb?sslmode=require` | Pooled Neon PostgreSQL connection string. |
| **Render** | `VISIONGUARD_DISPATCHER` | **Yes** | `worker` | Routes run execution to decoupled worker via Neon. |
| **Render** | `VISIONGUARD_CORS_ORIGINS` | **Yes** | `https://your-app.vercel.app` | Comma-separated allowed frontend production domains. |
| **Render** | `VISIONGUARD_STORAGE_BACKEND` | **Yes** | `b2` | S3-compatible cloud storage provider (`b2` or `r2`). |
| **Render** | `VISIONGUARD_STORAGE_BUCKET` | **Yes** | `visionguard-artifacts` | Bucket name for persistent artifacts (alias: `B2_BUCKET_NAME`). |
| **Render** | `VISIONGUARD_STORAGE_ENDPOINT` | **Yes** | `https://s3.us-east-005.backblazeb2.com` | B2 S3 API endpoint (alias: `B2_ENDPOINT_URL`). |
| **Render** | `VISIONGUARD_STORAGE_ACCESS_KEY_ID` | **Yes** | `<b2_key_id>` | B2 Application Key ID (alias: `B2_ACCESS_KEY_ID`). |
| **Render** | `VISIONGUARD_STORAGE_SECRET_ACCESS_KEY` | **Yes** | `<b2_application_key>` | B2 Application Secret Key (alias: `B2_SECRET_ACCESS_KEY`). |
| **Render** | `VISIONGUARD_STORAGE_REGION` | No | `us-east-005` | B2 storage region (alias: `B2_REGION`). |
| **HF Spaces**| `DATABASE_URL` | **Yes** | `postgresql+psycopg://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` | Direct or pooled Neon connection string. |
| **HF Spaces**| `PORT` | **Yes** | `7860` | Internal health check port (automatically set by HF). |
| **HF Spaces**| `VISIONGUARD_LEASE_TIMEOUT_SECONDS` | No | `60` | Lease duration before job is considered stale. |
| **HF Spaces**| `VISIONGUARD_MAX_ATTEMPTS` | No | `3` | Max retries for failed/crashed evaluations. |
| **HF Spaces**| `VISIONGUARD_STORAGE_BACKEND` | **Yes** | `b2` | Storage backend type. |
| **HF Spaces**| `VISIONGUARD_STORAGE_BUCKET` | **Yes** | `visionguard-artifacts` | B2 bucket name. |
| **HF Spaces**| `VISIONGUARD_STORAGE_ENDPOINT` | **Yes** | `https://s3.us-east-005.backblazeb2.com` | B2 S3 API endpoint. |
| **HF Spaces**| `VISIONGUARD_STORAGE_ACCESS_KEY_ID` | **Yes** | `<b2_key_id>` | B2 Application Key ID. |
| **HF Spaces**| `VISIONGUARD_STORAGE_SECRET_ACCESS_KEY` | **Yes** | `<b2_application_key>` | B2 Application Secret Key. |
| **HF Spaces**| `VISIONGUARD_STORAGE_REGION` | No | `us-east-005` | B2 storage region. |
| **Vercel** | `VITE_API_BASE_URL` | **Yes** | `https://visionguard-api.onrender.com` | Render FastAPI base URL (no trailing slash). |

> [!CAUTION]
> **Zero Trust Rule**: Never set `VISIONGUARD_STORAGE_ACCESS_KEY_ID` or `DATABASE_URL` in Vercel. Frontend builds are public and accessible to browser clients. Storage and database credentials must ONLY be configured on Render and Hugging Face Spaces.

---

## 3. Step-by-Step Deployment Instructions

### Step 1: Neon Database Configuration & Migrations

1. Log in to [Neon Console](https://console.neon.tech).
2. Create or verify your database branch (e.g. `main` for production, `br-twilight-pond-b5kgwni2` for staging).
3. Copy the connection string in `postgresql+psycopg` format with `sslmode=require`:
   ```bash
   postgresql+psycopg://<username>:<password>@<endpoint>.neon.tech/<dbname>?sslmode=require
   ```
4. Run Alembic migrations against the database from your deployment runner:
   ```bash
   # Check current migration revision
   alembic -c backend/alembic.ini current

   # Upgrade schema to latest head (creates runs, reports, artifacts tables)
   alembic -c backend/alembic.ini upgrade head
   ```
5. Verify schema status:
   ```bash
   alembic -c backend/alembic.ini current
   # Expected output: 20261026_04 (head)
   ```

---

### Step 2: Backblaze B2 Bucket Setup (Primary)

1. In Backblaze B2 Console, navigate to **Buckets** > **Create a Bucket**:
   - Bucket Name: `visionguard-artifacts`
   - Bucket Type: `Private`
   - Default Encryption: `Enabled` (Server-Side Encryption)
2. Under **Application Keys**, click **Add a New Application Key**:
   - Name of Key: `visionguard-artifacts`
   - Allow access to Bucket(s): `visionguard-artifacts`
   - Type of Access: `Read and Write`
3. Note down the credentials generated:
   - `keyID` (maps to `VISIONGUARD_STORAGE_ACCESS_KEY_ID` / `B2_ACCESS_KEY_ID`)
   - `applicationKey` (maps to `VISIONGUARD_STORAGE_SECRET_ACCESS_KEY` / `B2_SECRET_ACCESS_KEY`)
   - `Endpoint`: `https://s3.<region>.backblazeb2.com` (e.g. `https://s3.us-east-005.backblazeb2.com`)
   - `Region`: e.g. `us-east-005`

*(Optional Alternative: If using Cloudflare R2, create bucket `visionguard-artifacts`, create R2 API Token with Object Read & Write, and set `VISIONGUARD_STORAGE_BACKEND=r2` with endpoint `https://<account_id>.r2.cloudflarestorage.com`).*

---

### Step 3: Render Deployment (FastAPI Gateway)

1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** > **Web Service**.
3. Connect your GitHub repository (`VisionGuard`).
4. Configure service settings:
   - **Name**: `visionguard-api`
   - **Runtime**: `Docker`
   - **Dockerfile Path**: `Dockerfile.api`
   - **Instance Type**: `Starter` (or `Free` for testing)
   - **Health Check Path**: `/health`
5. Under **Environment Variables**, add:
   ```env
   DATABASE_URL=postgresql+psycopg://<user>:<password>@<endpoint>-pooler.neon.tech/<dbname>?sslmode=require
   VISIONGUARD_DISPATCHER=worker
   VISIONGUARD_CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
   VISIONGUARD_STORAGE_BACKEND=b2
   VISIONGUARD_STORAGE_BUCKET=visionguard-artifacts
   VISIONGUARD_STORAGE_ENDPOINT=https://s3.us-east-005.backblazeb2.com
   VISIONGUARD_STORAGE_ACCESS_KEY_ID=<b2_key_id>
   VISIONGUARD_STORAGE_SECRET_ACCESS_KEY=<b2_application_key>
   VISIONGUARD_STORAGE_REGION=us-east-005
   ```
6. Click **Create Web Service**.
7. Render runs `Dockerfile.api`. The container boots uvicorn on `$PORT` and checks `/health`.
8. Once healthy, copy your Render service URL (e.g. `https://visionguard-api.onrender.com`).


---

### Step 4: Hugging Face Spaces Deployment (ML Worker)

1. Log in to [Hugging Face](https://huggingface.co).
2. Click **New Space**.
   - **Space Name**: `visionguard-worker`
   - **Space SDK**: `Docker` (select **Blank**)
   - **Space Hardware**: `CPU basic` (free) or `T4 small` (for fast GPU inference)
   - **Visibility**: `Public` or `Private` (Private recommended for dedicated backends)
3. Connect your repository or push `Dockerfile.worker` + backend source.
   *(Note: HF Docker Spaces builds from `Dockerfile` in the root of the space repo. Copy `Dockerfile.worker` to `Dockerfile` when pushing to HF).*
4. In the Space **Settings** > **Variables and secrets**, add Secrets:
   ```env
   DATABASE_URL=postgresql+psycopg://<user>:<password>@<endpoint>.neon.tech/<dbname>?sslmode=require
   PORT=7860
   VISIONGUARD_LEASE_TIMEOUT_SECONDS=60
   VISIONGUARD_MAX_ATTEMPTS=3
   VISIONGUARD_STORAGE_BACKEND=b2
   VISIONGUARD_STORAGE_BUCKET=visionguard-artifacts
   VISIONGUARD_STORAGE_ENDPOINT=https://s3.us-east-005.backblazeb2.com
   VISIONGUARD_STORAGE_ACCESS_KEY_ID=<b2_key_id>
   VISIONGUARD_STORAGE_SECRET_ACCESS_KEY=<b2_application_key>
   VISIONGUARD_STORAGE_REGION=us-east-005
   ```
5. Hugging Face builds the Docker container and launches `python -m backend.app.worker --poll --interval 2.0`.
6. The worker starts the background health server on `0.0.0.0:7860`.
7. Hugging Face checks port 7860, receives `200 OK` from `GET /health`, and marks the space **Running**.

---

### Step 5: Vercel Deployment (React Frontend)

1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** > **Project** and import `VisionGuard`.
3. In Project Configuration:
   - **Framework Preset**: `Other` (or `Vite`)
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.output/public`
4. Under **Environment Variables**:
   ```env
   VITE_API_BASE_URL=https://visionguard-api.onrender.com
   ```
5. Click **Deploy**.
6. Once deployed, note down the Vercel production URL (e.g. `https://visionguard.vercel.app`).
7. Update `VISIONGUARD_CORS_ORIGINS` in your Render Web Service settings to match this exact Vercel URL.

---

## 4. Full Evaluation Lifecycle Smoke Testing

Run these verification steps against the live deployed stack.

### Test 1: Verify API Gateway Health
```bash
curl -f https://visionguard-api.onrender.com/health
```
**Expected Response:**
```json
{"status": "healthy", "service": "visionguard-api"}
```

### Test 2: Verify Hugging Face Worker Health
```bash
curl -f https://<your-hf-username>-visionguard-worker.hf.space/health
```
**Expected Response:**
```json
{"status": "healthy", "service": "visionguard-worker", "worker_id": "worker-poll-...", "uptime_seconds": 120.5}
```

### Test 3: Query Registered Models & Datasets
```bash
curl https://visionguard-api.onrender.com/api/v1/models
curl https://visionguard-api.onrender.com/api/v1/datasets
```
**Expected Response:**
- Models includes: `"fasterrcnn_resnet50_fpn"`
- Datasets includes: `"visionguard_demo"`

### Test 4: Submit Evaluation Run
```bash
curl -X POST https://visionguard-api.onrender.com/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "fasterrcnn_resnet50_fpn",
    "dataset_id": "visionguard_demo",
    "config": {
      "corruptions": [
        {"kind": "fog", "severity": 1}
      ],
      "iou_threshold": 0.5,
      "confidence_threshold": 0.5
    }
  }'
```
**Expected Response:** `HTTP 201 Created`
```json
{
  "run_id": "run-xxxxxxxx",
  "status": "QUEUED",
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo"
}
```

### Test 5: Monitor Run Lifecycle & Worker Claim
Poll the run status:
```bash
curl https://visionguard-api.onrender.com/api/v1/runs/<run_id>
```
1. Transitions from `QUEUED` to `RUNNING` within 2–5 seconds (claimed by HF worker).
2. Worker runs Faster R-CNN on demo dataset, applies corruption, generates confusion matrix and report.
3. Status transitions to `COMPLETED` (approx. 5–15 seconds on GPU, 30–60 seconds on CPU).

### Test 6: Verify Evaluation Report & Artifact Retrieval
```bash
# Retrieve structured evaluation report
curl https://visionguard-api.onrender.com/api/v1/runs/<run_id>/report

# List generated artifacts (images, CSVs, JSON)
curl https://visionguard-api.onrender.com/api/v1/runs/<run_id>/artifacts

# Request presigned download URL for an artifact
curl https://visionguard-api.onrender.com/api/v1/runs/<run_id>/artifacts/<artifact_id>/download-url
```
**Expected Output:**
- Report contains `overall_map`, `condition_metrics`, and `failure_slices`.
- Artifacts list returns objects uploaded to Cloudflare R2 / Backblaze B2.
- Presigned download URL redirects to private bucket download.

### Test 7: Verify Frontend Visuals
1. Open `https://<your-vercel-domain>.vercel.app` in a web browser.
2. Verify the dashboard displays the completed run in the Runs table.
3. Open the Run detail page: verify metrics charts, confusion matrix visualization, and failure inspector drawer.

---

## 5. Rollback Procedures

### Scenario A: API Gateway Rollback (Render)
If a newly deployed API image fails health checks or throws errors:
1. In Render Dashboard, navigate to `visionguard-api` > **Deploys**.
2. Locate the previous successful deploy.
3. Click the three dots `...` and select **Rollback to this deploy**.
4. Render immediately swaps traffic to the previous healthy container.

### Scenario B: Database Schema Rollback (Neon / Alembic)
If a new migration causes query failures or breaks compatibility:
1. Connect via deployment runner:
   ```bash
   # Check current migration revision
   alembic -c backend/alembic.ini current

   # Downgrade by 1 revision
   alembic -c backend/alembic.ini downgrade -1
   ```
2. If using Neon branches, you can restore instant branch snapshots:
   - In Neon Console, click **Branches** > Select branch > **Restore from snapshot**.

### Scenario C: ML Worker Rollback (Hugging Face Spaces)
1. In your HF Space repo, checkout the previous working git commit:
   ```bash
   git checkout <previous_commit>
   git push -f origin main
   ```
2. Hugging Face re-triggers Docker build from the known good commit.

### Scenario D: Frontend Rollback (Vercel)
1. In Vercel Dashboard, navigate to **Deployments**.
2. Select the previous stable deployment.
3. Click **Instant Rollback**.
4. Vercel routes global CDN edge traffic to the prior build instantly.

---

## 6. Resource Limits, Failure Modes & Mitigations

| Platform | Limitation / Risk | Impact | Recommended Mitigation |
|---|---|---|---|
| **Render** | Free tier spins down after 15 minutes of inactivity | First request takes 50+ seconds cold start | Upgrade to Starter tier ($7/mo) or configure external health pinger (e.g. UptimeRobot) every 10 min. |
| **Hugging Face** | Free CPU Space sleeps after 48h of inactivity | Worker stops polling database | Set Space visibility or trigger health check pinger to `http://<space-url>/health` to keep active. |
| **Hugging Face** | Ephemeral container storage | Cached model weights re-download on restart | Pre-cache `fasterrcnn_resnet50_fpn` weights in Dockerfile layer or use fast TorchHub cache directory. |
| **Neon** | Compute scales to 0 after 5 min inactivity | First DB query incurs 1–2s latency | Use pooled connection string (`-pooler.neon.tech`) for Render API to prevent connection exhaustion. |
| **Vercel** | `VITE_API_BASE_URL` baked at build time | Frontend calls stale API if Render URL changes | Trigger frontend re-build whenever API hostname changes. |
| **R2 / B2** | S3 API rate limits on massive batch evaluations | Artifact uploads throttled | Worker uses exponential backoff and retries; chunking large evaluation artifacts. |

---

## 7. Security & Secret Verification Checklist

Before running production:
- [x] Tracked files in git contain **zero** credentials, API keys, or plaintext secrets.
- [x] `.env` is explicitly ignored by `.gitignore` and never committed.
- [x] Neon database connection uses strict `sslmode=require`.
- [x] Hugging Face Spaces port 7860 is bound to lightweight health server, not exposing sensitive routes.
- [x] Render API enforces exact CORS allowlist via `VISIONGUARD_CORS_ORIGINS`.
- [x] Object storage credentials (R2 / B2) are configured **only** on Render API and Hugging Face Worker.
- [x] Frontend contains **no** cloud storage or database keys.
