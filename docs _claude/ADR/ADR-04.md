# ADR-04 — Filesystem is source of truth; SQLite is a disposable index
- Status: Proposed · Date: 24 Oct 2026

## Context
Master Plan proposed a relational model (runs, test_cases, detections, artifacts). Heavy schema is unnecessary for the MVP.

## Decision
Authoritative records are `report.json` and `status.json` per run on disk. SQLite stores one `runs` index table, rebuildable from disk. No ORM-heavy schema.

## Consequences
+ Trivial recovery; reports portable. − No rich queries; PostgreSQL deferred to V2+.
