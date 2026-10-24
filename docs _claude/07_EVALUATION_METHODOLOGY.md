# 07 — Evaluation and Algorithm Specification

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owners | Aditya (matching, metrics, failures, gate) · Chinmay (corruptions, adapter) |
| Stage | 1 — frozen before parallel coding |
| Sources | Architecture §5.5–§5.8; Master Plan §E, §F |

> This document must be technically precise. **No team member decides independently how a metric is calculated.** Numeric parameters marked *initial* are defaults to be calibrated (task M-2) — they are not validated values. VisionGuard severities are its own 1–3 scale and are **not comparable** to ImageNet-C / `imagecorruptions` severities or their published numbers.

---

## 1. Experimental protocol

1. Fix the image set; record SHA-256 per image.
2. Run baseline inference once per image (cached by content hash).
3. Apply **one corruption type at a time** at a documented severity (a *condition* = corruption × severity).
4. Keep weights, `imgsz`, confidence floor, NMS settings and preprocessing identical for clean and corrupted inference.
5. Match baseline ↔ corrupted predictions with the rule in §3.
6. Aggregate per condition (micro-average), then per corruption and overall.
7. Inspect individual failures (§6).
8. Seeds: stochastic corruptions use the derived seed in §2.1; every seed and scaled parameter is stored.

## 2. Image corruption algorithms

### 2.1 Common rules

| Rule | Detail |
| --- | --- |
| Input/Output | RGB `uint8` HWC; shape preserved for geometry-preserving corruptions |
| Purity | Operate on a copy; never mutate input |
| Determinism | Output is a pure function of `(image bytes, corruption id, severity, seed, library versions)` |
| Seed derivation | `seed = int.from_bytes(sha256(f"{run_seed}\|{image_sha256}\|{corruption_id}\|{severity}")[:8], "big")` — independent of iteration order and of which other conditions are selected |
| Resolution independence | Spatial parameters are defined at a **640-px reference short side** and scaled linearly: `p_actual = p_ref × (short_side / 640)`; the scaled value is recorded |
| Clipping | Float work; clip to [0, 255]; cast to `uint8` **once**, at the end |
| Severity | Integers 1–3 (Mild / Moderate / Severe) |
| Notation | `I` input (0–255), `O` output, `s` = short_side/640 |

### 2.2 Catalog

| `id` | Models | Math / implementation | Severity 1 / 2 / 3 (reference) | Randomness | Pri |
| --- | --- | --- | --- | --- | --- |
| `gaussian_blur` | Defocus | `O = I ∗ G_σ`, `σ = σ_ref·s`; `cv2.GaussianBlur`, kernel `k = 2·⌈3σ⌉+1` (odd) | σ = 1.0 / 2.5 / 5.0 px | none | P0 |
| `motion_blur` | Camera/subject motion | `O = I ∗ K`, `K` = normalized 1-px line of length `L = L_ref·s` (min 3, made odd) at angle `θ`; `cv2.filter2D` | L = 7 / 15 / 27 px | θ ~ U[0°,180°) from seed; recorded | P1 |
| `low_light` | Underexposure | sRGB→linear: `c_lin = ((c/255+0.055)/1.055)^2.4` (c>0.04045 else c/12.92); `c_lin' = g·c_lin`; re-encode to sRGB. **Not** a naive multiply of gamma-encoded values | g = 0.55 / 0.30 / 0.12 | none | P0 |
| `gaussian_noise` | Sensor noise | `O = clip(I + N(0, σ²))`, independent per pixel and channel, on 0–255 scale | σ = 5 / 15 / 30 | `numpy.random.Generator(seed)` | P0 |
| `jpeg_compression` | Compression artifacts | `cv2.imencode(".jpg", I_bgr, [IMWRITE_JPEG_QUALITY, q])` then decode (BGR↔RGB handled explicitly) | q = 70 / 40 / 15 | none | P0 |
| `haze` | Reduced visibility | `O = I·t + A·(1−t)`, uniform `t`, airlight `A = 0.9·255` | t = 0.75 / 0.50 / 0.30 | none | P1 |
| `occlusion` | Partial obstruction | Fill an axis-aligned rectangle (aspect from seed within [0.5, 2.0] `[PROPOSED]`) covering `a` of image area with a constant gray (value 127) `[PROPOSED]` | a = 5 % / 15 % / 30 % | position and aspect from seed; recorded | P1 |
| `rotation` | Camera tilt | Affine rotation about center, documented padding | 5° / 15° / 30° | none | **P2** (`geometry_preserving=false`) |

**Per-corruption I/O behaviour.** All P0/P1 corruptions return an image of identical shape and dtype; `params` records the scaled values actually used (e.g. `{"sigma": 2.5, "scale": 1.25, "sigma_applied": 3.125}`).

**Known limitations (written into every report that uses them).** Haze uses uniform transmission (no depth map), so it does not reproduce real fog; synthetic noise/blur approximate real sensors; low-light omits shot-noise amplification and tone-mapping. Real camera, weather and lighting variation is not fully reproduced.

**Geometry-changing corruptions** (`rotation`, crop, perspective) change the coordinate frame: baseline detections and GT boxes would need the same transform, and rotated boxes re-fit to axis-aligned boxes inflate. They are excluded from labeled-mode gating until a tested box-mapping exists.

**Calibration task M-2.** On the sample set, confirm severity 1 yields a small effect and severity 3 a clearly measurable one for the chosen detector; update defaults and record the calibration date in the catalog.

## 3. Prediction comparison (label-free)

### 3.1 Preprocessing

All consistency metrics use detections with `confidence ≥ τ` (default **0.25**, same τ for baseline and corrupted). mAP is the exception (all detections ≥ `conf_floor`).

### 3.2 IoU

For boxes `a = [ax1, ay1, ax2, ay2]`, `b` likewise:

```
inter_w = max(0, min(ax2,bx2) − max(ax1,bx1))
inter_h = max(0, min(ay2,by2) − max(ay1,by1))
inter   = inter_w · inter_h
union   = area(a) + area(b) − inter
IoU     = inter / union          (0 if union == 0)
```

### 3.3 Matching strategy (per image)

1. `B` = baseline detections (≥ τ), `C` = corrupted detections (≥ τ).
2. For each class separately, build `IoU[b, c]`.
3. Solve a one-to-one assignment maximizing total IoU (Hungarian — `scipy.optimize.linear_sum_assignment`).
4. Discard assigned pairs with `IoU < θ` (default **θ = 0.5**). Result: matched `M`, lost `B∖M`, unmatched corrupted `C∖M`.
5. **Class flips:** among `B∖M × C∖M`, pairs with class-agnostic `IoU ≥ θ` and *different* classes are recorded as flips and removed from lost / unmatched corrupted (no double counting). Resolve flip conflicts with the same one-to-one rule.
6. A corrupted box never matches two baseline boxes, and vice versa.

### 3.4 Definitions

| Term | Definition |
| --- | --- |
| Detection retention | Matched baseline detections ÷ baseline detections |
| Detection loss | Baseline detections with no match and no flip |
| Class change (flip) | Spatially matched (class-agnostic) to a corrupted detection of a different class |
| Confidence change | `conf_corrupted − conf_baseline` for matched pairs |
| Unmatched detection | Corrupted detection with no baseline counterpart (named `unmatched_corrupted`; "false positive" is reserved for labeled mode) |

### 3.5 Worked example (for TC-004/TC-005)

Baseline: `person@0.92 [100,80,250,350]`, `car@0.80 [300,200,500,320]`. Corrupted run A = identical → `|M|=2`, retention 1.0. Corrupted run B drops the car → `|M|=1`, retention 0.5, loss_rate 0.5.

## 4. Evaluation metrics

### 4.1 Two metric families — never mixed

| Family | Labels needed | Answers | Badge |
| --- | --- | --- | --- |
| Consistency | No | How much did output change vs the model's own clean output? | `CONSISTENCY` |
| Ground truth | Yes | How correct is output vs verified labels? | `GROUND TRUTH` |

A model that is consistently wrong scores perfectly on retention. A disappearing detection is a *change*; it is a false negative only if a label confirms the object exists.

### 4.2 Consistency metrics

| Metric | Formula | Inputs | Undefined when | Interpretation / limitation |
| --- | --- | --- | --- | --- |
| `retention` | `Σ\|M\| / Σ\|B\|` (micro-average; per-image stored) | `B`, `M` | `Σ\|B\|=0` → `null`, `NO_BASELINE_DETECTIONS` | Consistency, not accuracy; depends on τ, θ and matching rule |
| `loss_rate` | `1 − retention` | same | same | |
| `mean_confidence_delta` | mean over `M` of `conf_c − conf_b` | matched pairs | `\|M\|=0` | Confidence is not calibrated correctness |
| `mean_matched_iou` | mean over `M` of IoU | matched pairs | `\|M\|=0` | Localization drift; ≥ θ by construction |
| `class_flip_rate` | `flips / Σ\|B\|` | flips, `B` | `Σ\|B\|=0` | |
| `unmatched_corrupted_rate` | `\|C∖M\| / \|C\|` after removing flips | `C`, `M` | `\|C\|=0` | Not a false-positive rate |
| `latency_ms` | mean, p50, p95 of `predict` wall time | timings | — | Warm-up excluded; GPU timing synchronizes before stop; hardware dependent |
| `relative_retention` | `retention_condition / retention_clean_control` (P1) | control run | control retention 0/undefined | Removes runtime nondeterminism floor |

**Clean-vs-clean control (P1).** Re-infer the clean images and compute retention vs the baseline. If < 1.0, the floor is runtime nondeterminism and is reported so noise is not attributed to corruption.

### 4.3 Ground-truth metrics (P1)

| Metric | Method |
| --- | --- |
| Precision | `TP/(TP+FP)` at τ, θ; per image greedy matching in descending confidence (COCO-style), class-aware, each GT matched once; micro-average (macro per class also stored) |
| Recall | `TP/(TP+FN)` |
| F1 | `2PR/(P+R)` |
| mAP@0.5 | `pycocotools` (directly or via `torchmetrics.detection.MeanAveragePrecision`), IoU 0.5 |
| mAP@0.5:0.95 | Same evaluator, thresholds 0.50:0.05:0.95 (standard COCO; custom threshold lists are restricted with the `pycocotools` backend) |
| `relative_map50` | `map50_corrupted / map50_clean`; undefined if clean mAP = 0. Verify the exact definition against Michaelis et al. before using that name in the UI |

Zero denominators → `null` + reason. **Do not implement a custom metric and call it mAP.** Pin the evaluator version in the manifest. `crowd` GT handled per COCO convention. Classes outside the model's label space are excluded and reported.

### 4.4 Aggregation and uncertainty

- Per condition: micro-averaged dataset metrics plus per-image arrays.
- Per corruption: mean over severities. Overall: mean over conditions, named `mean_relative_retention` (**not** a certification score).
- **Bootstrap CIs (P1):** resample images with replacement (1000 resamples, fixed seed), 95 % percentile interval for `retention` and `map50` deltas. N < 30: "small sample" banner; N = 1: no interval, single-image caveat.
- No significance claim unless a documented test is run.

## 5. Regression gate semantics

`evaluate_gate(rules, results) → {verdict, rules[]}`: `PASS` all rules satisfied; `FAIL` any rule violated; `ERROR` any rule unevaluable (undefined metric, errored condition, partial run). Never a silent pass. Thresholds are user-defined.

## 6. Failure taxonomy and ranking

| Type | Mode | Definition |
| --- | --- | --- |
| `LOST_DETECTION` | consistency | Baseline detection with no match in corrupted output |
| `CLASS_FLIP` | consistency | Matched spatially to a different-class corrupted detection |
| `LOCALIZATION_SHIFT` | consistency | Matched pair with `IoU < θ_loc` (default 0.75) |
| `CONFIDENCE_DROP` | consistency | Matched pair with `Δconf ≤ −δ` (default 0.20) |
| `NEW_DETECTION` | consistency | Corrupted detection with no baseline counterpart |
| `GT_REGRESSION_FN` | ground truth | GT matched (TP) in clean, missed (FN) in corrupted |
| `GT_NEW_FP` | ground truth | Corrupted detection with no GT match and no clean FP counterpart |

**Ranking score (ordering only):** `score = w₁·type_weight + w₂·|Δconf| + w₃·(1 − IoU)`, with confidence-weighted loss for `LOST_DETECTION` (a lost 0.95 ranks above a lost 0.30). Weights are constants in one file; the score is never shown as a metric. Only top-K per condition (default 20) keep images.

## 7. Required honesty statements

- Retention and confidence deltas are consistency measures, not accuracy.
- A robustness score from a small set is not a universal model property.
- Transformations approximate real conditions.
- Report whether ground-truth labels were used, and N.
- Example wording (Master Plan §F2; A, B, N are placeholders filled from measurements only): *"On this test set of N images, detection retention was B% under the selected condition. This is a consistency comparison against the baseline. Ground-truth labels were/weren't available, so this result should/should not be interpreted as an accuracy measurement."*

## 8. Open methodology tasks

| ID | Task | Owner |
| --- | --- | --- |
| M-1 | Measure latency/memory on the demo machine; set `MAX_IMAGES` and condition cap | Chinmay |
| M-2 | Calibrate severities per corruption on the sample set | Chinmay |
| M-3 | Verify `relative_map50` definition against the paper | Aditya |
| M-4 | Verify chosen detector's NMS behaviour (NMS-free models) and `conf_floor` | Chinmay |
| M-5 | Hand-check matching/metric examples before implementing tests | Aditya |
