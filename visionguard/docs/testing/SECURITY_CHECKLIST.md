# VisionGuard Pre-launch Security Checklist

Status values: `Not checked`, `Pass`, `Fail`, `Blocked`, or `N/A`.
Record evidence and the date for every completed check.

| # | Check | What to verify for this repository | Initial status |
|---:|---|---|---|
| 1 | Remove test data | Inspect production database and startup/deployment process for demo records. | Not checked |
| 2 | Hide API keys | Scan tracked files and Git history for secrets; rotate any exposed credentials. | Not checked |
| 3 | Protect admin routes | No admin routes were identified in the reviewed `main.py`; mark N/A only after confirming the full app has none. | Not checked |
| 4 | Authentication and permissions | The reviewed API code does not show authentication; decide whether endpoints should be public and add access control if needed. | Not checked |
| 5 | Database rules | Review SQLite file permissions, DB path, and who can access run history. No user-level ownership checks are shown in the reviewed code. | Not checked |
| 6 | Validate inputs | Test corruption name, severity levels, IoU bounds, seed, and malformed inputs. Current code checks corruption name and numeric severity parsing; IoU bounds need review. | Not checked |
| 7 | API rate limits | No rate limiter was identified in the reviewed API file. Decide and implement a limit if this API will be exposed publicly. | Not checked |
| 8 | File upload security | Test malformed images, allowed formats, image dimensions, and upload size. The reviewed code decodes images but does not enforce an explicit request-size limit. | Not checked |
| 9 | API errors | Test invalid images, invalid corruption names, missing run IDs, and unexpected processing failures. | Not checked |
| 10 | Remove debug logs | Review logging configuration and verify sensitive values are not logged. | Not checked |
| 11 | Hide sensitive errors | Ensure unexpected exceptions do not expose stack traces, local paths, or secrets to clients. | Not checked |
| 12 | Mobile layout | Manually or automatically test the React UI at narrow viewport widths. Frontend test dependencies are not present in the supplied `package.json`. | Not checked |
| 13 | Slow internet | Test delayed/failed `/api/analyze` requests, loading state, error display, and retry behavior. | Not checked |
| 14 | Payments and webhooks | No payment or webhook functionality was identified in the reviewed files. Confirm with the team; if absent, document N/A. | Not checked |
| 15 | Try to break the app | Test malformed requests, large uploads, invalid parameters, missing run IDs, and concurrent requests in a safe test environment. | Not checked |

## Source observations

- `backend/main.py` configures CORS with `allow_origins=["*"]`.
  Review and restrict origins for deployment if the API is not intended to be open to all browser origins.
- `backend/main.py` reads the complete uploaded file into memory and has no explicit upload-size limit.
- `backend/main.py` accepts an IoU form value without an explicit 0-to-1 validation check.
- The reviewed API file does not show authentication or rate limiting.
- `backend/core.py` contains pure functions suitable for fast unit tests.
- `frontend/package.json` defines Vite/build scripts but no frontend test script.

These observations are based on the files included in the supplied repository ZIP. Re-check the current branch before treating them as current deployment findings.
