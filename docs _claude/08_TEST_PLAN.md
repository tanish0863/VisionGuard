# 08 — Test Plan and Test Cases

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Aditya |
| Stage | 3 — evolves during development |
| Sources | Architecture §14 (referenced), Master Plan §J; test cases drafted from SRS 02 and methodology 07 |

Actual output / status columns are filled during execution. Status values: `NOT RUN`, `PASS`, `FAIL`, `BLOCKED`.

## 1. Test categories

| Category | What to test | Tooling | Owner |
| --- | --- | --- | --- |
| Unit | Individual functions (IoU, loaders, seeds) | pytest | Module owner |
| Integration | Communication between modules (orchestrator ↔ adapter ↔ metrics) | pytest | Tanish |
| API | Requests, responses, status codes, error envelope | pytest + FastAPI `TestClient` | Member 5 (TBC) |
| Model | Model loading, prediction format, no-detection case | pytest | Chinmay |
| Corruption | Shape, determinism, no mutation, seed, severity validation | pytest | Chinmay |
| Metric | Hand-checked values, undefined cases | pytest | Aditya |
| UI | Dashboard interactions, states | Frontend tests / manual script | Vanashree |
| End-to-end | Fresh start → sample → run → history → export | Manual script + scripted API run | All |

## 2. Entry / exit criteria and quality gates

- **Merge gate (per PR):** unit + relevant integration tests pass; lint passes; schema/API changes include updated fixtures.
- **Release gate:** backend tests pass; frontend production build succeeds; no secret or absolute local path required; sample image and demo steps work offline; all charts built from API data; normal path **and** an expected error path rehearsed.
- **Feature freeze check:** E2E script passes on a clean checkout.

## 3. Test data and fixtures

| Fixture | Location | Use |
| --- | --- | --- |
| Sample image(s) with known detections | `backend/tests/fixtures/images/` | Model/API/E2E |
| Tiny COCO zip (3 images, known GT) | `fixtures/datasets/tiny_coco.zip` | Dataset, GT metrics |
| Bad inputs (corrupt JPEG, `.txt`, oversized, zip-slip, bad annotation) | `fixtures/bad/` | Validation |
| Known-good expected response | `fixtures/expected/run_report.json` | Contract tests |
| Hand-built prediction pairs | `fixtures/predictions/*.json` | Matching/metrics |
| `MockAdapter` | `visionguard/models/mock_adapter.py` | CI without weights |

## 4. Test cases

### 4.1 Dataset and input (unit/API)

| ID | Objective | Input | Steps | Expected result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-001 | Load valid image | `sample.jpg` | `POST /datasets` | 201; `dataset_id`; `has_labels=false` | | NOT RUN |
| TC-002 | Reject unsupported file | `notes.txt` renamed `.jpg` | `POST /datasets` | 400 `UNSUPPORTED_FORMAT`/`INVALID_IMAGE` (magic bytes) | | NOT RUN |
| TC-007 | Reject corrupt image | truncated JPEG | upload | 400 `INVALID_IMAGE`; nothing stored | | NOT RUN |
| TC-008 | Oversize file | file > `MAX_UPLOAD_MB` | upload | 413 `IMAGE_TOO_LARGE` | | NOT RUN |
| TC-009 | Zip path traversal | zip containing `../x.jpg` | upload | 400 `INVALID_ARCHIVE`; nothing extracted | | NOT RUN |
| TC-010 | Invalid annotation | box with `w<=0` | upload COCO zip | 400 `INVALID_ANNOTATION` with field detail | | NOT RUN |
| TC-011 | EXIF orientation | rotated phone photo | load | Pixels and boxes consistent; dims reflect rotation | | NOT RUN |
| TC-012 | Class map exclusion | dataset class absent in model | upload | Class in `excluded_classes` + warning | | NOT RUN |
| TC-013 | COCO `xywh→xyxy` | box `[10,20,30,40]` | load | `bbox_xyxy=[10,20,40,60]` | | NOT RUN |

### 4.2 Corruption

| ID | Objective | Input | Steps | Expected result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-003 | Apply Gaussian blur | sample, sev 2 | `apply` | Image generated, same shape/dtype, differs from input | | NOT RUN |
| TC-014 | Determinism | same args twice | apply ×2 | Byte-identical outputs | | NOT RUN |
| TC-015 | No mutation | input copy | apply | Input unchanged | | NOT RUN |
| TC-016 | Seed independence | conditions in different order | derive seeds | Same seed per (image, corruption, severity) | | NOT RUN |
| TC-017 | Resolution scaling | 320 vs 1280 short side | `params_for` | σ scales by short_side/640 and is recorded | | NOT RUN |
| TC-018 | Severity validation | severity 0 and 4 | apply | `INVALID_SEVERITY` | | NOT RUN |
| TC-019 | Low-light in linear space | mid-gray pixel | apply sev 1 | Matches linear-light formula, not naive multiply | | NOT RUN |
| TC-020 | Noise statistics | flat image | apply | Sample std ≈ σ within tolerance; values clipped | | NOT RUN |
| TC-021 | JPEG quality effect | sample | apply q=15 | Output differs; shape preserved | | NOT RUN |
| TC-022 | Unknown corruption | `type="foo"` | `POST /runs` | 422 `UNKNOWN_CORRUPTION` | | NOT RUN |

### 4.3 Model

| ID | Objective | Input | Steps | Expected result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-023 | Model loads | pinned weights | `load()`; `/health` | `model_loaded=true` | | NOT RUN |
| TC-024 | Prediction format | sample | `predict` | Conforms to PredictionResult: xyxy, 0–1 conf, sorted | | NOT RUN |
| TC-025 | Original-pixel coordinates | non-square image | `predict` | Boxes within `[0,W]×[0,H]` (letterbox undone) | | NOT RUN |
| TC-026 | No detections | blank image | `predict` | `predictions: []` | | NOT RUN |
| TC-027 | Weights checksum mismatch | altered file | startup | `503 MODEL_UNAVAILABLE`; no fake output | | NOT RUN |
| TC-028 | Mock flagged | `MockAdapter` | run + report | `is_mock: true`; not selectable in demo config | | NOT RUN |

### 4.4 Metrics and matching

| ID | Objective | Input | Steps | Expected result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-004 | Compare identical predictions | B = C | match | Retention 100 % (1.0) | | NOT RUN |
| TC-005 | Remove one matched detection | B has 2, C has 1 | match | Retention decreases (0.5) | | NOT RUN |
| TC-029 | Wrong class, same box | person vs dog | match | Class flip counted; not also lost/unmatched | | NOT RUN |
| TC-030 | Overlapping candidates | 1 baseline, 2 overlapping corrupted | match | One-to-one; second becomes unmatched | | NOT RUN |
| TC-031 | IoU below θ | IoU 0.45, θ 0.5 | match | No match | | NOT RUN |
| TC-032 | Zero baseline detections | B empty | metrics | retention `null`, `NO_BASELINE_DETECTIONS` | | NOT RUN |
| TC-033 | Zero corrupted detections | C empty | metrics | retention 0; rates handled (`unmatched_corrupted_rate` `null`) | | NOT RUN |
| TC-034 | Confidence delta | known pairs | metrics | Equals hand-computed mean | | NOT RUN |
| TC-035 | IoU function | known boxes, disjoint, identical, zero-area | iou | Hand-checked values; no divide-by-zero | | NOT RUN |
| TC-036 | τ applied to both sides | detections 0.2 / 0.3 | metrics τ=0.25 | Only 0.3 counted on both | | NOT RUN |
| TC-037 | Precision/recall/F1 | tiny GT fixture | metrics | Matches hand-computed TP/FP/FN | | NOT RUN |
| TC-038 | mAP vs pycocotools | tiny GT fixture | evaluate | Equals direct `pycocotools` result | | NOT RUN |
| TC-039 | GT metric on unlabeled data | image-only dataset + `map50` | `POST /runs` | 422 `METRIC_UNAVAILABLE` at creation | | NOT RUN |
| TC-040 | Micro-average | 2 images, different counts | aggregate | `Σ|M|/Σ|B|`, not mean of ratios | | NOT RUN |
| TC-041 | Bootstrap reproducible | fixed seed | bootstrap ×2 | Identical CI; N=1 → no CI | | NOT RUN |

### 4.5 Failure analysis, gate, report

| ID | Objective | Input | Steps | Expected result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-042 | Failure classification | crafted pairs | analyze | Each type correctly assigned | | NOT RUN |
| TC-043 | Ranking order | lost 0.95 vs lost 0.30 | rank | 0.95 ranks higher | | NOT RUN |
| TC-044 | Top-K artifact policy | 50 failures, K=20 | run | 20 images persisted; 50 JSON records | | NOT RUN |
| TC-045 | Gate PASS | rule satisfied | evaluate | PASS with evidence | | NOT RUN |
| TC-046 | Gate FAIL | rule violated | evaluate | FAIL | | NOT RUN |
| TC-047 | Gate ERROR never silent pass | undefined metric / failed condition | evaluate | ERROR | | NOT RUN |
| TC-006 | Generate report | completed run | `GET /report` | Valid JSON report validating against schema | | NOT RUN |
| TC-048 | Report honesty | unlabeled run | inspect `limitations` | States consistency ≠ accuracy; no GT metrics present | | NOT RUN |
| TC-049 | Manifest completeness | completed run | inspect | All manifest fields present incl. seeds, hashes | | NOT RUN |
| TC-050 | HTML export offline | completed run | open file offline | Renders with embedded images | | NOT RUN |

### 4.6 Run management and API

| ID | Objective | Input | Steps | Expected result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TC-051 | Create run | valid config | `POST /runs` | 202 `QUEUED` quickly | | NOT RUN |
| TC-052 | Status lifecycle | valid run | poll | `QUEUED→RUNNING→COMPLETED` with progress | | NOT RUN |
| TC-053 | Unknown run | bad ID | `GET /runs/x` | 404 `RUN_NOT_FOUND` | | NOT RUN |
| TC-054 | Persistence after restart | completed run | restart backend | Run listed and report retrievable | | NOT RUN |
| TC-055 | Orphan recovery | kill during run | restart | Run `FAILED/INTERRUPTED` | | NOT RUN |
| TC-056 | Cancel | running run | `POST /cancel` | `CANCELLED` between images | | NOT RUN |
| TC-057 | Partial run | force one condition to error | run | `PARTIAL`; gate `ERROR`; others reported | | NOT RUN |
| TC-058 | Missing artifact | non-persisted id | `GET artifact` | 404 `ARTIFACT_NOT_FOUND`; run intact | | NOT RUN |
| TC-059 | Error envelope shape | any 4xx | inspect | `{error:{code,message,details,request_id}}`; no stack trace | | NOT RUN |
| TC-060 | Artifact path safety | `../../etc/passwd` as id | request | 404; no filesystem access | | NOT RUN |
| TC-061 | Same-seed reproducibility | same config twice | compare | Identical corrupted pixels; metrics equal within documented nondeterminism | | NOT RUN |
| TC-062 | OpenAPI/types in sync | regenerate types | CI step | No diff in `api.gen.ts` | | NOT RUN |

### 4.7 CLI

| ID | Objective | Expected result | Status |
| --- | --- | --- | --- |
| TC-063 | Gate PASS | exit code 0 | NOT RUN |
| TC-064 | Gate FAIL | exit code 1 | NOT RUN |
| TC-065 | Gate ERROR / run FAILED / PARTIAL | exit code 2 | NOT RUN |
| TC-066 | Invalid arguments | exit code 64 | NOT RUN |

### 4.8 UI

| ID | Objective | Steps | Expected result | Status |
| --- | --- | --- | --- | --- |
| TC-067 | Dashboard empty | open with no runs | Empty state + quick-start | NOT RUN |
| TC-068 | New evaluation validation | no corruption selected | Run disabled/field error | NOT RUN |
| TC-069 | Progress display | start run | Stage + done/total updates; polling stops at terminal | NOT RUN |
| TC-070 | Metric badges | open results | Each card shows CONSISTENCY/GROUND TRUTH badge and tooltip | NOT RUN |
| TC-071 | Overlay alignment | open failure | Boxes align with objects on non-square image | NOT RUN |
| TC-072 | Failed run | induce `MODEL_UNAVAILABLE` | Visible error panel; no fake data | NOT RUN |
| TC-073 | Partial run banner | induce partial | Banner + gate `ERROR` | NOT RUN |
| TC-074 | Small sample banner | N<30 | Banner shown; N=1 caveat | NOT RUN |
| TC-075 | Filters | apply filter with no results | "No results" + Clear filters | NOT RUN |

### 4.9 End-to-end

| ID | Scenario | Steps | Expected result | Status |
| --- | --- | --- | --- | --- |
| TC-076 | Fresh start demo | Clean checkout → README commands → `/health` → sample → run (3 corruptions) → history → export | Completes without manual DB edits | NOT RUN |
| TC-077 | Labeled flow (P1) | Upload tiny COCO zip → run → GT metrics visible | precision/recall/mAP shown with GROUND TRUTH badge | NOT RUN |
| TC-078 | Error path rehearsal | Upload invalid file in demo | Clear error, app recovers | NOT RUN |
| TC-079 | Offline | Disable network | Demo still works (local model/samples) | NOT RUN |
| TC-080 | Windows run | Execute TC-076 on Windows | Passes | NOT RUN |

## 5. Security test cases

| ID | Test | Expected |
| --- | --- | --- |
| SEC-01 | Zip bomb (huge uncompressed size) | Rejected before extraction |
| SEC-02 | Symlink in zip | Rejected |
| SEC-03 | Filename with path chars / null bytes | Stored under server-generated name |
| SEC-04 | `model_id` containing a path | 404/422; no file access |
| SEC-05 | CORS from unlisted origin | Blocked |
| SEC-06 | Error responses | No stack traces or absolute paths |

## 6. Defect handling

Log defects as issues with: test ID, build/commit, steps, expected vs actual, severity (blocker / major / minor). Blockers on P0 features stop merges to `main`.

## 7. Metrics of testing progress

Track: pass/total by category, open blockers, P0 coverage (every P0 SRS requirement has ≥ 1 passing test — see traceability below).

## 8. Requirement traceability (excerpt)

| SRS ID | Tests |
| --- | --- |
| FR-001/003 | TC-001, 002, 007, 008 |
| FR-004 | TC-009, SEC-01/02 |
| FR-012–015 | TC-003, 014–021 |
| FR-018–021 | TC-004, 005, 029–036 |
| FR-022/023 | TC-037–039 |
| FR-026–028 | TC-042–044 |
| FR-030–032 | TC-006, 048–050 |
| FR-033–037 | TC-051–058 |
| FR-039–041 | TC-045–047, 063–066 |
