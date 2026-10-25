# VisionGuard backend

The FastAPI backend stores evaluation runs and reports in PostgreSQL. Neon
Serverless PostgreSQL is the recommended hosted database. SQLite is used only
by isolated unit tests; the application never silently falls back to it.

## Create and configure a Neon database

1. Create a Neon project and database in the Neon Console.
2. In the project dashboard, open **Connect**, choose the database and role,
   and copy the connection string. Use the pooled URL for normal web service
   workloads when Neon offers it.
3. Keep TLS enabled. Neon connection strings should include
   `sslmode=require`; if omitted, the backend adds that setting. A URL that
   explicitly disables TLS is rejected.
4. From the repository root, create a local environment file:

   ```powershell
   Copy-Item .env.example .env
   code .env
   ```

5. Replace the `DATABASE_URL` placeholder in `.env` with the connection string
   copied from Neon. Do not paste a real URL into source files, logs, issues,
   or commits. `.env` is ignored by Git.

For production, configure `DATABASE_URL` as a secret environment variable in
the deployment platform; do not deploy or commit `.env`. The API requires this
variable and returns a clear startup configuration error when it is absent.

## Install and migrate

Run from the repository root in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
```

Migrations are versioned in `backend\migrations\versions`. They are not run
automatically at application startup. Before migrating a database that already
contains tables or data, take a Neon backup/branch and inspect its schema. The
initial migration leaves compatible `runs` and `reports` tables in place, adds
missing indexes, and refuses incompatible existing tables rather than
dropping or rewriting them. Do not stamp an existing database or edit the
Alembic version table without reviewing its schema and migration history.

To add a future migration after changing the SQLAlchemy metadata:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini revision --autogenerate -m "describe schema change"
```

Review and test the generated migration before applying it with `upgrade head`.
Keep migrations data-preserving; automatic downgrades are intentionally
disabled to avoid deleting evaluation data.

The previous local `backend\visionguard.sqlite3` file is not used by the new
application and is left untouched. It contained no run or report rows when
inspected. The migration does not copy SQLite data to Neon.

## Start and verify the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation. The
database-aware health endpoint is `http://127.0.0.1:8000/health`; it returns
`503` if the database is unavailable. Run list and report operations continue
to use the existing API contract:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | API and database connectivity |
| `GET` | `/api/v1/models` | Configured model IDs |
| `POST` | `/api/v1/runs` | Validate, persist, and queue an evaluation |
| `GET` | `/api/v1/runs` | List runs (`limit` 1-100, `offset` >= 0) |
| `GET` | `/api/v1/runs/{run_id}` | Retrieve persisted run status |
| `GET` | `/api/v1/runs/{run_id}/report` | Retrieve the stored terminal report |

Set optional model IDs as a comma-separated environment variable:

```powershell
$env:VISIONGUARD_SUPPORTED_MODELS = "fasterrcnn_resnet50_fpn"
```

The API calls `visionguard.core.api:evaluate_run(config, run_id=...)` and
validates reports against the shared `EvaluationReport` contract. The current
shared evaluator returns fixture/demo data and marks it `is_fixture: true`;
this is not real model inference.

## Database and migrations

SQLAlchemy provides a small synchronous connection pool with connection
pre-ping; `psycopg` connects to PostgreSQL. Run configuration and report
payloads are stored as PostgreSQL `JSONB`, alongside relational run IDs,
statuses, model/dataset IDs, timestamps, and error messages. Reports have a
unique run foreign key. Indexes support time-ordered and status-filtered run
queries. Every write is transactional and uses parameterized SQL expressions.

The migration-managed schema consists of:

- `runs`: ID, status, model/dataset IDs, JSONB config, creation/update and
  lifecycle timestamps,
  and a safe error summary.
- `reports`: report ID, unique run ID foreign key, JSONB report, and creation
  timestamp.
- `alembic_version`: Alembic's migration revision tracking table.

The API checks database connectivity on startup and during `/health`. It does
not create or alter production tables on startup. Database errors returned by
the API are sanitized and do not include the URL, password, or driver details.

## Tests

The normal suite uses temporary SQLite databases and mocked evaluator data. It
does not connect to Neon or require model weights/GPU:

```powershell
.\.venv\Scripts\python.exe -m pytest .\visionguard_contracts\tests .\backend\tests -v
```

An optional read-only connectivity test uses a **dedicated test database**:

```powershell
$env:TEST_DATABASE_URL = "postgresql://USER:PASSWORD@TEST_HOST/TEST_DATABASE?sslmode=require"
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_postgres_integration.py -v
```

That test only runs `SELECT 1`; it does not create, alter, or delete tables. Do
not set `TEST_DATABASE_URL` to a production database. Unit tests use in-memory
or temporary SQLite files and never read or modify `DATABASE_URL`.

## Troubleshooting

- **`DATABASE_URL is required`:** Create `.env` from `.env.example`, set the
  connection string, and run the commands from the repository root.
- **TLS/SSL errors:** Copy the current Neon connection string and keep
  `sslmode=require`; do not disable TLS.
- **Authentication or host errors:** Re-copy the URL from Neon’s **Connect**
  panel, confirm the role/database, and rotate credentials in Neon if exposed.
  Never paste credentials into chat or commit them.
- **Missing-table or migration errors:** Apply `alembic upgrade head`. If the
  initial migration reports incompatible existing tables, stop and inspect
  the schema and take a backup; do not drop the tables to force the migration.
- **Network/pooler errors:** Confirm outbound connectivity and use the pooled
  connection URL intended for application workloads. The full URL is never
  intentionally logged by this backend.
