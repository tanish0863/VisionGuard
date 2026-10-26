# VisionGuard PostgreSQL Verification & Compatibility

## 1. Overview
VisionGuard is architected to utilize PostgreSQL (specifically Neon Serverless PostgreSQL) as its production relational store, while preserving SQLite support for fast, isolated in-memory unit tests.

This document verifies the PostgreSQL compatibility guarantees, connection lifecycle, and integration testing protocols.

---

## 2. PostgreSQL Compatibility Guarantees

| Feature | PostgreSQL Implementation | SQLite Fallback (Tests) |
|---|---|---|
| **Driver** | `psycopg` (v3 via `postgresql+psycopg`) | Built-in `sqlite3` |
| **TLS/SSL** | Enforced: `sslmode=require` (or `verify-ca`/`verify-full`) | Not applicable (in-memory) |
| **JSON Storage** | `JSONB` binary JSON with indexability and queries | `JSON` text variant |
| **Identifiers** | Standard UUID strings (36 chars) | Standard UUID strings |
| **Timestamps** | Timezone-aware UTC `TIMESTAMPTZ` | ISO 8601 strings |
| **Connection Pooling** | `pool_size=5`, `max_overflow=10`, `pool_recycle=300s`, `pool_pre_ping=True` | `StaticPool` for memory retention |
| **Atomic Claiming** | Atomic `UPDATE ... WHERE status = 'QUEUED'` with atomic status flip | In-transaction update |
| **Cascade Delete** | `ON DELETE CASCADE` foreign key from `reports.run_id` to `runs.run_id` | Foreign key enabled in tests |

---

## 3. Database Security & Verification Policy

### Production Safety Non-Negotiable
- **Never expose credentials:** Database connection strings, passwords, and hostnames must never be printed in logs, exposed in error responses, or committed to version control.
- **Dedicated Test Database:** All live integration testing against PostgreSQL must be performed against an isolated test database specified via `TEST_DATABASE_URL`.
- **Safety Assertion:** `backend/tests/test_postgres_integration.py` explicitly validates:
  ```python
  if prod_url and test_url == prod_url:
      pytest.fail("SAFETY GUARD: TEST_DATABASE_URL must never match the production DATABASE_URL")
  ```

---

## 4. End-to-End Verification Checklist

When executing against an approved development or staging PostgreSQL database:
1. **Migration Verification:** Apply `alembic -c backend/alembic.ini upgrade head` and verify that revision `20261026_02` is active.
2. **Atomic Lifecycle:** Verify that runs progress from `QUEUED` to `RUNNING` (with worker lease) to `COMPLETED`.
3. **JSONB Report Storage:** Verify report insertion into `reports` with complex nested evaluation JSON, and verify that retrieval parses full condition metrics.
4. **Restart Persistence:** Disconnect the engine and re-instantiate `RunDatabase` to verify data persistence across API restarts.
5. **Stale Lease Recovery:** Simulate expired worker heartbeats and verify that `recover_stale_runs` safely transitions expired runs back to `QUEUED` or `FAILED`.
