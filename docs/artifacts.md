# VisionGuard Artifacts System

## Overview

During model evaluation, VisionGuard evaluates object detectors against clean images and procedurally corrupted variants.

The frontend requires access to:
1. Original clean images.
2. Corrupted image variants evaluated by the model.
3. Prediction overlay visualizations (when available).

---

## Artifact Endpoints

- **List Artifacts:** `GET /api/v1/runs/{run_id}/artifacts`
- **Retrieve Image:** `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}`

### Artifact ID Convention

Artifact IDs follow a deterministic, URL-safe scheme:
- **Clean Image:** `<image_id>__clean` (e.g. `01_street_urban__clean`)
- **Corrupted Image:** `<image_id>__<corruption_name>_s<severity>` (e.g. `01_street_urban__gaussian_noise_s2`)
- **Overlay Visualization:** `<image_id>__overlay` (e.g. `01_street_urban__overlay`)

---

## Security Boundaries & Path Traversal Prevention

1. **Strict Root Boundary:** Artifact paths are resolved strictly within registered dataset storage roots (e.g. `backend/visionguard/datasets/visionguard_demo`).
2. **Path Traversal Defense:**
   - Any attempt to access paths containing relative traversal tokens (`..`), absolute Windows paths (`C:\...`), or paths outside registered root directories is immediately rejected with `403 Forbidden` or `404 Not Found`.
3. **Run Isolation:** The requested artifact must match an image evaluated in the specified `run_id` report.
4. **No Arbitrary File Serving:** Source code, configuration files (`.env`), model checkpoints, and database files can never be served through the artifact API.

---

## Clean vs. Corrupted vs. Overlay Support

| Artifact Type | Available | Storage / Generation Strategy |
|---|---|---|
| Clean Image | Yes | Served directly from registered dataset directory. |
| Corrupted Image | Yes | Synthesized deterministically using the evaluation run's seed and corruption parameters. |
| Overlays | No (HTTP 404) | Not pre-rendered server-side to save disk/RAM. Bounding boxes (`bbox_xyxy`, `labels`, `scores`) are returned in the evaluation report so the frontend can render crisp SVG/Canvas bounding box overlays client-side. |
