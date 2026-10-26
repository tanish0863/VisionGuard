# VisionGuard Database Migrations Guide

## 1. Overview
VisionGuard utilizes [Alembic](https://alembic.sqlalchemy.org/) alongside SQLAlchemy for version-controlled database schema migrations. Schema versioning ensures that table structures, indexes, and constraints remain deterministic across development, testing, and production environments.

- **Configuration:** `backend/alembic.ini`
- **Migration Environment:** `backend/migrations/env.py`
- **Versions Directory:** `backend/migrations/versions/`

---

## 2. Migration Revisions History

### Revision 1: `20261025_01_initial_postgres_schema.py`
- **Revises:** `None` (Initial schema)
- **Tables created:**
  - `runs`: Primary run tracking table with `run_id` (UUID PK), `status` (with CheckConstraint `ck_runs_status`), `model_id`, `dataset_id`, `config_json` (`JSONB`), `created_at`, `updated_at`, `started_at`, `finished_at`, `error_message`.
  - `reports`: Evaluation report table with `report_id` (UUID PK), `run_id` (Foreign Key referencing `runs.run_id` with `CASCADE` delete, unique), `report_json` (`JSONB`), `created_at`.
- **Indexes:**
  - `ix_runs_created_at` on `runs(created_at)`
  - `ix_runs_status_created_at` on `runs(status, created_at)`
  - `ix_reports_created_at` on `reports(created_at)`
- **Downgrade Policy:** Automatic downgrade is disabled to protect against accidental data loss of evaluation results.

### Revision 2: `20261026_02_add_worker_lease_columns.py`
- **Revises:** `20261025_01`
- **Columns added to `runs`:**
  - `worker_id` (`String(64)`, nullable) — Identifies the worker process currently holding the execution lease.
  - `heartbeat_at` (`DateTime(timezone=True)`, nullable) — Timestamp of the last liveness heartbeat renewed by the worker.
  - `attempt_count` (`Integer`, non-null, default 0) — Counter tracking execution attempts for bounded crash recovery.
- **Indexes added:**
  - `ix_runs_status_heartbeat` on `runs(status, heartbeat_at)` — Supports fast index scans during stale lease recovery sweeps.
- **Downgrade:** Drops `ix_runs_status_heartbeat`, `attempt_count`, `heartbeat_at`, and `worker_id`.

---

## 3. Migration Commands

### Check Current Migration Version
```powershell
.\.venv-gpu\Scripts\alembic -c backend/alembic.ini current
```

### Apply Migrations (Upgrade to Head)
```powershell
.\.venv-gpu\Scripts\alembic -c backend/alembic.ini upgrade head
```

### Create a New Migration
```powershell
.\.venv-gpu\Scripts\alembic -c backend/alembic.ini revision -m "description_of_change"
```

---

## 4. Safety Guardrails

1. **Isolation of Environments:**
   - Production migrations require explicit operational sign-off.
   - For test runs and CI, configure `TEST_DATABASE_URL` or `ALEMBIC_DATABASE_URL` pointing to an isolated development branch or test instance.
   - Tests enforce that `TEST_DATABASE_URL` never matches `DATABASE_URL`.
2. **TLS Requirement:**
   - PostgreSQL connection strings must specify TLS (`sslmode=require` or stronger).
3. **Data Preservation:**
   - Never run destructive down-revisions on production databases.
