# 01 — Product Requirements Document (PRD)

| Field | Value |
| --- | --- |
| Product | VisionGuard |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Tanish |
| Approval stage | 1 — Product and technical agreement |
| Sources | Master Plan §A, §B, §K, §O; Architecture §2 |

> This document describes what the user experiences and why — not the internal Python implementation (see 03).

---

## 1. Product overview

VisionGuard is a web platform that stress-tests computer-vision object detectors. A user supplies an image or a small dataset, chooses a detector and a set of controlled image corruptions (blur, low light, noise, compression, haze…), and VisionGuard runs the **same detector on the clean images and on seeded, degraded versions of them**. It compares outputs under a fixed protocol, surfaces concrete failure cases, and produces a reproducible report with an optional pass/fail regression gate.

## 2. Problem statement

Models are usually evaluated on clean, curated images. Deployment images contain motion blur, low light, sensor noise, compression artifacts and haze. A detector that scores well on clean data can lose objects, change classes or shift boxes when conditions change.

## 3. Existing problem and its impact

- Developers check robustness with one-off scripts that are rarely reproducible, rarely visual, and rarely wired into a pass/fail check.
- Published evidence (Michaelis et al., 2019) shows that standard detectors can fall to 30–60 % of their original performance on corrupted images. This is motivation only — **not a VisionGuard result**.
- Impact: unreliable behaviour is discovered late, failures are hard to reproduce, and reliability regressions slip into releases unnoticed.

## 4. Proposed solution

An integrated workflow: *upload → stress test → visual failure explorer → shareable report*, in one app, with two guiding rules:

1. **Honest metrics.** Label-free *consistency* metrics are never presented as *accuracy*. Ground-truth metrics appear only when labels exist.
2. **Reproducibility by construction.** Every run stores a manifest (input hashes, model identity, library versions, corruption parameters, seeds) sufficient to re-execute it.

## 5. Target users

| User | Description | Primary need |
| --- | --- | --- |
| ML developer (primary) | Builds/fine-tunes detectors | See which conditions break the model and inspect examples |
| QA / reliability engineer | Guards releases | Repeatable pass/fail regression check, exit codes for CI |
| Hackathon judge / reviewer | Sees a demo for minutes | Understand value in under three minutes, with real numbers |
| Domain engineer (future) | PCB, road damage, agriculture | Reuse the engine with a domain model |

## 6. User needs and use cases

| ID | Use case | Outcome |
| --- | --- | --- |
| UC-1 | Test a detector on one image under blur, low light and noise | See lost/changed detections side by side |
| UC-2 | Test on a labeled COCO-format set | Precision/recall/F1/mAP clean vs degraded |
| UC-3 | Sweep severity of one corruption | Reliability heatmap and curves |
| UC-4 | Inspect worst failures | Ranked gallery with before/after overlays |
| UC-5 | Re-open a past run | Persisted run with config and manifest |
| UC-6 | Export evidence | JSON (and HTML) report with limitations text |
| UC-7 | Gate a release | PASS / FAIL / ERROR verdict from declared rules |

## 7. Product objectives

| # | Objective | Priority |
| --- | --- | --- |
| 1 | Establish a clean-image baseline | P0 |
| 2 | Evaluate under controlled, seeded degradation | P0 |
| 3 | Measure change with correctly defined metrics (two separate families) | P0 |
| 4 | Identify, rank and visually inspect failure cases | P0 |
| 5 | Generate reproducible JSON/HTML reports with a manifest | P0 JSON / P1 HTML |
| 6 | Configurable regression gate (PASS / FAIL / ERROR) | P1 |
| 7 | Compare mitigations or two models on identical conditions | P2 |

## 8. Core features

| Feature | Behaviour | Priority |
| --- | --- | --- |
| Dataset input & validation | Single image (P0) or COCO zip (P1); field-level errors | P0/P1 |
| Model selection | Pretrained detector via adapter | P0 |
| Corruption configuration | ≥ 3 seeded corruptions, 3 severities, or a scenario preset | P0 |
| Clean vs degraded results | Metric cards, heatmap, severity sweep, condition table | P0 |
| Failure explorer | Filter, rank, before/after swipe with overlays | P0 |
| Run history | Persisted runs reopenable after restart | P0 |
| Report export | JSON authoritative; HTML self-contained | P0/P1 |
| Regression gate | Declarative rules, tri-state verdict, CLI exit codes | P1 |
| Scenario presets | `night_driving`, `drone_haze`, `cheap_camera`, `full_sweep` | P1 |

### Main user journey

```
User selects dataset
       ↓
Selects computer vision model
       ↓
Configures image corruptions
       ↓
Starts evaluation
       ↓
Views clean vs. degraded results
       ↓
Inspects failure cases
       ↓
Downloads evaluation report
```

## 9. MVP scope

**In:** single-image and (P1) COCO dataset runs; one pretrained detector; 3–5 corruptions (target 6–8 at P1); detection comparison; failure explorer; saved runs; JSON report; sample-image quick start; honest limitations text.

**Excluded from MVP:**

- Training or fine-tuning models; automatic model repair
- Safety/fairness/production-readiness certification
- Authentication, multi-tenant SaaS, cloud GPU orchestration
- Real-time multi-camera or video analysis
- Geometry-changing corruptions in labeled mode (rotation — P2)
- Any accuracy claim without ground-truth labels

## 10. Expected outcomes

- A judge can upload an image and complete a robustness run without editing code.
- Run settings and model version are visible in the UI and stored with the run.
- At least three corruptions and a baseline comparison work end to end.
- Errors are visible; the UI never fakes successful inference.
- Every demo claim is backed by a measurement produced in that run.

## 11. Success criteria

| Criterion | Measure |
| --- | --- |
| Works from a clean start | New member runs the app from README commands |
| Core flow complete | Upload → inference → ≥ 3 corruptions → comparison → failure view → saved run |
| Metrics defined & tested | Each metric has a formula, undefined-case handling and unit tests (see 07, 08) |
| Reproducible | Same config + seed ⇒ identical corrupted pixels |
| Honest | Report states whether labels were used; consistency never labelled accuracy |
| Team understanding | All five members can explain the image-to-report pipeline |

> No speed, accuracy or scalability targets are promised until measured (Architecture §3.2; tasks M-1, M-2).

## 12. Product limitations

- Tests a selected detector, not every architecture.
- Synthetic corruptions approximate, and do not reproduce, real cameras, weather or lighting.
- Consistency metrics do not replace ground-truth evaluation; a consistently wrong model scores perfectly on retention.
- Small samples give uncertain results; the number of images is always shown.
- Inference speed depends on hardware, warm-up, image size and batch settings.
- A report documents observed behaviour; it does not certify safety or fairness.
- Prior art exists (Hendrycks & Dietterich, Michaelis et al., Deepchecks, FiftyOne plugin): **VisionGuard does not claim the idea is novel**; its differentiation is the integrated workflow, strict metric taxonomy, gate semantics, manifest replay, presets and adapter.

## 13. Future enhancements

| Stage | Extension |
| --- | --- |
| V2 | Batch/labeled benchmarks, CSV reports, model version comparison, bootstrap CIs |
| V3 | Video: frame sampling, temporal consistency |
| V4 | Domain adapters (PCB, road damage, industrial safety, agriculture) |
| V5 | Calibration evaluation, distribution shift, explainability, custom suites |
| Other | CI GitHub Action, PDF export, segmentation/classification tasks, second detector A/B |

## 14. Assumptions and dependencies

- The official HackFusion 2.0 problem statement and rubric are **not yet confirmed**; if a specific problem is assigned, VisionGuard serves as the reliability layer for it.
- A small, legally usable demo dataset is available offline.
- Windows is likely among development platforms.
