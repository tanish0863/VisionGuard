# 05 — API Specification

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Member 5 (TBC) with Tanish (backend) |
| Stage | 2 |
| Basis | Architecture §4.1, §5.2, §6, §7.3; Master Plan §G, §I4. Endpoints beyond `datasets`/`runs`/`catalog` are **`[PROPOSED]`** |

> **Single source of truth:** Pydantic models in `backend/visionguard/schemas/`. This document is a human-readable view; the live contract is FastAPI's OpenAPI at `/docs` and `/openapi.json`. If this file and the code disagree, **fix one in the same PR** — never maintain two contradictory contracts. Sample fixtures live in `backend/tests/fixtures/`.

## 1. Conventions

| Item | Rule |
| --- | --- |
| Base URL (dev) | `http://localhost:8000/api/v1` (frontend proxies `/api`) |
| Content type | JSON; uploads use `multipart/form-data` |
| IDs | Opaque strings: `ds_…`, `run_…`, `art_…`, `fail_…` |
| Timestamps | ISO-8601 UTC (`2026-10-24T10:02:11Z`) |
| Confidence | Decimal 0.0–1.0 |
| Boxes | `bbox_xyxy`, absolute pixels, original image |
| Versioning | Path prefix `/api/v1`; schema objects carry `schema_version: "1.0"` |
| Auth | None in MVP |
| Errors | Standard envelope (§4) |

## 2. Endpoint summary

| Method | Endpoint | Description | Pri |
| --- | --- | --- | --- |
| GET | `/health` | Backend and model health | P0 |
| GET | `/models` | Available detectors | P0 |
| GET | `/corruptions` | Corruption catalog (declares severity ranges) | P0 |
| GET | `/presets` | Scenario presets | P1 |
| POST | `/datasets` | Register/upload dataset (image or COCO zip) | P0 |
| GET | `/datasets` / `/datasets/{id}` | List / fetch dataset | P0 |
| POST | `/runs` | Start evaluation | P0 |
| GET | `/runs` | List runs | P0 |
| GET | `/runs/{id}` | Run status and progress | P0 |
| POST | `/runs/{id}/cancel` | Request cancellation | P1 |
| GET | `/runs/{id}/report` | Retrieve report (`?format=json|html`) | P0/P1 |
| GET | `/runs/{id}/failures` | Ranked failure cases (filterable) | P0 |
| GET | `/runs/{id}/artifacts/{artifact_id}` | Image/report artifact | P0 |
| POST | `/runs/{id}/replay` | Re-execute from manifest | P2 |

## 3. Run status lifecycle

`QUEUED → RUNNING → COMPLETED | PARTIAL | FAILED | CANCELLED`

| Status | Meaning | Terminal |
| --- | --- | --- |
| QUEUED | Accepted, waiting for the single worker | no |
| RUNNING | `stage` ∈ `VALIDATING, BASELINE, CONDITIONS, AGGREGATING, ANALYZING_FAILURES, GATE, REPORTING` | no |
| COMPLETED | All conditions OK, report written | yes |
| PARTIAL | Some conditions failed; report written; gate = `ERROR` | yes |
| FAILED | Baseline or fatal error (incl. `INTERRUPTED`) | yes |
| CANCELLED | Cancel observed between images | yes |

Frontend polls `GET /runs/{id}` every 1 s until terminal.

## 4. Error format and status codes

```json
{ "error": { "code": "INVALID_CONFIG", "message": "Invalid evaluation configuration.",
             "details": [ { "field": "corruptions[0].severities[1]", "issue": "must be between 1 and 3" } ],
             "request_id": "req_01J8Z7" } }
```

| Status | When |
| --- | --- |
| 200 | OK |
| 201 | Dataset created |
| 202 | Run accepted |
| 400 | Bad file/archive/annotation (`INVALID_IMAGE`, `UNSUPPORTED_FORMAT`, `INVALID_ANNOTATION`, `INVALID_ARCHIVE`) |
| 404 | Unknown dataset/model/run/artifact |
| 409 | State conflict (`RUN_NOT_CANCELLABLE`, `RUN_NOT_COMPLETE`) |
| 413 | Too large (`IMAGE_TOO_LARGE`, `DATASET_TOO_LARGE`) |
| 422 | Validation (`INVALID_CONFIG`, `METRIC_UNAVAILABLE`, `UNKNOWN_CORRUPTION`, `INVALID_SEVERITY`, `CLASS_MAP_EMPTY`) |
| 500 | `INFERENCE_FAILED`, `INTERNAL` — no stack traces in body |
| 503 | `MODEL_UNAVAILABLE`, `RESOURCE_EXHAUSTED` — no fake detections |

## 5. Endpoints

### GET `/health`

```json
{ "status": "ok", "model_loaded": true, "model_id": "yolo-nano-default", "is_mock": false, "version": "0.1.0" }
```
`model_loaded: false` while loading → UI shows "loading". Failed load → `status: "degraded"`.

### GET `/models`

```json
{ "models": [ { "model_id": "yolo-nano-default", "name": "<name>", "version": "<pinned>",
                "weights_sha256": "<hex>", "device": "cuda:0", "is_mock": false, "num_classes": 80 } ] }
```

### GET `/corruptions`

```json
{ "corruptions": [
  { "id": "gaussian_blur", "family": "blur", "geometry_preserving": true,
    "severities": [1, 2, 3], "labels": ["Mild", "Moderate", "Severe"], "priority": "P0",
    "params_at_reference": { "1": {"sigma": 1.0}, "2": {"sigma": 2.5}, "3": {"sigma": 5.0} } } ] }
```

### GET `/presets`

```json
{ "presets": [ { "id": "night_driving", "description": "Low light + noise + motion blur",
                 "corruptions": [ {"type": "low_light", "severities": [1,2,3]},
                                  {"type": "gaussian_noise", "severities": [1,2,3]},
                                  {"type": "motion_blur", "severities": [1,2,3]} ],
                 "disclaimer": "A convenience for choosing corruptions, not a validated scenario." } ] }
```

### POST `/datasets`

`multipart/form-data`: `file` (image or `.zip`), `name` (optional), `skip_invalid` (bool, default false), `class_map` (optional JSON override).

Response `201`:

```json
{ "dataset_id": "ds_01J8Z3K4", "name": "street_sample", "has_labels": true, "num_images": 24,
  "dataset_sha256": "<hex>",
  "class_map": [ { "dataset_category_id": 1, "dataset_name": "person", "model_class_id": 0, "included": true } ],
  "excluded_classes": [], "warnings": [ { "code": "DUPLICATE_IMAGE", "detail": "000007.jpg == 000003.jpg" } ] }
```
Errors: `400 INVALID_ARCHIVE` example:
```json
{ "error": { "code": "INVALID_ARCHIVE", "message": "Archive contains an unsafe path.",
             "details": [ { "field": "file", "issue": "entry '../x.jpg' escapes extraction root" } ], "request_id": "req_01J8Z8" } }
```

### GET `/datasets`, GET `/datasets/{id}`
List returns `{ "datasets": [ {dataset_id, name, has_labels, num_images, created_at} ] }`. Detail returns the dataset schema (06 §2), without image bytes.

### POST `/runs`

Request body = `RunConfig` (06 §8). Realistic example:

```json
{ "schema_version": "1.0", "dataset_id": "ds_01J8Z3K4", "model_id": "yolo-nano-default", "preset": null,
  "corruptions": [ { "type": "gaussian_blur", "severities": [1,2,3] },
                   { "type": "low_light", "severities": [1,2,3] },
                   { "type": "gaussian_noise", "severities": [2] } ],
  "inference": { "imgsz": 640, "conf_floor": 0.001, "max_det": 100, "device": "auto" },
  "evaluation": { "confidence_threshold": 0.25, "iou_match_threshold": 0.5,
                  "metrics": ["retention","mean_confidence_delta","mean_matched_iou","precision","recall","f1","map50","map50_95"],
                  "bootstrap": { "enabled": true, "n_resamples": 1000, "seed": 1234 } },
  "seed": 1234, "persist_corrupted": "failures", "top_k_failures": 20, "gate": null }
```

Response `202`:

```json
{ "run_id": "run_01J8Z5Q2", "status": "QUEUED", "normalized_config_url": "/api/v1/runs/run_01J8Z5Q2" }
```
Validation notes: `preset` and `corruptions` are mutually exclusive; presets are expanded server-side; label metrics on unlabeled datasets fail **here** with `422 METRIC_UNAVAILABLE`; conditions ∈ [1, 24].

### GET `/runs`
Query: `limit` (default 25), `cursor`, `status`. Response:
```json
{ "runs": [ { "run_id": "run_01J8Z5Q2", "created_at": "2026-10-24T10:02:11Z", "status": "COMPLETED",
              "model_id": "yolo-nano-default", "dataset_id": "ds_01J8Z3K4", "gate_verdict": null,
              "mean_relative_retention": 0.78 } ], "next_cursor": null }
```
(values illustrative)

### GET `/runs/{id}`

```json
{ "run_id": "run_01J8Z5Q2", "status": "RUNNING", "stage": "CONDITIONS", "progress": { "done": 14, "total": 49 },
  "created_at": "2026-10-24T10:02:11Z", "started_at": "2026-10-24T10:02:12Z", "finished_at": null,
  "error": null, "conditions": [ { "condition_id": "gaussian_blur:2", "status": "DONE" } ] }
```
Terminal `FAILED`: `"error": { "code": "MODEL_UNAVAILABLE", "message": "Weights checksum mismatch." }`.

### POST `/runs/{id}/cancel`
`200 { "run_id": "...", "status": "RUNNING", "cancel_requested": true }`; `409 RUN_NOT_CANCELLABLE` if terminal.

### GET `/runs/{id}/report`
`?format=json` (default) returns `report.json` (06 §10). `?format=html` returns `text/html` attachment. `409 RUN_NOT_COMPLETE` if still running; `404` if HTML not generated.

### GET `/runs/{id}/failures`
Query: `condition_id`, `corruption`, `severity`, `type`, `image_id`, `limit`, `cursor`, `sort=score_desc`.
```json
{ "failures": [ { "failure_id": "fail_0007", "image_id": "img_000003", "condition_id": "low_light:3",
                  "type": "LOST_DETECTION", "score": 0.91,
                  "baseline_detection": { "class_id": 0, "class_name": "person", "confidence": 0.95, "bbox_xyxy": [100.0, 80.0, 250.0, 350.0] },
                  "corrupted_detection": null, "matched_gt": null, "match": { "iou": null, "theta": 0.5 },
                  "artifacts": { "original": "art_a1", "corrupted": "art_a2" } } ], "next_cursor": null }
```

### GET `/runs/{id}/artifacts/{artifact_id}`
Returns image bytes (`image/png`) or report file. `404 ARTIFACT_NOT_FOUND` if not persisted (run metadata kept). Artifact IDs are opaque; clients never send paths.

### POST `/runs/{id}/replay` (P2)
`202 { "run_id": "run_new", "replay_of": "run_01J8Z5Q2" }`; report includes a `replay.match: true|false` diff.

## 6. Validation rules (summary)

| Field | Rule |
| --- | --- |
| `file` | Magic-byte check; ≤ `MAX_UPLOAD_MB`; ≤ `MAX_IMAGE_PIXELS` per image |
| zip | No traversal/symlinks; size and entry caps |
| `dataset_id`, `model_id` | Must exist |
| `corruptions[].severities` | Within catalog range |
| `confidence_threshold`, `iou_match_threshold` | (0, 1) |
| `seed` | Integer; always recorded |
| `persist_corrupted` | `failures` \| `all` \| `none` |
| `gate` | See 06 §8.2 |

## 7. File upload behaviour

Streamed to disk with a running size cap; rejected atomically (no partial dataset). Original filenames are metadata only; storage names are server-generated. Zip contents are validated before extraction into `storage/datasets/<id>/`.

## 8. Contract change process

Any change to this file or `schemas/` is a **contract change**: PR labelled `contract-change`, fixtures updated, OpenAPI diff reviewed, approved per 09 §9, TS types regenerated (`npm run gen:api`).
