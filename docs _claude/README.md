# VisionGuard — Documentation Set

Computer Vision Reliability Testing & Failure-Analysis Platform.
Documentation baseline v1.0 · 24 October 2026 · Status: **Draft for team approval**

## How these documents were produced

Generated from two team inputs:

- `VisionGuard_Computer_Vision_Master_Plan.docx` (v1.0, 23 Oct 2026)
- `VisionGuard_SYSTEM_ARCHITECTURE.md` (v1.0, 24 Oct 2026)

The documentation-planning guide (10 core documents, 3 approval stages, 4 frozen contracts) defines the set below.

> **Source gap — please read.** The uploaded architecture file stops in the middle of §7.4 (the `report.json` schema). Sections §8 (API), §9 (Storage), §10 (Regression Gate), §11 (Errors/Logging), §12 (Security), §13 (Deployment), §14 (Testing), §15 (Team), §16–§18 and Appendices A–D were **not present**, although earlier sections refer to them. Where those documents needed that content, it was **drafted here as a proposal consistent with the references in §1–§7**, and is tagged **`[PROPOSED]`**. Everything not tagged is taken from the two source files. Review every `[PROPOSED]` item before freezing contracts. If you have the complete architecture file, send it and these can be reconciled.

## Document index

| No. | File | Stage | Owner (suggested) |
| --- | --- | --- | --- |
| 1 | [01_PRODUCT_REQUIREMENTS.md](01_PRODUCT_REQUIREMENTS.md) | 1 | Tanish |
| 2 | [02_SOFTWARE_REQUIREMENTS.md](02_SOFTWARE_REQUIREMENTS.md) | 1 | Tanish |
| 3 | [03_SYSTEM_ARCHITECTURE.md](03_SYSTEM_ARCHITECTURE.md) | 1 | Tanish + module owners |
| 4 | [04_UI_UX_SPECIFICATION.md](04_UI_UX_SPECIFICATION.md) | 2 | Vanashree |
| 5 | [05_API_SPECIFICATION.md](05_API_SPECIFICATION.md) | 2 | Member 5 (TBC) with Tanish |
| 6 | [06_DATA_SCHEMA.md](06_DATA_SCHEMA.md) | 1 | Tanish + all |
| 7 | [07_EVALUATION_METHODOLOGY.md](07_EVALUATION_METHODOLOGY.md) | 1 | Aditya (corruptions: Chinmay) |
| 8 | [08_TEST_PLAN.md](08_TEST_PLAN.md) | 3 | Aditya |
| 9 | [09_DEVELOPMENT_WORKFLOW.md](09_DEVELOPMENT_WORKFLOW.md) | 2 | Member 5 (TBC) |
| 10 | [10_SETUP_AND_ENVIRONMENT.md](10_SETUP_AND_ENVIRONMENT.md) | 2 | Member 5 (TBC) |
| — | [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) | 3 | Tanish |
| — | [RISK_REGISTER.md](RISK_REGISTER.md) | 3 | All |
| — | [DEMO_PLAN.md](DEMO_PLAN.md) | 3 | Member 5 (TBC) |
| — | [REFERENCES.md](REFERENCES.md) | 3 | Member 5 (TBC) |
| — | [USER_GUIDE.md](USER_GUIDE.md) | 3 | Member 5 (TBC) |
| — | [ADR/](ADR/) | 3 | Decision owner |

## Approval stages

1. **Stage 1 — Product & technical agreement:** PRD, SRS, Architecture, Data Schema, Evaluation Methodology.
2. **Stage 2 — Parallel development preparation:** API Spec, UI/UX Spec, Development Workflow, Setup Guide.
3. **Stage 3 — Implementation verification (evolves):** Test Plan, Roadmap, Risk Register, Demo Plan, User Guide.

## The four contracts to freeze before parallel coding

| # | Contract | Where defined |
| --- | --- | --- |
| 1 | Dataset contract | 06 §2–§3 (COCO zip in, `xyxy` internally) |
| 2 | Prediction contract | 06 §4 (adapter output) |
| 3 | Evaluation contract | 07 (matching, metrics, failure taxonomy) |
| 4 | API contract | 05 (endpoints, errors, run lifecycle) |

## Reconciliation decisions applied (Master Plan vs Architecture)

| Topic | Decision of record |
| --- | --- |
| Input unit | Run evaluates a dataset of 1…N images; single image = dataset of one, no labels |
| Run endpoint | `POST /api/v1/runs` (dataset created first via `POST /api/v1/datasets`); `/api/analyze` is dropped |
| Persistence | Filesystem is source of truth; SQLite only a disposable index of runs |
| Code layout | Framework-free `visionguard` core package; FastAPI layer is thin |
| Retention vs consistency | One metric: `retention` |
| "False positive" | Reserved for labeled mode; label-free term is `unmatched_corrupted` |
| Rotation | P2 (changes coordinate frame) |
| Corruption severities | VisionGuard's own 1–3 scale, not comparable to ImageNet-C |

## Open items needing a human decision

1. Name of the fifth team member and final ownership of docs 5, 9, 10, demo, report generator.
2. Official HackFusion 2.0 problem statement, rubric and dates (not yet confirmed in the sources).
3. Chosen detector, exact package/weights version (Ultralytics is AGPL-3.0 — see ADR-05).
4. Placeholder limits (`MAX_IMAGES`, upload caps, condition cap) — to be set after measurement task M-1.
5. Severity calibration (M-2) before any numbers appear in the pitch.
6. Repository URL.
