# VisionGuard Security Audit & Review

## 1. Executive Summary
This security review evaluates the VisionGuard architecture across authentication, data protection, network exposure, input validation, and file access.

**Current Security Posture:** Suitable for internal engineering evaluation and staging environments. Authentication and multi-tenant authorization are deliberately omitted from the initial MVP architecture and represent prerequisites before public multi-user exposure.

---

## 2. Security Assessment by Area

### 2.1 Transport Security & Database Protection
- **TLS/SSL Enforcement:** Mandatory for all PostgreSQL connections. `_require_postgres_tls` rejects unencrypted connections or connection strings without `sslmode=require` (or `verify-ca`/`verify-full`).
- **Credential Storage:** Secrets are managed strictly via environment variables. Connection strings are scrubbed from error responses and terminal logs.

### 2.2 CORS & API Exposure
- **Origin Whitelisting:** CORS origins are restricted to configured domains via `VISIONGUARD_CORS_ORIGINS`. Wildcard `*` origins are disallowable with credentials.
- **Exposed Endpoints:** All `/api/v1/*` endpoints are currently unauthenticated. Anyone with network access to the API can submit evaluation jobs and view persisted reports.

### 2.3 Input Validation & Injection Prevention
- **Pydantic Validation:** All incoming payloads are strictly validated using typed Pydantic models. Malformed parameters produce structured `422 Unprocessable Entity` responses.
- **SQL Injection Prevention:** All database operations utilize parameterized SQLAlchemy Core queries. No raw SQL string interpolation is permitted.
- **Path Traversal Guardrails:** Artifact retrieval (`/api/v1/runs/{run_id}/artifacts/{artifact_id}`) enforces strict filename and UUID regex validation, preventing directory traversal attacks (`../`).

### 2.4 ML Evaluation Pipeline Security
- **Model Checkpoints:** Faster R-CNN uses official PyTorch torchvision weights (`WeightsEnum.DEFAULT`). Arbitrary untrusted `.pt` or pickle checkpoint files cannot be uploaded through the API.
- **Dataset Boundaries:** Evaluator only executes against registered datasets registered in `DATASET_REGISTRY`. Arbitrary filesystem directories cannot be passed via the API.
- **Bounded Resource Consumption:** Thread limits (`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`) prevent thread starvation on shared hosts.

---

## 3. Known Limitations & Production Hardening Roadmap

| Risk / Gap | Impact | Recommended Production Fix |
|---|---|---|
| **No Authentication (AuthN)** | Anyone on the network can submit runs and view reports. | Implement OAuth2 / OIDC (e.g. Auth0, Clerk, or Keycloak) with JWT bearer token verification. |
| **No Multi-Tenant Isolation (AuthZ)** | Runs have no tenant ownership; all users share a global namespace. | Add `user_id` / `tenant_id` foreign keys to `runs` table and enforce row-level security. |
| **Rate Limiting** | Evaluator queue could be flooded with compute-heavy runs. | Implement token-bucket rate limiting via Redis or API gateway (e.g. Cloudflare / Kong). |
| **Storage Quotas** | Corrupted artifact images could exhaust local disk space. | Offload image artifact storage to S3/R2 with lifecycle expiration policies. |
