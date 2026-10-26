# VisionGuard Testing Strategy

## Current project scope

The backend in `backend/core.py` implements image corruptions, box warping,
IoU, detection comparison, and Markdown report formatting. The API in
`backend/main.py` exposes `/api/health`, `/api/analyze`, `/api/runs/{run_id}`,
and `/api/runs/{run_id}/report`. Existing tests are in `backend/tests/`.

## Test layers

- **Unit tests:** exercise `core.py` functions without loading the YOLO model.
- **API tests:** verify health, invalid inputs, run lookup, analysis persistence,
  and report export. Model inference is stubbed for deterministic tests.
- **Security review:** use `SECURITY_CHECKLIST.md` to track controls that are
  absent, present, or still need verification.
- **Frontend tests:** not configured in the supplied `frontend/package.json`;
  add a frontend test runner only after agreeing on the tool and dependencies.

## Run backend tests

From the repository root:

```powershell
cd backend
python -m pip install -r requirements-test.txt
python -m pytest tests -v
```

The API test setup uses a temporary SQLite database so tests do not intentionally
write to the normal development database. Tests stub model inference and should
not need `yolov8n.pt`.

## Result statuses

- Planned: scenario documented but no test code yet.
- Implemented: test code exists.
- Passed: test was executed and passed.
- Failed: test was executed and did not pass.
- Blocked: cannot be run because a dependency or feature is missing.
- N/A: confirmed not applicable, with a reason.

Do not mark tests as passed without executing them.
