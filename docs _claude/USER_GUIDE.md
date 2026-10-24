# VisionGuard User Guide

Version 0.1 (draft, written ahead of implementation — screens and labels may change) · Owner: Member 5 (TBC)

## 1. What VisionGuard does

It runs your object detector on clean images and on controlled, degraded copies (blur, low light, noise…), then shows what changed: lost detections, class changes, shifted boxes — with a report you can keep.

## 2. Before you start

- Backend and frontend are running (see `10_SETUP_AND_ENVIRONMENT.md`).
- The header shows **Model: ready**. If it shows a mock-model warning, results are fake — do not use them for conclusions.

## 3. Quick start

1. Open the **Dashboard**, click **Run sample evaluation**.
2. Wait for progress to finish (stage and `done/total` are shown).
3. Review the results page.

## 4. Running your own evaluation

1. **New Evaluation** → upload an image or a COCO `.zip` (`images/` + `annotations.json`).
2. Choose the model.
3. Pick corruptions and severities (1 Mild, 2 Moderate, 3 Severe) or a scenario preset.
4. Optionally adjust thresholds (confidence τ, IoU match θ), seed, and gate rules.
5. Click **Run evaluation**.

## 5. Reading the results

| Item | Meaning |
| --- | --- |
| `CONSISTENCY` badge | How much output changed vs the model's own clean output. **Not accuracy** |
| `GROUND TRUTH` badge | Correctness vs your labels — shown only if labels exist |
| Retention | Share of clean detections still found (matched) after corruption |
| Confidence Δ | Average change in confidence of matched detections |
| Mean IoU | How far boxes moved (1.0 = identical) |
| Class flips | Detections that kept their place but changed class |
| Heatmap | Corruption × severity, colored by relative retention |
| Gate | PASS / FAIL / ERROR from your rules; ERROR means it could not be evaluated, never a pass |

Small samples (N < 30) carry a warning; a single image gives an illustration, not a measurement.

## 6. Inspecting failures

Open **Failure Analysis**, filter by corruption, severity or type, and use the swipe to compare clean vs degraded with overlays. Only the top failures per condition keep images. The ranking score only orders the gallery.

## 7. Exporting

Use **Export JSON** (authoritative) or **Export HTML** (self-contained, opens offline). Reports include model, settings, seed, N, results, manifest and limitations.

## 8. Reproducing a run

Same dataset, model, configuration and seed produce the same corrupted pixels. The manifest in each report lists everything needed to re-run it.

## 9. Command line

```
visionguard run --dataset <path> --model default --preset night_driving --gate gate.yaml --out ./storage
```
Exit codes: 0 PASS, 1 FAIL, 2 ERROR/FAILED/PARTIAL, 64 bad arguments.

## 10. Common messages

| Message / code | What to do |
| --- | --- |
| `UNSUPPORTED_FORMAT` / `INVALID_IMAGE` | Use JPG, PNG, WEBP or BMP that opens normally |
| `IMAGE_TOO_LARGE` / `DATASET_TOO_LARGE` | Reduce size/count |
| `METRIC_UNAVAILABLE` | You asked for precision/recall/mAP without labels — remove or upload labels |
| `MODEL_UNAVAILABLE` | Model weights missing — ask the maintainer |
| Run `PARTIAL` | Some conditions failed; others are valid; gate shows ERROR |

## 11. Limitations

Synthetic corruptions approximate real conditions; consistency is not accuracy; results depend on your images and hardware; a report does not certify safety or fairness.
