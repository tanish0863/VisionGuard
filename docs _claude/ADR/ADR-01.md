# ADR-01 — Modular monolith
- Status: Proposed · Date: 24 Oct 2026 · Deciders: team (Tanish final)

## Context
Five people, a 24-hour build, local-first demo. Microservices, queues and Kubernetes add failure modes without benefit.

## Decision
One backend process, one frontend, one core Python package imported by both API and CLI. Single-worker job runner inside the API process.

## Consequences
+ Fewer integration risks; evaluation logic written once. − No horizontal scaling; one run at a time; Uvicorn must run a single process. Revisit if measured runtime requires a queue.
