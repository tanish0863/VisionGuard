# ADR-02 — Framework-free core package (`visionguard`)
- Status: Proposed · Date: 24 Oct 2026 · Deciders: Tanish

## Context
The Master Plan placed services under `backend/app/services/`; the architecture requires the same evaluation from web, CLI and future CI.

## Decision
`visionguard` has zero web imports; `api/` is a thin layer (parse → call → return schema). Dependency rules in 03 §3.

## Consequences
+ Testable modules, CLI/CI reuse, parallel ownership. − An extra boundary to maintain; rules need review or `import-linter`.
