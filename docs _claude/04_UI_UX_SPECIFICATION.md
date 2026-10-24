# 04 — UI/UX Design Specification

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Vanashree |
| Stage | 2 |
| Sources | Architecture §5.1; Master Plan §H |

Stack: React + TypeScript + Vite, React Router, Recharts, TanStack Query (recommended) or `fetch` + hooks. Types come from `frontend/src/types/api.gen.ts` (generated from OpenAPI). No global state library in MVP.

**Golden rules**

1. The UI never shows fabricated or placeholder results as if real.
2. Every metric carries a badge: `CONSISTENCY` or `GROUND TRUTH`, with a tooltip definition.
3. Overlays are rendered client-side from JSON, scaled by the image's natural size.
4. Every screen defines loading, empty and error states.
5. Confidence is shown as a percentage in the UI only; the API uses 0–1.

> Wireframes: ASCII layouts below. Replace with Figma frames and link them here once designed: `<Figma URL — add>`.

---

## 0. Global layout and navigation

```
┌──────────────────────────────────────────────────────────────────────┐
│ VisionGuard │ Dashboard │ New Evaluation │ Settings & Glossary │ ● Model: ready │
└──────────────────────────────────────────────────────────────────────┘
```

| Route | Screen |
| --- | --- |
| `/` | Dashboard |
| `/new` | New Evaluation |
| `/runs/:id` | Evaluation Details (results) |
| `/runs/:id/failures` | Failure Analysis |
| `/settings` | Settings & Glossary |

Header model badge calls `GET /health`; shows `ready`, `loading`, or `unavailable` (with `is_mock` warning banner if a mock model is active).

---

## 1. Dashboard (`/`)

**Purpose.** Overview of evaluation runs and results; fastest path to a first run.

**Layout.** Quick-start card (top), summary cards (total runs, last gate verdict, last mean relative retention), runs table.

```
┌ Quick start ─────────────────────────────┐
│ [ Run sample evaluation ]  [ New evaluation ] │
└──────────────────────────────────────────┘
┌ Recent runs ─────────────────────────────────────────────────┐
│ Run ID │ Created │ Dataset │ Model │ Status │ Gate │ Mean retention │
└──────────────────────────────────────────────────────────────┘
```

| Aspect | Spec |
| --- | --- |
| Components | `RunTable`, `StatusBadge`, `GateBadge`, `MetricCard` |
| Actions | Open run; start sample run; delete (P2) |
| Data | `GET /runs` (id, created_at, status, model, dataset, gate verdict, mean_relative_retention) |
| Navigation | Row → `/runs/:id`; buttons → `/new` |
| Loading | Skeleton rows |
| Empty | "No runs yet" + prominent quick-start button |
| Error | Inline banner with retry; table hidden |

---

## 2. New Evaluation (`/new`)

**Purpose.** Configure dataset, model, corruptions, thresholds, gate rules and start a run.

```
Left panel (form)                         Right panel (preview)
1 Dataset: (•) Upload  ( ) Sample         Image / dataset summary
   [ drop image or .zip ]                  N images · labeled? · warnings
2 Model:   [ detector v ]  (is_mock flag)
3 Corruptions: preset [ none v ]
   [x] gaussian_blur   sev [1][2][3]      Conditions: 6   (max 24)
   [x] low_light       sev [1][2][3]
   [ ] gaussian_noise ...
4 Thresholds: τ [0.25]  IoU θ [0.50]
5 Gate rules (optional) [+ add rule]
6 Seed [1234]   Persist corrupted: [failures v]
                      [ Run evaluation ]
```

| Aspect | Spec |
| --- | --- |
| Components | `ImageUploader`, `ModelSelect`, `CorruptionControls` (rendered from `GET /corruptions`), `PresetSelect` (`GET /presets`), `ThresholdInputs`, `GateRuleEditor` |
| Actions | Upload (`POST /datasets`), start (`POST /runs`) |
| Validation | Client: file type/size, ≥ 1 condition, 1–24 conditions. Server errors map to fields via `error.details[].field` |
| Display rules | Preset and manual corruptions are mutually exclusive; preset shows its disclaimer ("a convenience, not a validated scenario") |
| Navigation | On `202` → `/runs/:id` |
| Loading | Upload progress bar; Run button disabled with spinner during submit |
| Empty | Before upload: dropzone with sample-image link |
| Error states | Invalid file; too large; no corruption selected; model unavailable (`503`); label-metric requested on unlabeled data (`422 METRIC_UNAVAILABLE` shown at field) |

---

## 3. Evaluation Details (`/runs/:id`)

**Purpose.** Clean-versus-degraded performance at a glance, drill-down to failures.

```
Header: run id · status · model · dataset (N) · seed · [Export JSON] [Export HTML]
Gate:   [ PASS | FAIL | ERROR ]  ▸ per-rule evidence
Cards:  Retention │ Loss rate │ Conf. Δ │ Mean IoU │ Class flips │ Latency   (CONSISTENCY)
        Precision │ Recall │ F1 │ mAP50 │ mAP50:95                          (GROUND TRUTH, if labels)
Heatmap (corruption × severity, colored by relative retention)
Severity sweep chart(s)
Condition table (sortable)  ──► [View failures]
Manifest & limitations (collapsible)
```

| Aspect | Spec |
| --- | --- |
| Components | `RunProgress`, `GateBadge`, `MetricCard`, `ReliabilityHeatmap`, `SeveritySweepChart`, `ConditionTable`, `ManifestPanel`, `LimitationsPanel` |
| Data | `GET /runs/{id}` (poll 1 s while `QUEUED|RUNNING`), `GET /runs/{id}/report` when terminal |
| Actions | Cancel (while running), export, open failures, copy manifest |
| Display | Heatmap cell hover shows value, N and CI; "small sample" banner if N < 30; single-image caveat if N = 1; `null` metrics display "N/A — reason" |
| Navigation | `View failures` → `/runs/:id/failures?condition=…` |
| Loading | `queued`: "Waiting for worker"; `running`: stage + `done/total` bar |
| Empty | Completed run with zero baseline detections: explain retention is undefined |
| Error | `FAILED`: error code + message, link to logs hint; `PARTIAL`: yellow banner listing failed conditions, gate shown as `ERROR`; `CANCELLED`: neutral banner |

---

## 4. Failure Analysis (`/runs/:id/failures`)

**Purpose.** Inspect how and where behaviour changed using original vs transformed images.

```
Filters: corruption [all v] severity [all v] type [all v] image [all v]   sort: score ▾
┌ FailureCard ┐ ┌ FailureCard ┐ ...                    ┌ Detail pane ─────────────────┐
│ thumb  type │ │ ...         │                         │ ComparisonSwipe (clean|corr.) │
└─────────────┘ └─────────────┘                         │ overlay toggles: class, conf  │
                                                        │ baseline det / corrupted det  │
                                                        │ IoU, Δconf, θ, matched GT     │
                                                        └───────────────────────────────┘
```

| Aspect | Spec |
| --- | --- |
| Components | `FailureFilters`, `FailureCard`, `ComparisonSwipe`, `DetectionOverlay`, `DetectionList` |
| Data | `GET /runs/{id}/failures?…`; images via `GET /runs/{id}/artifacts/{artifact_id}` |
| Actions | Filter, sort, open detail, toggle overlays, step prev/next |
| Display | Failure type chip (`LOST_DETECTION`, …); score used for ordering only, labelled "ranking score — not a metric" |
| Loading | Card skeletons; image placeholders until loaded |
| Empty | "No failures found for this run" and "No results for these filters" (with Clear filters) |
| Error | Missing artifact (`404`): "Image no longer available (run metadata preserved)"; non-persisted images: note "Only top-K failures keep images" |

---

## 5. Settings & Glossary (`/settings`)

| Aspect | Spec |
| --- | --- |
| Purpose | Defaults, model info, metric glossary, limitations |
| Components | `DefaultsForm` (τ, θ, seed, persist policy), `ModelInfoCard`, `MetricGlossary`, `AboutLimitations` |
| Data | `GET /models`, `GET /health` |
| Glossary entries | retention, loss rate, IoU, confidence delta, class flip, precision, recall, F1, mAP, consistency vs ground truth |
| States | Loading skeleton; error banner on model info failure |

---

## 6. Component specifications

| Component | Responsibility | Key props |
| --- | --- | --- |
| `DetectionOverlay` | SVG layer over `<img>`; scales `bbox_xyxy` by natural size; class/confidence toggles | `imageUrl`, `detections`, `naturalSize`, `showLabels` |
| `ComparisonSwipe` | Before/after slider, synchronized overlays | `cleanUrl`, `corruptedUrl`, detections ×2 |
| `ReliabilityHeatmap` | corruption × severity grid, color by relative retention (or relative mAP) | `cells`, `metric` |
| `SeveritySweepChart` | Recharts line per corruption; plots API values only | `series` |
| `MetricCard` | Value, tooltip definition, family badge, N | `name`, `value`, `family`, `undefinedReason` |
| `GateBadge` | PASS/FAIL/ERROR with expandable evidence | `result` |
| `FailureCard` | Type, score, thumbnails, link | `failure` |
| `RunProgress` | Stage + `done/total` | `status` |
| `MetricGlossary` | Plain-language definitions | — |

## 7. Visual and interaction guidelines

- Two-dimensional, responsive panel layout; no 3D.
- Colors: green PASS, red FAIL, amber ERROR/PARTIAL, grey CANCELLED; never rely on color alone (icon + text).
- Distinct, consistent labels: "Clean (baseline)", "Degraded", "Confidence", "Ground truth".
- Accessibility: keyboard-operable controls, alt text on images, focus states, sufficient contrast.
- Polling stops on terminal state; show last-updated time.
- Fonts/styling: choose Tailwind **or** CSS modules once; do not spend hours on a design system.

## 8. Required UI states checklist (per screen)

| Screen | Loading | Empty | Error |
| --- | --- | --- | --- |
| Dashboard | ✔ | ✔ | ✔ |
| New Evaluation | ✔ | ✔ | ✔ |
| Evaluation Details | ✔ | ✔ | ✔ |
| Failure Analysis | ✔ | ✔ | ✔ |
| Settings | ✔ | — | ✔ |

## 9. Design hand-off checklist

- [ ] Figma (or equivalent) frames for 5 screens × states
- [ ] Heatmap color scale and legend finalized
- [ ] Glossary copy approved by methodology owner (Aditya)
- [ ] Component props agreed against generated API types
