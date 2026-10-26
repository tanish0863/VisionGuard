# Distributed Artifact Storage with Backblaze B2

## 1. Overview & Architecture

VisionGuard uses **Backblaze B2 Cloud Storage** via its S3-compatible API as the shared object storage backend for distributed evaluation runs.

### Deployment Topology

```
┌──────────────────────────────────────┐           ┌──────────────────────────────────────┐
│      Hugging Face Spaces Worker      │           │          Render API Server           │
│      (PyTorch / CUDA Evaluator)      │           │          (FastAPI Gateway)           │
└──────────────────┬───────────────────┘           └──────────────────┬───────────────────┘
                   │                                                  │
          1. Upload Artifacts                                2. Generate Presigned
         (PUT runs/{run_id}/...)                             Download URLs (15 min)
                   │                                                  │
                   ▼                                                  ▼
             ┌──────────────────────────────────────────────────────────────┐
             │                   Backblaze B2 Private Bucket                │
             │                  (visionguard-artifacts)                     │
             └──────────────────────────────┬───────────────────────────────┘
                                            │
                                            │ 3. Fetch Directly via Signed URL
                                            ▼
                             ┌──────────────────────────────┐
                             │        Vercel Frontend       │
                             │       (React/Vite App)       │
                             └──────────────────────────────┘
```

1. **Hugging Face ML Worker:**
   - Evaluates object detection models against clean and corrupted condition datasets.
   - Uploads visual artifacts (clean baseline, corrupted conditions, diagnostic images) to the Backblaze B2 private bucket using `boto3`.
   - Inserts artifact metadata records into the **Neon PostgreSQL** database.
   - Marks the run complete only after all uploads and metadata records are committed.

2. **Render API Gateway (FastAPI):**
   - Authorizes requests and verifies run ownership.
   - Generates temporary signed URLs (15-minute / 900-second expiration) using S3 Signature Version 4.
   - Proxies artifact streams via `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}` or issues download links via `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download-url`.
   - Never exposes B2 credentials to the client browser.

3. **Neon PostgreSQL:**
   - Stores job state, worker heartbeats, evaluation reports, and the `artifacts` metadata table.
   - Large image binaries are kept strictly in B2, preserving database lightweight performance.

4. **Vercel Frontend:**
   - Requests temporary signed download URLs from the API.
   - Directly displays visual comparisons and provides report downloads using B2 signed URLs.

---

## 2. Configuration & Environment Variables

Storage configuration uses standard environment variables. Zero credentials are hardcoded.

| Variable | Description | Example |
|---|---|---|
| `B2_ENDPOINT_URL` | Backblaze B2 S3 endpoint URL | `https://s3.us-east-005.backblazeb2.com` |
| `B2_REGION` | Backblaze B2 region identifier | `us-east-005` |
| `B2_BUCKET_NAME` | Private bucket name | `visionguard-artifacts` |
| `B2_ACCESS_KEY_ID` | Application Key ID | `<your-b2-key-id>` |
| `B2_SECRET_ACCESS_KEY` | Application Key Secret | `<your-b2-application-key>` |
| `VISIONGUARD_STORAGE_BACKEND` | Storage driver (`b2` or `local`) | `b2` |

> [!NOTE]
> The storage subsystem in [`backend/app/storage.py`](file:///d:/Projects/VisionGuard/backend/app/storage.py) and [`backend/app/services/b2_storage.py`](file:///d:/Projects/VisionGuard/backend/app/services/b2_storage.py) also supports `VISIONGUARD_STORAGE_*` aliases for universal S3 compatibility.

---

## 3. Storage Abstraction & Services

### Reusable Service: `b2_storage.py`
Located at [`backend/app/services/b2_storage.py`](file:///d:/Projects/VisionGuard/backend/app/services/b2_storage.py):
- `upload_artifact(local_path, object_key, content_type)`: Uploads local file to B2.
- `upload_bytes(data, object_key, content_type, metadata)`: Streams binary data directly to B2.
- `generate_download_url(object_key, expires_in=900)`: Creates temporary presigned GET URLs with virtual-host addressing.
- `delete_artifact(object_key)`: Deletes an object.

### Storage Abstraction: `storage.py`
Located at [`backend/app/storage.py`](file:///d:/Projects/VisionGuard/backend/app/storage.py):
- `FileSystemArtifactStorage`: Atomic local file operations for offline development.
- `S3ArtifactStorage`: Full S3v4 client supporting Backblaze B2 with automatic retries and `s3={"addressing_style": "virtual"}`.
- `validate_storage_key(key)`: Path traversal defense blocking `..`, `\`, null bytes, and absolute paths.

---

## 4. Neon PostgreSQL Artifacts Schema

The `artifacts` table tracks object metadata without storing binary payloads:

```sql
CREATE TABLE artifacts (
    artifact_id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    artifact_type VARCHAR(64) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    object_key VARCHAR(1024) NOT NULL UNIQUE,
    content_type VARCHAR(128) NOT NULL,
    size_bytes BIGINT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_artifacts_run_id ON artifacts(run_id);
CREATE INDEX ix_artifacts_created_at ON artifacts(created_at);
```

Managed via Alembic migration:
[`backend/migrations/versions/20261026_03_create_artifacts_table.py`](file:///d:/Projects/VisionGuard/backend/migrations/versions/20261026_03_create_artifacts_table.py)

---

## 5. API Endpoints

### 1. Generate Presigned Download URL
- **Endpoint:** `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download-url`
- **Parameters:** `expires_in` (integer, default 900 seconds)
- **Response:**
  ```json
  {
    "artifact_id": "clean_01_street_urban",
    "file_name": "clean_01_street_urban.jpg",
    "download_url": "https://visionguard-artifacts.s3.us-east-005.backblazeb2.com/runs/...?X-Amz-Signature=...",
    "expires_in": 900
  }
  ```

### 2. Stream Artifact (Proxy)
- **Endpoint:** `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}`
- Streams the image binary directly with `Cache-Control: public, max-age=3600`.

### 3. List Run Artifacts
- **Endpoint:** `GET /api/v1/runs/{run_id}/artifacts`
- Returns all clean and corrupted image artifacts discovered in B2 and the evaluation report.

---

## 6. Frontend Integration

In [`frontend/src/lib/api.ts`](file:///d:/Projects/VisionGuard/frontend/src/lib/api.ts):

```typescript
// Fetch a fresh 15-minute presigned URL
const { download_url } = await api.getArtifactDownloadUrl(runId, artifactId);

// Display image or trigger download
window.open(download_url, "_blank", "noopener,noreferrer");
```

---

## 7. Verification & Testing

### Automated Test Suite
- Offline unit tests with `botocore.stub.Stubber`:
  ```powershell
  .\.venv-gpu\Scripts\pytest backend\tests\test_storage.py backend\tests\test_artifacts.py -v
  ```
- Live Backblaze B2 bucket integration test:
  ```powershell
  .\.venv-gpu\Scripts\pytest backend\tests\test_storage.py -k test_live_backblaze_b2_integration -v
  ```
- Frontend unit tests:
  ```powershell
  cd frontend; npm test -- --run
  ```
