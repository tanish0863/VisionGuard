# Project Roadmap

Version 1.0 · 24 Oct 2026 · Owner: Tanish · Source: Master Plan §M, §O5

> Dates below come from the Master Plan's preparation window. The official HackFusion 2.0 event dates and rubric are **unconfirmed** — update when known.

## 1. Preparation window

| Date | Target | Evidence of completion |
| --- | --- | --- |
| 23 Oct | Scope agreed, repository created, API contract defined, stack installed | README skeleton, issues, shared request/response fixture |
| 24 Oct | Baseline inference and image upload; **documentation set approved (Stage 1)** | A real image returns structured detections through the API |
| 25 Oct | Corruption engine and matching | Three transformations work; tests cover basic cases |
| 26 Oct | Frontend comparison UI and metrics | Real API results in the dashboard |
| 27 Oct | Persistence, history, failure explorer | Completed run can be revisited |
| 28 Oct | Automated tests, report, robustness fixes | Test suite and report work on prepared samples |
| 29 Oct | Feature freeze, fresh-start test, pitch rehearsal | Documented startup; no critical blockers |

## 2. Documentation gates

| Gate | Documents | Needed before |
| --- | --- | --- |
| Stage 1 | PRD, SRS, Architecture, Data Schema, Evaluation Methodology | Any parallel coding |
| Stage 2 | API, UI/UX, Dev Workflow, Setup Guide | Module development |
| Stage 3 | Test plan, roadmap, risk register, demo plan, user guide | Evolve with implementation |

Four contracts frozen before parallel coding: dataset, prediction, evaluation, API.

## 3. 24-hour event execution

| Phase | Time | Goal |
| --- | --- | --- |
| Brief and plan | Hour 0–1 | Read official PS/rubric; adapt scope; agree acceptance criteria |
| Vertical slice | 1–4 | Upload → real inference → result in UI |
| Core CV test | 4–9 | Corruptions, repeat inference, comparison metrics |
| Integration | 9–14 | History, failures, stable schema |
| Polish and validation | 14–19 | Errors, charts, report, tests, responsive UI |
| Demo hardening | 19–22 | Clean restart, sample data, offline plan, rehearsal |
| Buffer and submission | Final 2 h | Critical fixes only; verify submission assets |

Planning allocations, not promises; adapt after the first working slice.

## 4. Priorities and cut order

| Priority | Features |
| --- | --- |
| P0 | Upload, baseline inference, 3 corruptions, comparison, 2–3 correctly defined metrics, failure view, stable API, working demo |
| P1 | Run history, 5–8 corruptions, report export (HTML), seeds, metric explanations, COCO labeled metrics, gate + CLI, presets, bootstrap CIs |
| P2 | Two-model comparison, replay, video, accounts, PDF, rotation with box mapping |
| Cut first | Video, auth, custom training, cloud GPU, elaborate animation, complex deployment |

## 5. Pre-event measurement tasks

| ID | Task |
| --- | --- |
| M-1 | Measure latency/memory on the real demo machine; set `MAX_IMAGES`; no latency claims before this |
| M-2 | Calibrate corruption severities on the sample set |
| M-3 | Verify `relative_map50` definition against the source paper |
| M-4 | Verify detector NMS behaviour and `conf_floor` |
| M-5 | Hand-check matching/metric examples |

## 6. Post-hackathon roadmap

| Stage | Extension |
| --- | --- |
| V1 | Hackathon MVP: single model, image corruptions, comparison metrics, failure explorer, saved run |
| V2 | Evaluation toolkit: batch datasets, labeled benchmarks, CSV/JSON reports, model version comparison |
| V3 | Video: frame sampling, temporal consistency, tracking-aware failures |
| V4 | Domain adapters: PCB, road damage, industrial safety, agriculture |
| V5 | Calibration, distribution shift, explainability, confidence intervals, custom suites |
