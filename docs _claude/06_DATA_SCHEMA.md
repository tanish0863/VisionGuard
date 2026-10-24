# 06 — Data Dictionary and Schema Specification

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Tanish + all module owners |
| Stage | 1 — freeze before parallel coding |
| Basis | Architecture §7.1–§7.4, §5.4–§5.8; items marked `[PROPOSED]` extend the truncated source |

> **Source of truth:** Pydantic models in `backend/visionguard/schemas/`. These tables document them. Any change is a contract change (see 09 §9). All examples are illustrative values, not results.

## 1. Global conventions

| Convention | Rule |
| --- | --- |
| Box format | `bbox_xyxy = [x_min, y_min, x_max, y_max]` — **never** `xywh` outside the dataset loader |
| Coordinate system | Absolute pixels in the **original, EXIF-normalized, pre-resize** image; origin top-left; x → right, y → down |
| Box validity | Floats; `x_min < x_max`, `y_min < y_max`; clipped to `[0, W] × [0, H]` |
| Image format | RGB, `uint8`, HWC (NumPy); EXIF orientation applied at ingestion |
| Confidence | Decimal in `[0.0, 1.0]` everywhere (API and files); percent formatting is UI-only |
| Class mapping | `class_id` indexes `ModelInfo.classes`; `class_name` always derived from it |
| Empty predictions | `"predictions": []` — never `null` |
| Unlabeled GT | `"ground_truth": null` — not `[]` (no labels ≠ labeled with zero objects) |
| Ordering | Predictions sorted by confidence descending |
| Timestamps | ISO-8601 UTC |
| IDs | Opaque, server-generated strings |
| Hashes | SHA-256, lowercase hex |
| Severity | Integer 1–3 (declared per corruption in the catalog) |
| Undefined metric | `null` plus a sibling `undefined_reason` string; never 0 / NaN |
| Schema version | Every top-level object has `schema_version: "1.0"` |

## 2. Dataset schema

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| schema_version | String | `"1.0"` | Yes |
| dataset_id | String | e.g. `ds_01J8Z3K4` | Yes |
| name | String | Display name | Yes |
| created_at | String (ISO) | Creation time | Yes |
| has_labels | Boolean | Annotations present | Yes |
| dataset_sha256 | String | Hash over sorted image hashes + annotations | Yes |
| classes | Array[{class_id:int, class_name:string}] | Model class space used | Yes |
| class_map | Array[ClassMapEntry] | Dataset→model mapping | If labeled |
| excluded_classes | Array[string] | Dataset classes with no model counterpart | Yes |
| warnings | Array[Warning] | Non-fatal issues | Yes |
| items | Array[DatasetItem] | Images | Yes |

**ClassMapEntry:** `dataset_category_id` (int), `dataset_name` (string), `model_class_id` (int | null), `included` (bool).
**Warning:** `code` (string), `detail` (string).

```json
{ "schema_version": "1.0", "dataset_id": "ds_01J8Z3K4", "name": "street_sample",
  "created_at": "2026-10-24T09:30:00Z", "has_labels": true, "dataset_sha256": "<hex>",
  "classes": [ { "class_id": 0, "class_name": "person" } ],
  "class_map": [ { "dataset_category_id": 1, "dataset_name": "person", "model_class_id": 0, "included": true } ],
  "excluded_classes": [], "warnings": [],
  "items": [ { "image_id": "img_000001", "file_name": "000001.jpg", "sha256": "<hex>", "width": 640, "height": 480,
               "ground_truth": [ { "gt_id": "gt_1", "class_id": 0, "class_name": "person",
                                   "bbox_xyxy": [100.0, 80.0, 250.0, 350.0], "iscrowd": false } ] } ] }
```

### 2.1 Input file format (decision of record)

```
dataset.zip
├── images/000001.jpg …
└── annotations.json     # COCO detection: images, annotations, categories; bbox = [x, y, w, h] absolute px
```
Single image: `.jpg .jpeg .png .webp .bmp`, no labels. Class names are matched to the model's label space by case-folded, trimmed name; unmatched classes are excluded and reported.

## 3. Annotation schema (internal)

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| gt_id | String | Unique within dataset | Yes |
| class_id | Integer | Model class ID after mapping | Yes |
| class_name | String | Class label | Yes |
| bbox_xyxy | Array[4] float | Converted once from COCO `xywh` at load time | Yes |
| iscrowd | Boolean | COCO crowd flag (handled per COCO convention) | Yes |

Validation: `x≥0, y≥0, w>0, h>0`; marginal out-of-bounds boxes clipped with a warning, grossly outside rejected; `category_id` must exist; every `image_id` references a file.

## 4. Image metadata and prediction schemas

### 4.1 Image metadata (`DatasetItem` minus ground truth)

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| image_id | String | Unique identifier (`img_000001`) | Yes |
| file_name | String | Original name (metadata only) | Yes |
| sha256 | String | Hash of file bytes | Yes |
| width | Integer | Pixels after EXIF normalization | Yes |
| height | Integer | Pixels after EXIF normalization | Yes |
| ground_truth | Array[Annotation] \| null | Labels | Yes |

### 4.2 Detection

| Field | Data type | Description | Required |
| --- | --- | --- | --- |
| class_id | Integer | Predicted class ID | Yes |
| class_name | String | Class label | Yes |
| confidence | Float | Prediction confidence 0–1 | Yes |
| bbox_xyxy | Array[4] | Bounding box coordinates | Yes |

### 4.3 PredictionResult (model-adapter output contract)

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| image_id | String | Image identifier | Yes |
| image_width | Integer | Original width | Yes |
| image_height | Integer | Original height | Yes |
| latency_ms | Float | `predict` wall time, warm-up excluded | Yes |
| predictions | Array[Detection] | All detections above `conf_floor`, sorted desc | Yes |

```json
{ "image_id": "img_000001", "image_width": 640, "image_height": 480, "latency_ms": 18.4,
  "predictions": [ { "class_id": 0, "class_name": "person", "confidence": 0.92, "bbox_xyxy": [100.0, 80.0, 250.0, 350.0] } ] }
```

## 5. Model configuration schema

### 5.1 ModelInfo (adapter `metadata()`)

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| model_id | String | e.g. `yolo-nano-default` | Yes |
| name | String | Library/model name | Yes |
| version | String | Pinned version | Yes |
| weights_sha256 | String | Checksum of weights | Yes |
| device | String | `cpu`, `cuda:0`… | Yes |
| is_mock | Boolean | True only for `MockAdapter` | Yes |
| classes | Array[{class_id,class_name}] | Authoritative label list | Yes |
| postprocessing | Object | Post-processing in effect (e.g. `nms`, or `none/NMS-free`) | Yes |
| cpu_fallback_used | Boolean | True if CUDA OOM fell back to CPU | Yes |

### 5.2 InferenceParams

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| imgsz | Integer | 640 | Identical for clean and corrupted |
| conf_floor | Float | 0.001 | Placeholder; validate per model |
| iou_nms | Float \| null | model default | Only if NMS applies |
| max_det | Integer | 100 | |
| device | String | `auto` | |

## 6. Corruption configuration schema

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| type | Enum | `gaussian_blur`, `motion_blur`, `low_light`, `gaussian_noise`, `jpeg_compression`, `haze`, `occlusion` (P2: `rotation`) | Yes |
| severities | Array[int] | Each within catalog range | Yes |

**CorruptionResult** (internal): `image` (ndarray), `params` (object, scaled values), `seed` (int). **Condition ID:** `"<type>:<severity>"`.

Catalog entry (`GET /corruptions`): `id`, `family`, `geometry_preserving`, `severities`, `labels`, `priority`, `params_at_reference`.

## 7. Scenario preset schema

`id` (string), `description` (string), `corruptions` (Array[Corruption config]), `disclaimer` (string). Presets: `night_driving`, `drone_haze`, `cheap_camera`, `full_sweep`.

## 8. Evaluation configuration schema (`RunConfig`)

| Field | Type | Required | Valid values / notes |
| --- | --- | --- | --- |
| schema_version | String | Yes | `"1.0"` |
| dataset_id | String | Yes | Must exist |
| model_id | String | Yes | Must exist |
| preset | String \| null | No | Mutually exclusive with `corruptions` |
| corruptions | Array | Yes if no preset | Catalog-valid; 1–24 conditions |
| inference | InferenceParams | No | Defaults from server |
| evaluation.confidence_threshold | Float | No | (0,1), default 0.25 |
| evaluation.iou_match_threshold | Float | No | (0,1), default 0.5 |
| evaluation.metrics | Array[string] | No | GT metrics on unlabeled → 422 |
| evaluation.bootstrap | {enabled, n_resamples, seed} | No | default 1000 resamples |
| seed | Integer | No | Random if omitted, **always recorded** |
| persist_corrupted | Enum | No | `failures` (default) \| `all` \| `none` |
| top_k_failures | Integer | No | Default 20 |
| gate | GateConfig \| null | No | See 8.2 |

### 8.1 Allowed metric names

Consistency: `retention`, `loss_rate`, `mean_confidence_delta`, `mean_matched_iou`, `class_flip_rate`, `unmatched_corrupted_rate`, `latency_ms`.
Ground truth: `precision`, `recall`, `f1`, `map50`, `map50_95`, `relative_map50`.

### 8.2 GateConfig `[PROPOSED]`

| Field | Type | Description |
| --- | --- | --- |
| rules[].id | String | Unique rule name |
| rules[].metric | String | Any metric in 8.1 or `relative_retention` |
| rules[].scope | `"all"` \| `"any"` \| {corruption, severity?} | Which conditions it applies to |
| rules[].op | Enum | `>=`, `>`, `<=`, `<` |
| rules[].threshold | Float | User-supplied; no shipped "safe" defaults |

## 9. Evaluation result schema

### 9.1 MetricValue

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| value | Float \| null | Metric value | Yes |
| undefined_reason | String \| null | e.g. `NO_BASELINE_DETECTIONS` | Yes |
| family | Enum | `CONSISTENCY` \| `GROUND_TRUTH` | Yes |
| n_images | Integer | Images contributing | Yes |
| ci95 | [Float, Float] \| null | Bootstrap interval if enabled and N ≥ 2 | No |

### 9.2 ConditionResult `[PROPOSED]` (shape)

```json
{ "condition_id": "gaussian_blur:2", "corruption": "gaussian_blur", "severity": 2, "status": "DONE",
  "params_at_reference": { "sigma": 2.5 },
  "consistency": { "retention": {"value": 0.71, "undefined_reason": null, "family": "CONSISTENCY", "n_images": 24, "ci95": [0.62, 0.79]},
                   "loss_rate": {"value": 0.29, "...": "..."}, "mean_confidence_delta": {"...": "..."},
                   "mean_matched_iou": {"...": "..."}, "class_flip_rate": {"...": "..."},
                   "unmatched_corrupted_rate": {"...": "..."} },
  "ground_truth": null,
  "delta_vs_clean": { "retention_abs": -0.29 },
  "latency_ms": { "mean": 19.1, "p50": 18.7, "p95": 25.0 },
  "per_image": [ { "image_id": "img_000001", "baseline_count": 4, "corrupted_count": 3, "matched": 3, "flips": 0, "lost": 1, "new": 0 } ],
  "error": null }
```
(values illustrative). `ground_truth` is `null` for unlabeled datasets.

## 10. Failure-case schema

| Field | Type | Description | Required |
| --- | --- | --- | --- |
| failure_id | String | `fail_…` | Yes |
| image_id | String | Image | Yes |
| condition_id | String | e.g. `low_light:3` | Yes |
| type | Enum | `LOST_DETECTION`, `CLASS_FLIP`, `LOCALIZATION_SHIFT`, `CONFIDENCE_DROP`, `NEW_DETECTION`, `GT_REGRESSION_FN`, `GT_NEW_FP` | Yes |
| score | Float | Ranking heuristic — ordering only, never a metric | Yes |
| baseline_detection | Detection \| null | | Yes |
| corrupted_detection | Detection \| null | | Yes |
| matched_gt | Annotation \| null | Labeled mode only | Yes |
| match | {iou: float\|null, theta: float} | | Yes |
| artifacts | {original: id\|null, corrupted: id\|null} | Only top-K have images | Yes |

## 11. Report schema (`report.json`)

| Section | Contents |
| --- | --- |
| `schema_version`, `run_id`, `status`, `created_at`, `finished_at` | Identity and timing |
| `app` | `version`, `git_commit` |
| `environment` | OS, Python, device, `libraries` map (numpy, opencv-python, detector package, pycocotools, evaluator version) |
| `model` | ModelInfo subset incl. `weights_sha256`, `is_mock`, `postprocessing` |
| `dataset` | `dataset_id`, `num_images`, `has_labels`, `dataset_sha256`, `class_map`, `excluded_classes` |
| `config` | Full normalized RunConfig |
| `manifest` | Reproducibility manifest (below) |
| `baseline` | Clean metrics (ground-truth family if labeled) and clean-vs-clean control (P1) |
| `conditions` | Array[ConditionResult] |
| `aggregates` | `per_corruption` (mean over severities), `overall.mean_relative_retention` — explicitly *not* a certification score |
| `failures` | Summary counts by type + top cases (FailureCase) |
| `gate` | `{verdict, rules:[{rule_id, observed, threshold, op, outcome, evidence}]}` or `null` |
| `warnings` | Array[Warning] |
| `limitations` | Auto-generated strings; wording switches on `has_labels` |

**Manifest:** input image/dataset hashes; model id, version, weights SHA-256, package versions, device, `cpu_fallback_used`; InferenceParams; per-condition corruption type, severity, scaled params, derived seeds; matching θ and τ; metric definitions version; evaluator versions; timestamp; app version / git commit; run status.

Required `limitations` strings (examples; wording from Master Plan §F2/§K1):
- *Unlabeled:* "Retention measures consistency against the clean baseline, not ground-truth accuracy."
- *Labeled:* "Ground-truth metrics are computed on N images; interpret with caution for small N."
- Always: "Synthetic corruptions approximate, and do not fully reproduce, real cameras, weather or lighting."

## 12. Valid value ranges (quick reference)

| Quantity | Range |
| --- | --- |
| confidence, τ, θ | (0, 1] for thresholds; detections 0–1 |
| severity | 1–3 |
| conditions per run | 1–24 (placeholder) |
| retention, loss_rate, rates | 0–1 or `null` |
| mean_confidence_delta | −1 … +1 or `null` |
| mean_matched_iou | θ … 1 or `null` |
| precision, recall, F1, mAP | 0–1 or `null` |
| latency_ms | ≥ 0 |
