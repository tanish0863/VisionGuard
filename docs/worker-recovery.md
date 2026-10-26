# VisionGuard Worker Crash Recovery & Durable Leases

## 1. Problem Statement
In production ML systems, GPU workers can crash unexpectedly due to hardware faults, out-of-memory (OOM) exceptions, or preemption. Without durable leases, runs being processed during a crash would remain in `RUNNING` status indefinitely, stranding user evaluations.

---

## 2. Durable Lease Mechanism

### Schema Additions (`runs` table)
- `worker_id` (`VARCHAR(64)`): Unique identifier of the executing worker process.
- `heartbeat_at` (`TIMESTAMPTZ`): Last active timestamp renewed periodically by the worker.
- `attempt_count` (`INTEGER`): Counter of execution attempts for bounded retries.
- Index `ix_runs_status_heartbeat` on `(status, heartbeat_at)`.

### Heartbeat Renewal
During execution, `_HeartbeatManager` daemon thread in `backend/app/execution.py` issues heartbeat renewals every `lease_timeout / 3` seconds (e.g. every 20 seconds for a 60-second lease timeout):
```sql
UPDATE runs
SET heartbeat_at = :now, updated_at = :now
WHERE run_id = :run_id AND worker_id = :worker_id AND status = 'RUNNING';
```

---

## 3. Stale Job Recovery Protocol

Any worker or recovery sweep (`POST /api/v1/runs/recover-stale`) invokes `RunDatabase.recover_stale_runs(now, lease_timeout_seconds, max_attempts)`:

```
For each run WHERE status = 'RUNNING' AND COALESCE(heartbeat_at, started_at) < (now - lease_timeout):

                  [ attempt_count < max_attempts ]
                                |
                +---------------+---------------+
                |                               |
               YES                             NO
                |                               |
                v                               v
         Requeue Run:                     Mark Run FAILED:
       status = 'QUEUED'                status = 'FAILED'
       worker_id = NULL                 error_message = 'Worker lease expired
       heartbeat_at = NULL               after exceeding retry limit'
```

### Key Guarantees
1. **Online Recovery:** Crash recovery runs while the FastAPI application remains continuously online, without requiring an API server restart.
2. **Healthy Long-Running Jobs Protected:** Active GPU jobs continuously renew heartbeats, preventing recovery sweeps from interrupting healthy inference.
3. **Bounded Retries:** Prevents poison jobs (e.g., malformed image files that consistently crash PyTorch) from looping indefinitely.
4. **No Concurrent Duplicate Execution:** Requeued jobs reset `worker_id` and can only be claimed after the prior lease has verifiably expired.

---

## 4. Test Evidence
Verified via `backend/tests/test_worker.py`:
- `test_crash_recovery_without_api_restart`: Simulates a worker dying during execution; confirms stale run is recovered to `QUEUED` and successfully completed by a subsequent worker while FastAPI stays running.
- `test_crash_recovery_bounded_retries`: Confirms that exceeding `max_attempts` transitions the run to `FAILED`.
- `test_healthy_heartbeat_lease_not_recovered`: Confirms that runs actively sending heartbeats are not touched by recovery sweeps.
