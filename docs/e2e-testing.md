# VisionGuard End-to-End Automated Browser Testing

## 1. Overview
VisionGuard utilizes [Playwright](https://playwright.dev/) for reproducible, automated browser testing of the full web application. The test suite exercises the complete lifecycle from submission to PyTorch Faster R-CNN inference, report persistence, and visual bounding-box canvas rendering against the real FastAPI backend and Vite frontend.

- **Configuration:** `frontend/playwright.config.ts`
- **Test Specifications:** `frontend/e2e/visionguard.spec.ts`, `frontend/e2e/worker_mode.spec.ts`
- **Output Artifacts:** `frontend/playwright-report/` (HTML report), `frontend/test-results/` (traces/videos)

---

## 2. Test Execution Commands

From the `frontend/` directory:

```powershell
# Run all end-to-end browser tests headlessly
npm run test:e2e

# Run Playwright in interactive UI mode
npm run test:e2e:ui

# View HTML test report
npx playwright show-report
```

---

## 3. Test Scenarios Implemented

| Scenario | Scope & Verifications | Status |
|---|---|---|
| **Scenario A — Application Startup** | Verifies root `/dashboard` rendering, header navigation links, FastAPI `/health` connectivity status (`Backend Connected`), navigation to `/new`, and dynamic loading of model and dataset catalogs (`visionguard_demo`). | **PASSED** |
| **Scenario B — Evaluation Submission** | Selects Faster R-CNN model, `visionguard_demo` dataset, activates Blur Severity 1 preset, submits evaluation form, captures `202 Accepted` response from `POST /api/v1/runs`, and verifies navigation to `/runs/:id`. | **PASSED** |
| **Scenario C — Run Lifecycle** | Monitors run status transition through `QUEUED` / `RUNNING` to terminal `COMPLETED` state under real Faster R-CNN inference. Confirms polling stops once terminal state is reached. | **PASSED** |
| **Scenario D — Report Display** | Validates retention, class consistency, and matched IoU summary cards. Verifies condition metrics table and confirms reference-free disclosure is visible while ground-truth accuracy metrics (mAP, precision, recall) are omitted. | **PASSED** |
| **Scenario E — Failure Visualization** | Navigates to `/runs/:id/failures`, validates side-by-side canvas rendering of clean and corrupted images, verifies client-side bounding box overlays, class tags, and confidence percentages. | **PASSED** |
| **Scenario F — Refresh Persistence** | Reloads the active run page, ensuring all run status, summary metrics, and report data persist from the database after a hard page refresh. | **PASSED** |
| **Scenario G — Error Handling** | Tests navigation to non-existent UUID (`/runs/non-existent-uuid-...`), verifies 404 error notification without application crash, and verifies Settings & Glossary page rendering. | **PASSED** |
| **Scenario H — Independent Worker Mode** | Creates a `QUEUED` run, invokes the decoupled evaluation worker process (`python -m backend.app.worker <run_id>`), verifies CUDA/CPU execution and report generation, and confirms frontend reflects `COMPLETED` state. | **PASSED** |

---

## 4. Test Environment Isolation

To ensure absolute safety and isolation:
- Tests communicate with a local FastAPI test server running with `TEST_DATABASE_URL` pointing to an isolated SQLite database (`scratch/test_e2e.db`).
- The production Neon PostgreSQL database is NEVER touched by automated browser test runs.
- The real PyTorch Faster R-CNN evaluation engine processes the registered `visionguard_demo` benchmark dataset (10 images).
