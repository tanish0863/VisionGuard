# 02 — Software Requirements Specification (SRS)

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Tanish |
| Stage | 1 |
| Sources | Architecture §3, §5; Master Plan §B, §J, §K |

Requirement IDs use `FR-###` / `NFR-###`. The "Arch" column maps to the `FR-01…FR-15` identifiers in Architecture §3.1 for traceability. Priorities: P0 must ship, P1 strong addition, P2 stretch.

---

## 1. Functional requirements

### 1.1 Dataset input and validation

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-001 | Accept a single image (`.jpg .jpeg .png .webp .bmp`) | Supported image is loaded as EXIF-normalized RGB uint8; `dataset_id` returned | P0 | FR-01 |
| FR-002 | Accept a COCO-format zip (`images/`, `annotations.json`) | Valid zip yields dataset with `has_labels=true`, boxes converted to `xyxy` once | P1 | FR-01 |
| FR-003 | Validate type (magic bytes), size, dimensions, annotation structure, class IDs, boxes | Invalid input returns field-level error with stable code; nothing half-ingested | P0 | FR-02 |
| FR-004 | Reject unsafe archives | Path traversal, symlinks, oversize or too many entries → `INVALID_ARCHIVE` | P0 | FR-02 |
| FR-005 | Map dataset classes to model classes by normalized name | Unmapped classes excluded from GT metrics and listed in `warnings` | P1 | FR-02 |
| FR-006 | Provide a bundled sample dataset | Quick-start button runs without upload | P0 | — |

### 1.2 Model selection and inference

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-007 | List available models | `GET /models` returns id, name, version, device, `is_mock` | P0 | FR-03 |
| FR-008 | Run clean inference via the model adapter | Returns normalized predictions in original-image pixel coordinates, sorted by confidence | P0 | FR-03 |
| FR-009 | Use identical inference settings for clean and degraded images | Settings recorded in manifest; asserted equal in tests | P0 | FR-05 |
| FR-010 | Return all detections above a low confidence floor | Thresholding at τ happens downstream, not in the adapter | P0 | FR-03 |
| FR-011 | Mock adapter for development, impossible to select in demo config | Reports from mock carry `is_mock: true` | P0 | — |

### 1.3 Image corruption

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-012 | Apply seeded corruptions with severities 1–3 | Output shape preserved (geometry-preserving types); params recorded | P0 | FR-04 |
| FR-013 | Deterministic output | Same image, corruption, severity, seed, library versions ⇒ identical pixels | P0 | FR-04 |
| FR-014 | Never mutate the original | Input buffer unchanged after `apply` | P0 | FR-04 |
| FR-015 | Resolution-independent parameters | Spatial params scaled from a 640-px reference short side; scaled value recorded | P0 | FR-04 |
| FR-016 | Expose catalog and presets | `GET /corruptions`, `GET /presets` drive UI controls | P0/P1 | FR-04 |

### 1.4 Degraded inference and prediction comparison

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-017 | Run inference for every (corruption, severity) condition | Each condition has per-image predictions or an `ERROR` status | P0 | FR-05 |
| FR-018 | Match baseline ↔ corrupted detections one-to-one per class (Hungarian, IoU ≥ θ) | One corrupted box never matches two baseline boxes | P0 | FR-06 |
| FR-019 | Detect class flips without double counting | Flips removed from lost / unmatched counts | P0 | FR-06 |
| FR-020 | Compute consistency metrics | `retention`, `loss_rate`, `mean_confidence_delta`, `mean_matched_iou`, `class_flip_rate`, `unmatched_corrupted_rate`, latency | P0 | FR-06 |
| FR-021 | Undefined metrics are `null` with a reason | e.g. `NO_BASELINE_DETECTIONS`; never 0 or NaN | P0 | FR-06 |
| FR-022 | Compute ground-truth metrics when labels exist | precision, recall, F1, mAP@0.5, mAP@0.5:0.95 via standard evaluator | P1 | FR-07 |
| FR-023 | Reject GT metrics on unlabeled data at creation | `422 METRIC_UNAVAILABLE` before the run starts | P0 | FR-07 |
| FR-024 | Compute absolute and relative deltas vs clean | per condition, in report | P0 | FR-08 |
| FR-025 | Bootstrap confidence intervals | 95 % CI for retention and mAP50 deltas; small-sample banner for N < 30 | P1 | — |

### 1.5 Failure analysis

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-026 | Classify failures by taxonomy | `LOST_DETECTION`, `CLASS_FLIP`, `LOCALIZATION_SHIFT`, `CONFIDENCE_DROP`, `NEW_DETECTION` (+ `GT_*` in labeled mode) | P0 | FR-09 |
| FR-027 | Rank failures | Heuristic score orders gallery only; never shown as a metric | P0 | FR-09 |
| FR-028 | Persist top-K failure images per condition | Default K = 20; others JSON-only | P0 | FR-09 |
| FR-029 | Show before/after overlays | Overlays rendered client-side from JSON | P0 | FR-09 |

### 1.6 Report generation

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-030 | Generate `report.json` with manifest | Valid against schema; contains only metrics computed in the run | P0 | FR-10 |
| FR-031 | Auto-generated limitations text | Wording switches on `has_labels` | P0 | FR-10 |
| FR-032 | Self-contained HTML report | Opens offline; top failures embedded as data-URIs | P1 | FR-10 |

### 1.7 Run management

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-033 | Persist runs; reopen after restart | Completed run viewable after backend restart | P0 | FR-12 |
| FR-034 | Run lifecycle states | `QUEUED → RUNNING → COMPLETED / PARTIAL / FAILED / CANCELLED` | P0 | FR-12 |
| FR-035 | Progress reporting | `{stage, done, total}` via polling | P1 | FR-13 |
| FR-036 | Cooperative cancellation | Flag checked between images | P1 | FR-13 |
| FR-037 | Mark orphaned `RUNNING` runs `FAILED/INTERRUPTED` on startup | Verified by restart test | P0 | — |
| FR-038 | List and filter runs | Dashboard shows status, gate verdict | P0 | FR-12 |

### 1.8 Regression checking

| ID | Requirement | Acceptance criteria | Pri | Arch |
| --- | --- | --- | --- | --- |
| FR-039 | Evaluate declarative gate rules | Verdict `PASS`/`FAIL`/`ERROR` with per-rule evidence | P1 | FR-11 |
| FR-040 | Never silently pass | Any errored rule or partial run ⇒ `ERROR` | P1 | FR-11 |
| FR-041 | CLI parity with exit codes | 0 PASS/no gate, 1 FAIL, 2 ERROR/FAILED/PARTIAL, 64 usage | P1 | FR-14 |
| FR-042 | Replay a run from its manifest | Reports whether results match | P2 | FR-15 |

---

## 2. Non-functional requirements

| ID | Quality | Requirement | Verification |
| --- | --- | --- | --- |
| NFR-001 | Performance | Baseline computed once; predictions cached by content hash; one inference stream. **No numeric targets until measured (M-1).** | Cache-hit test; timing measured on demo machine |
| NFR-002 | Reliability | Failure yields a structured error; never fake or mock data substituted | Fault-injection tests |
| NFR-003 | Reproducibility | Manifest stores input hashes, model identity/weights SHA-256, library versions, corruption params, seeds | Manifest completeness test; replay (P2) |
| NFR-004 | Security | Untrusted uploads handled safely (see 03 §12) | Security test cases |
| NFR-005 | Maintainability | Add a model, corruption or metric without editing the orchestrator (registries + ABCs) | Review: no orchestrator diff when adding a corruption |
| NFR-006 | Modularity | One-directional dependencies; core has zero web imports | `import-linter` in CI (optional) |
| NFR-007 | Usability | Metric glossary in UI; limitations in every report; consistency vs ground-truth badges | UI review |
| NFR-008 | Compatibility | Windows + Linux; `pathlib` everywhere; no fork-only multiprocessing | CI/manual run on Windows |
| NFR-009 | Honesty | No claim beyond the evidence; "we did not find" not "no one has" | Pitch review |
| NFR-010 | Observability | Structured logs with `run_id`; no full images logged | Log inspection |

## 3. User roles

No authentication in MVP. Single implicit role: **operator** (can create datasets, start/cancel runs, view and export reports). Roles are a future item.

## 4. Input constraints

| Item | Constraint |
| --- | --- |
| Image formats | `.jpg .jpeg .png .webp .bmp`, verified by magic bytes |
| Upload size | ≤ `MAX_UPLOAD_MB` (starting default 10, Master Plan §N1) |
| Image pixels | ≤ `MAX_IMAGE_PIXELS` (starting default 20,000,000) |
| Dataset size | ≤ `MAX_IMAGES` (placeholder 200, set after M-1) |
| Conditions per run | 1–24 (placeholder cap) |
| Severity | Integer 1–3 (range declared per corruption by the catalog) |
| Thresholds | τ and θ in (0, 1); defaults 0.25 and 0.5 |
| Annotations | COCO detection format; `bbox=[x,y,w,h]` pixels; `x≥0,y≥0,w>0,h>0` |

## 5. Output constraints

- Boxes: `bbox_xyxy`, absolute pixels, original (EXIF-normalized) image, origin top-left.
- Confidence: decimal in [0, 1] everywhere; percent is UI-only.
- No detections: `"predictions": []`, never `null`.
- Unlabeled `ground_truth` is `null`, not `[]`.
- Reports are JSON (authoritative) with optional HTML.

## 6. System limitations

See PRD §12. Additionally: single worker (one run at a time), single process (no multi-worker Uvicorn), local-first demo.

## 7. Feature acceptance summary (Definition of Done for MVP)

- [ ] Application starts from documented commands on a clean machine
- [ ] Actual model inference used in the demo
- [ ] Three corruptions run from the UI
- [ ] Baseline and degraded predictions comparable
- [ ] Metrics have definitions and automated tests
- [ ] Run settings and model version saved
- [ ] Report or result summary exportable
- [ ] All five members can explain the pipeline
- [ ] Pitch avoids unsupported performance/novelty claims
