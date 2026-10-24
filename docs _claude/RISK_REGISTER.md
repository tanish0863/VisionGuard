# Risk Register

Version 1.0 · 24 Oct 2026 · Owner: all · Source: Master Plan §O4 plus architecture-derived risks. L = likelihood, I = impact (H/M/L).

| ID | Risk | L / I | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Model installation takes too long | M / H | Verify install before event; pin versions; tested fallback and sample outputs | Chinmay | Open |
| R-02 | Frontend/backend integration fails | H / H | Freeze schemas early; vertical slice first; shared fixtures; generated TS types | Tanish | Open |
| R-03 | Metrics are misleading | M / H | Written formulas, hand-checked tests; consistency vs ground-truth separation | Aditya | Open |
| R-04 | Inference too slow | M / M | Small model; cap image size/conditions; no uncontrolled concurrency; measure (M-1) | Chinmay | Open |
| R-05 | Demo internet fails | M / H | Local model, local samples, local startup plan | Member 5 | Open |
| R-06 | Scope creep | H / H | P0/P1/P2 list; feature freeze 29 Oct; no training before core flow | Tanish | Open |
| R-07 | Dataset/model licence issue | L–M / H | Check terms; document sources in `samples/SOURCES.md`; small permitted sample | Member 5 | Open |
| R-08 | Ultralytics AGPL-3.0 conflicts with future closed-source/SaaS plans | M / M | Adapter boundary; ADR-05; revisit before productization | Tanish | Open |
| R-09 | Windows-specific failures (paths, multiprocessing, `pycocotools` build) | M / M | `pathlib`; single process; test on Windows early; document fix | All | Open |
| R-10 | Overclaiming novelty/performance in pitch | M / H | Use "we did not find"; only measured numbers; review pitch against 07 §7 | Tanish | Open |
| R-11 | Uncalibrated severities give uninformative results | M / M | Calibration M-2 before demo | Chinmay | Open |
| R-12 | Runtime nondeterminism blamed on corruption | M / M | Clean-vs-clean control (P1); report floor | Aditya | Open |
| R-13 | Single-process job runner loses state on restart | M / L | `status.json` + startup recovery marks `INTERRUPTED` | Tanish | Open |
| R-14 | Truncated/inconsistent architecture source (§8–§18 missing) leads to contract drift | M / H | Reconcile `[PROPOSED]` items; approve contracts at kickoff | Tanish | **New** |
| R-15 | Fifth member unassigned; docs 5/9/10, demo, report generator lack an owner | M / M | Confirm assignment at kickoff | Tanish | **New** |
| R-16 | Official HackFusion problem statement differs from VisionGuard | M / H | Read brief in first hour; use VisionGuard as reliability layer | Team | Open |
| R-17 | Untrusted upload (zip bomb, traversal, malformed image) | L / H | Validation rules; SEC test cases | Aditya / Tanish | Open |
