# Distributed Artifact Storage (Cloudflare R2 & S3)

## 1. Overview & Architecture

VisionGuard's production architecture is distributed across specialized cloud environments:
- **API Server:** FastAPI running on **Render** (stateless, handles requests and reporting).
- **ML Evaluator Worker:** PyTorch ML worker running on **Hugging Face Spaces** or dedicated GPU compute instances (asynchronous queue processor).
- **Relational Database:** PostgreSQL running on **Neon** (job metadata, lease coordination, evaluation reports).

In distributed deployments, the worker and API instances do not share a common local filesystem. Any image artifacts produced or transformed by the worker (such as corrupted condition variants, clean baseline crops, or diagnostic frames) must be stored in centralized, highly-available object storage accessible by both the worker (for writing) and the API (for streaming to the frontend).

**Cloudflare R2** provides an S3-compatible object storage solution with:
- **Zero Egress Bandwidth Fees:** No unexpected data transfer charges when streaming visual artifacts to users.
- **High Concurrency & Throughput:** Scales automatically under heavy parallel worker writes.
- **S3 API Compatibility:** Works natively with standard Python `boto3` / `botocore` clients using the AWS Signature Version 4 protocol.

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│     Hugging Face Spaces Worker   │           │         Render API Server       │
│  (PyTorch / CUDA Inference)     │           │         (FastAPI Gateway)       │
└──────────────┬──────────────────┘           └────────────────┬────────────────┘
               │                                               │
       1. Upload Artifacts                            2. Stream Artifacts
      (PUT runs/{run_id}/{id}.jpg)                   (GET runs/{run_id}/{id}.jpg)
               │                                               │
               ▼                                               ▼
         ┌───────────────────────────────────────────────────────────┐
         │                    Cloudflare R2 Bucket                   │
         │                (S3-Compatible Object Store)               │
         └───────────────────────────────────────────────────────────┘
```

---

## 2. Storage Abstraction Layer

VisionGuard provides a pluggable, environment-driven storage layer in [`backend/app/storage.py`](file:///d:/Projects/VisionGuard/backend/app/storage.py) implementing the `ArtifactStorage` protocol:

```python
class ArtifactStorage(Protocol):
    def put_object(self, key: str, data: bytes, content_type: str = "image/jpeg", metadata: dict[str, str] | None = None) -> str: ...
    def get_object(self, key: str) -> StorageObject: ...
    def head_object(self, key: str) -> StorageObjectMetadata | None: ...
    def delete_object(self, key: str) -> bool: ...
    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> list[StorageObjectMetadata]: ...
    def object_exists(self, key: str) -> bool: ...
```

### Available Implementations

1. **`FileSystemArtifactStorage` (Local Mode):**
   - Stores files in a local directory (default: `artifacts/`).
   - Uses atomic temporary file creation and replacement (`tempfile.NamedTemporaryFile` + `os.replace`) to guarantee zero file corruption under concurrent readers.
   - Ideal for local development, unit tests, and single-host Docker Compose environments.

2. **`S3ArtifactStorage` (Cloudflare R2 / S3 Mode):**
   - Backed by `boto3` with `botocore.config.Config(signature_version="s3v4")`.
   - Automatic retry handling with standard retry modes (`max_attempts=3`).
   - Maps `botocore.exceptions.ClientError` (404 / `NoSuchKey`) cleanly to `StorageObjectNotFoundError`.
   - Supports bucket-level key prefixes (`VISIONGUARD_STORAGE_PREFIX`) for multi-environment staging inside a single bucket.

### Key Validation & Security Guardrails

All storage operations pass through `validate_storage_key(key)`:
- Rejects directory traversal tokens (`..`).
- Rejects backslashes (`\`) and null bytes (`\0`).
- Rejects absolute paths (leading `/`).
- Enforces strict character whitelist regex: `^[a-zA-Z0-9_\-\.]+(/[a-zA-Z0-9_\-\.]+)*$`.
- Prevents cross-tenant path attacks and unauthorized filesystem escapes.

---

## 3. Configuration & Environment Variables

Storage configuration is managed via standard environment variables. Zero credentials are hardcoded.

| Variable | Required in R2 Mode | Default | Description |
|---|---|---|---|
| `VISIONGUARD_STORAGE_BACKEND` | No | `local` | Storage driver: `local` or `r2` (also accepts `s3`). |
| `VISIONGUARD_STORAGE_BUCKET` | Yes (for R2) | `None` | Cloudflare R2 bucket name (e.g. `visionguard-artifacts`). |
| `VISIONGUARD_STORAGE_ENDPOINT` | Yes (for R2) | `None` | Cloudflare R2 endpoint URL (`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`). |
| `VISIONGUARD_STORAGE_ACCESS_KEY_ID` | Yes (for R2) | `None` | Cloudflare R2 API Token Access Key ID. |
| `VISIONGUARD_STORAGE_SECRET_ACCESS_KEY` | Yes (for R2) | `None` | Cloudflare R2 API Token Secret Access Key. |
| `VISIONGUARD_STORAGE_REGION` | No | `auto` | Region identifier (`auto` for Cloudflare R2, `us-east-1` for standard AWS S3). |
| `VISIONGUARD_STORAGE_PREFIX` | No | `""` | Optional key prefix prepended to all object keys (e.g. `dev/` or `prod/`). |
| `VISIONGUARD_STORAGE_LOCAL_DIR` | No | `artifacts/` | Filesystem directory path used when `VISIONGUARD_STORAGE_BACKEND=local`. |

### Example `.env` Configuration for Cloudflare R2

```ini
# Distributed Object Storage (Cloudflare R2)
VISIONGUARD_STORAGE_BACKEND=r2
VISIONGUARD_STORAGE_BUCKET=visionguard-artifacts
VISIONGUARD_STORAGE_ENDPOINT=https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com
VISIONGUARD_STORAGE_ACCESS_KEY_ID=your_r2_access_key_id
VISIONGUARD_STORAGE_SECRET_ACCESS_KEY=your_r2_secret_access_key
VISIONGUARD_STORAGE_REGION=auto
VISIONGUARD_STORAGE_PREFIX=production/
```

### Example `.env` Configuration for Local Development

```ini
# Local Filesystem Storage (No cloud credentials required)
VISIONGUARD_STORAGE_BACKEND=local
VISIONGUARD_STORAGE_LOCAL_DIR=artifacts/
```

---

## 4. Worker Upload & API Serving Flow

### Worker Execution Pipeline

During job execution ([`backend/app/execution.py`](file:///d:/Projects/VisionGuard/backend/app/execution.py)):
1. The ML worker claims a `QUEUED` run and transitions it to `RUNNING` with an active heartbeat lease.
2. The evaluator evaluates clean images and synthesizes corrupted variants for each test condition.
3. Once the report is generated, `upload_run_artifacts(run_id, report_data, storage=storage)` in [`backend/app/artifacts.py`](file:///d:/Projects/VisionGuard/backend/app/artifacts.py) is called:
   - Encodes clean images and corrupted condition images to JPEG format.
   - Puts objects at keys matching `runs/{run_id}/{artifact_id}.jpg`.
   - Records metadata tags: `run_id`, `artifact_id`, `corruption_name`, `severity`, `clean_image_id`.
   - **Fault-Tolerant:** Individual image upload failures are logged as warnings and do not fail the overall evaluation run.
4. Report JSON with evaluation metrics is committed to Neon PostgreSQL.

### API Gateway Serving

The FastAPI server ([`backend/app/main.py`](file:///d:/Projects/VisionGuard/backend/app/main.py)) exposes authenticated/authorized artifact access:
- **`GET /api/v1/runs/{run_id}/artifacts`**:
  - Queries `storage.list_objects(prefix=f"runs/{run_id}/")`.
  - Merges stored objects with any report metadata in database.
  - Returns a list of available artifacts with size, content type, and metadata.
- **`GET /api/v1/runs/{run_id}/artifacts/{artifact_id}`**:
  - Resolves object key `runs/{run_id}/{artifact_id}.jpg`.
  - Fetches the object from `storage.get_object(key)`.
  - Streams `Response(content=obj.data, media_type=obj.content_type)`.
  - If storage is `local` and the object is clean or not yet uploaded, falls back to local dataset image resolution transparently.
  - **Zero Credential Exposure:** The API handles all authentication with R2. Presigned URLs and R2 credentials are never returned or leaked to the client browser.

---

## 5. Cloudflare R2 Bucket Setup Guide

### Step 1: Create the R2 Bucket
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **R2 Object Storage** in the sidebar.
3. Click **Create bucket**.
4. Enter a bucket name (e.g., `visionguard-artifacts`).
5. Choose **Default** (Automatic) location and confirm.

### Step 2: Generate API Tokens
1. On the R2 Overview page, click **Manage R2 API Tokens** on the right side.
2. Click **Create API token**.
3. Set permissions to **Object Read & Write**.
4. Under **Apply to specific buckets only**, select your `visionguard-artifacts` bucket.
5. Set TTL as required by your organization's security policy.
6. Click **Create API Token**.
7. Copy the following values into your environment or secret manager:
   - **Account ID** (used to form `VISIONGUARD_STORAGE_ENDPOINT`).
   - **Access Key ID** (`VISIONGUARD_STORAGE_ACCESS_KEY_ID`).
   - **Secret Access Key** (`VISIONGUARD_STORAGE_SECRET_ACCESS_KEY`).

### Step 3: Configure Lifecycle Policies (Recommended)
To prevent unbound growth of transient evaluation images:
1. In your bucket settings, open the **Lifecycle Rules** tab.
2. Add a rule:
   - Name: `Expire-Evaluation-Artifacts-30d`
   - Prefix: `runs/`
   - Action: **Delete object after 30 days**.
3. Save the rule.

---

## 6. Testing & Validation

### Offline Unit Tests
Unit tests in [`backend/tests/test_storage.py`](file:///d:/Projects/VisionGuard/backend/tests/test_storage.py) test the complete storage abstraction without real cloud calls using `botocore.stub.Stubber`:
```powershell
.\.venv-gpu\Scripts\pytest backend\tests\test_storage.py backend\tests\test_artifacts.py -v
```

These tests verify:
- Key validation and path traversal rejections (`..`, `\`, null bytes, absolute paths).
- `FileSystemArtifactStorage` write, read, delete, list, atomic replacement, and metadata handling.
- `S3ArtifactStorage` PutObject, GetObject, HeadObject, DeleteObject, ListObjectsV2, and 404 mapping via `Stubber`.
- Worker artifact upload and API artifact retrieval end-to-end integration.

### Live Staging Integration Test
To run the live integration test against an actual Cloudflare R2 bucket:
```powershell
$env:VISIONGUARD_STORAGE_BACKEND="r2"
$env:VISIONGUARD_TEST_R2_BUCKET="my-staging-bucket"
$env:VISIONGUARD_STORAGE_ENDPOINT="https://<account_id>.r2.cloudflarestorage.com"
$env:VISIONGUARD_STORAGE_ACCESS_KEY_ID="<key_id>"
$env:VISIONGUARD_STORAGE_SECRET_ACCESS_KEY="<secret_key>"

.\.venv-gpu\Scripts\pytest backend\tests\test_storage.py -k test_s3_storage_live_r2_integration -v
```
When live credentials are not present in the environment, the live integration test is automatically and safely skipped.
