# 09 — Development and Git Workflow

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Member 5 (TBC) with Tanish |
| Stage | 2 — ready before module development |
| Sources | Master Plan §D1, §L; Architecture §4.3, §15; documentation guide §2 Doc 9 |

## 1. Repository structure

See 03 §15. Key rules: one package manager per side (decide `pyproject.toml` **or** `requirements.txt`; update commands and README accordingly); weights, datasets, uploads, `storage/` and `artifacts/` are git-ignored; `.env.example` is committed, `.env` never.

## 2. Team responsibilities

| Member | Primary module | Deliverables |
| --- | --- | --- |
| Tanish | Backend API, orchestrator, run/artifact store, CLI, PRD/SRS/architecture, shared contracts | Routes, schemas, run lifecycle, startup recovery, integration |
| Chinmay | Model adapter, corruption engine; corruption methodology | `DetectorAdapter`s, `Corruption` registry, calibration M-1/M-2 |
| Vanashree | Frontend and UI/UX spec | Pages, components, heatmap, failure explorer, generated API types |
| Aditya | Dataset loader, matcher/metrics, failure analysis, gate; evaluation methodology and test plan | Matching, metrics, taxonomy, gate, test fixtures |
| Member 5 (name TBC) | API spec upkeep, report generator, setup/docs, demo coordination, QA | `report.json`/HTML, README/setup, demo plan |

Ownership is a suggestion from the architecture and planning guide — **confirm names and the fifth member's scope at kickoff.**

**Learning rule:** each member completes one small task outside their module and can explain the full image-to-report pipeline.

## 3. Branch strategy

```
main                  protected; release-quality; only via PR
├── chinmay           personal integration branch
├── tanish
├── vanashree
├── aditya
└── documentation     docs + member 5 work
```

- Direct pushes to `main` are disabled; PRs require ≥ 1 review (≥ 2 for contract changes).
- Each developer works on their branch, raises PRs into `main`, merges after review, then rebases/merges `main` back into their branch **at least daily**.
- Optional short-lived topic branches: `feat/<owner>-<topic>`, `fix/<owner>-<topic>`, `docs/<topic>`, e.g. `feat/chinmay-motion-blur`.
- ⚠ Do **not** create `tanish/feature` style branches while a branch named `tanish` exists — Git cannot hold both `tanish` and `tanish/...` refs.

## 4. Commit message conventions

Conventional Commits: `<type>(<scope>): <summary>` (imperative, ≤ 72 chars).

| Type | Use |
| --- | --- |
| `feat` | New functionality |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Tests |
| `refactor` | No behaviour change |
| `chore` | Tooling, deps, config |
| `contract` | Change to schemas/API (also label PR `contract-change`) |

Scopes: `api`, `core`, `adapter`, `corruption`, `metrics`, `failures`, `gate`, `report`, `storage`, `cli`, `ui`, `docs`. Commit working slices — not one giant commit at the end.

## 5. Pull request process

1. Branch is up to date with `main`; tests and lint pass locally.
2. PR description: what/why, linked issue, how tested, screenshots for UI, **contract impact: yes/no**.
3. CI (or manual checklist) passes: backend tests, frontend build, type generation clean.
4. Reviewer assigned from a different module where possible; response within agreed time (suggested: same working day during the build).
5. Author resolves comments; reviewer approves; **author squash-merges**.
6. Delete merged topic branches.

### PR template

```markdown
## What / Why
## Linked issue
## How tested (commands, test IDs)
## Contract impact  [ ] none  [ ] schema  [ ] API  — approvers tagged
## Screenshots (UI)
## Checklist
- [ ] Tests added/updated  - [ ] Docs updated  - [ ] No secrets / absolute paths  - [ ] DoD met
```

## 6. Code review rules

- Check: correctness, tests, dependency rules (03 §3), no web imports in `visionguard`, no detector imports outside `*_adapter.py`, no hand-written API types in frontend, no fabricated/default results on failure.
- Contract changes (`schemas/`, 05, 06) get a dedicated review (see §9).
- Reviewers comment on behaviour, not style that linters enforce.
- No self-approval. Blocking comments must state what would unblock.

## 7. Coding standards

| Area | Standard |
| --- | --- |
| Python | 3.x (pin in 10), type hints on public functions, Pydantic for data, `ruff` + `black` (or `ruff format`), `pathlib` for all paths, no fork-only multiprocessing |
| Logging | Structured; include `run_id`; never log full images |
| Errors | Raise typed errors mapped to the error catalogue; no bare `except`; no stack traces in responses |
| Determinism | Seeds explicit; no global RNG |
| TypeScript | `strict` mode; ESLint + Prettier; generated types only for API payloads |
| Frontend | One styling approach (Tailwind **or** CSS modules); every screen handles loading/empty/error |
| Tests | New logic ships with tests; metric changes need hand-checked values |
| Docs | Update the relevant doc in the same PR |
| Secrets | Never committed; `.env.example` documents variables |

## 8. File ownership (CODEOWNERS)

```
/backend/api/                     @tanish
/backend/visionguard/orchestrator.py @tanish
/backend/visionguard/storage/     @tanish
/backend/visionguard/schemas/     @tanish @aditya   # shared; contract-change rules apply
/backend/visionguard/models/      @chinmay
/backend/visionguard/corruptions/ @chinmay
/backend/visionguard/io/          @aditya
/backend/visionguard/matching/    @aditya
/backend/visionguard/metrics/     @aditya
/backend/visionguard/failures/    @aditya
/backend/visionguard/gate/        @aditya
/backend/visionguard/report/      <member5-handle>
/frontend/                        @vanashree
/docs/                            @tanish <member5-handle>
```
(Replace GitHub handles; add Member 5.)

## 9. Shared schema and architecture approvals

| Change | Approvers |
| --- | --- |
| `schemas/`, 06 Data Schema | Tanish (final) + Aditya + at least one consumer (Vanashree for UI fields) |
| API spec 05 / OpenAPI | Tanish (final) + Vanashree |
| Evaluation methodology 07 (metric definitions) | Aditya (final) + Chinmay |
| Architecture 03 / dependency rules | Tanish (final) + one module owner |
| Corruption catalog values | Chinmay (final) + Aditya |

Process: open an issue → PR labelled `contract-change` → update fixtures and docs together → all approvers approve → merge → regenerate frontend types → announce in the team channel. **Do not start parallel implementations against an unapproved contract.**

## 10. Conflict resolution

1. Merge conflicts: the person merging second resolves; for shared files ask the owner.
2. Technical disagreement: time-box to 15 minutes; if unresolved the final approver in §9 decides and records an ADR.
3. Scope disagreement: use the P0/P1/P2 list; P0 wins; cut P2 first.

## 11. Integration schedule

| Integration | Evidence |
| --- | --- |
| 1 | `/health` route + frontend connection |
| 2 | Image upload returns real baseline detections |
| 3 | One corruption + one comparison result |
| 4 | All MVP corruptions, metrics, saved run |
| 5 | Report, error states, clean startup, demo rehearsal |

Calendar from the Master Plan: 23 Oct scope/repo/contract; 24 Oct baseline inference + upload; 25 Oct corruptions + matching; 26 Oct frontend comparison + metrics; 27 Oct persistence/history/failures; 28 Oct tests/report/robustness; 29 Oct feature freeze, fresh-start test, pitch rehearsal. See PROJECT_ROADMAP.md. Integration is merged in small steps by Tanish (integration owner).

## 12. Issue tracking

One shared board (GitHub Projects or Jira). Each issue: owner, acceptance criteria (link SRS ID), dependencies, priority (P0/P1/P2), status (`Backlog → In progress → In review → Done`). Labels: `contract-change`, `blocker`, `P0/P1/P2`, module labels.

## 13. Definition of Done

A task is done when:

- [ ] Code merged to `main` via reviewed PR
- [ ] Unit/integration tests added and passing; relevant TC-IDs updated
- [ ] Runnable example or usage note provided
- [ ] Schemas/API/docs updated if affected; fixtures committed
- [ ] No secret, local absolute path, large artifact or model binary committed
- [ ] Errors handled visibly; no fabricated results
- [ ] Works on a clean checkout using documented commands (Windows verified where relevant)
- [ ] Component status in 03 updated (`PLANNED → IN PROGRESS → IMPLEMENTED`)
