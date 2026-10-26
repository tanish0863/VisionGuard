# VisionGuard Worker Architecture

## 1. Overview
VisionGuard provides two decoupled execution modes configured via `VISIONGUARD_DISPATCHER`:
1. `background`: Single-process local execution via FastAPI `BackgroundTasks`. Ideal for local development on machines where the API server and GPU coexist.
2. `worker`: Fully decoupled distributed execution. FastAPI acts purely as an API gateway, persisting jobs in `QUEUED` status. One or more external GPU worker processes poll or claim jobs from the database and execute Faster R-CNN inference.

---

## 2. Dispatcher Configuration Modes

```
+-------------------------------------------------------------------------------+
|                             POST /api/v1/runs                                 |
+-------------------------------------------------------------------------------+
                                      |
                                      v
                        Persist run as status='QUEUED'
                                      |
                     [ Check VISIONGUARD_DISPATCHER ]
                                      |
                  +-------------------+-------------------+
                  |                                       |
                  v                                       v
         [ mode='background' ]                     [ mode='worker' ]
                  |                                       |
       FastAPI BackgroundTask executes                    |
       evaluator in-process                       API returns 202 Accepted
                  |                               Run remains in 'QUEUED' status
                  v                                       |
         QUEUED -> RUNNING -> COMPLETED                   v
                                                Independent Worker Process
                                                claims job via atomic DB lock:
                                                QUEUED -> RUNNING -> COMPLETED
```

---

## 3. Atomic Job Claiming & PostgreSQL Concurrency

To prevent race conditions when multiple workers operate concurrently:
- On PostgreSQL, `claim_next_queued_run(worker_id, claimed_at)` uses transaction-level row locking with `FOR UPDATE SKIP LOCKED`:
  ```sql
  SELECT run_id FROM runs
  WHERE status = 'QUEUED'
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  UPDATE runs
  SET status = 'RUNNING',
      started_at = :claimed_at,
      heartbeat_at = :claimed_at,
      worker_id = :worker_id,
      attempt_count = attempt_count + 1,
      updated_at = :claimed_at
  WHERE run_id = :selected_run_id AND status = 'QUEUED';
  ```
- On SQLite, table-level transaction locking is utilized for local development and test suite compatibility.
- Each claim increments the monotonically increasing fencing generation `attempt_count`.

---

## 4. Fencing Generation & Lease Ownership Validation

To prevent stale worker processes (e.g. following network partitions, long GC pauses, or crashed nodes whose leases expired) from corrupting state or overwriting reports:
- Every mutation query (`heartbeat_run`, `complete_run`, `fail_run`, `persist_report`, `update_run_status`) enforces:
  - `runs.c.worker_id == worker_id`
  - `runs.c.attempt_count == attempt_count`
- If Worker A's lease expires and Worker B reclaims the job, `attempt_count` increments. Any subsequent heartbeat, completion, failure, or report persistence from Worker A is rejected (`ValueError` or `False`), even if Worker A reuses the same worker process ID upon restart.

---

## 5. SQL Recovery Query Optimization

Stale lease reclamation in `recover_stale_runs()` is performed directly in the database engine via SQL expressions:
```sql
SELECT run_id, attempt_count
FROM runs
WHERE status = 'RUNNING'
  AND COALESCE(heartbeat_at, started_at) < :cutoff;
```
- If `attempt_count < max_attempts`: run is requeued to `QUEUED` for retry.
- If `attempt_count >= max_attempts`: run is transitioned to `FAILED` terminal state.

---

## 6. Shared Artifact Storage

In distributed worker mode, the API gateway and ML worker nodes share artifact storage:
- `docker-compose.yml` mounts a named volume `run-artifacts:/app/backend/artifacts` across both the `api` and `worker` services.
- The API resolves stored artifacts with strict path traversal boundaries (`is_relative_to()`).

---

## 7. Concurrency & Regression Verification
Verified via:
- `test_two_workers_atomic_claiming`: Confirms atomic claiming prevents double allocation.
- `test_stale_worker_lease_expiry_and_mutation_rejection`: Reproduces lease expiry and verifies rejection of late heartbeats, completions, failures, and report persistences.
- `test_worker_creates_artifact_and_api_retrieves_content`: Confirms worker-written files in shared storage are discoverable and retrievable via the API gateway.
- `test_postgres_multi_worker_concurrency_skip_locked`: Dispatches 5 concurrent worker threads in PostgreSQL verifying `FOR UPDATE SKIP LOCKED` guarantees zero collision.

