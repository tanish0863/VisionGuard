# Demo and Presentation Plan

Version 1.0 · 24 Oct 2026 · Owner: Member 5 (TBC) · Source: Master Plan §O1–§O3, Architecture Appendix B (referenced)

## 1. Principles

- Use **actual model inference** and measured values only; no placeholder numbers.
- State clearly whether ground-truth labels were used.
- Local-first: model, samples and app run offline.
- Never claim the idea is new — say "we did not find a tool that combines all of these".

## 2. Three-minute live demo

| Time | Step | Show | Say |
| --- | --- | --- | --- |
| 0:00–0:20 | Opening | Title/problem slide | Models degrade under conditions unlike their training data |
| 0:20–0:45 | Baseline | Upload prepared image; real detections | Same model, same settings |
| 0:45–1:25 | Stress test | Choose blur, low light, noise; run severities 1–3 | Controlled, seeded corruptions |
| 1:25–2:00 | Compare | Results page: heatmap, retention, confidence delta, clean vs degraded | Consistency metrics vs ground-truth metrics are separate |
| 2:00–2:30 | Failure explorer | Open one lost/changed detection with before/after swipe | Concrete, inspectable failures |
| 2:30–2:50 | Reproducibility | Manifest, run history, gate verdict, export | Re-runnable evidence |
| 2:50–3:00 | Close | Limitations slide | What results mean; whether labels were used |

## 3. Pitch

"VisionGuard helps developers discover when a computer vision model becomes unreliable. Instead of testing only clean images, it runs controlled stress tests, compares model outputs, identifies failure cases, and records reproducible evidence. It does not pretend that confidence equals correctness: where labels are available, it reports ground-truth metrics; otherwise, it clearly reports baseline consistency."

## 4. Differentiators to mention (integrated-workflow claims only)

1. Upload → stress test → failure explorer → shareable report in one app.
2. Strict separation of consistency vs ground-truth metrics.
3. Regression gate with PASS/FAIL/ERROR and CLI exit codes (P1).
4. Reproducibility manifest (replay is P2).
5. Scenario presets.
6. Model-agnostic adapter.

## 5. Likely judge questions

| Question | Answer direction |
| --- | --- |
| How is this different from just running a model? | Orchestrates controlled transformations, fixed comparison protocol, failure collection, reproducible settings |
| How do you know a model failed? | We separate prediction changes from true errors; error metrics need labels, consistency is reported separately |
| Is your score scientifically validated? | It is a defined project metric on a documented test set, with formulas, N and limitations — not a certification |
| Can it work with any model? | Not yet; the adapter pattern is extensible but each model/task needs an adapter |
| What about video? | Stretch: sample frames, run the same tests, aggregate |
| What is novel? | Not the idea; the integrated workflow, usability, reproducibility, failure inspection and honest reporting |
| Why not accuracy? | Without labels, accuracy is unknowable; we say so |

## 6. Preparation checklist

- [ ] Prepared sample image(s) and tiny labeled set; licences noted
- [ ] Known-good run seeded in history as a fallback
- [ ] Fresh-start rehearsal on the demo machine (Windows)
- [ ] Network-off rehearsal
- [ ] Error-path rehearsal (invalid upload)
- [ ] Screenshots and architecture diagram for submission
- [ ] Every number on slides traceable to a run report
- [ ] Roles: presenter, driver, Q&A per member; all five can explain the pipeline

## 7. Submission checklist

README (problem, solution, architecture, setup, sample workflow, limitations) · diagram and screenshots · pinned dependencies and `.env.example` · demo data with licence notes · known-good config and truthful results · roles, repo link, demo link if deployed · no API keys, personal images, large artifacts or secrets.

## 8. Fallbacks

| Failure | Fallback |
| --- | --- |
| GPU unavailable | CPU run on small sample |
| Live run too slow | Open the seeded known-good run |
| Backend crash | Restart script; run persists on disk |
| Projector/Wi-Fi | Everything local; screenshots as last resort |
