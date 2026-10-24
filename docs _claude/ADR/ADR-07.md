# ADR-07 — Single schema source: Pydantic → OpenAPI → generated TypeScript
- Status: Proposed · Date: 24 Oct 2026

## Context
Parallel frontend/backend work risks contradictory contracts.

## Decision
Pydantic models in `visionguard/schemas/` are authoritative; OpenAPI is generated; frontend types are generated into `api.gen.ts`. No hand-written duplicates; contract changes follow 09 §9.

## Consequences
+ No drift. − A generation step in the workflow.
