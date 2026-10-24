# ADR-03 — Dataset-oriented runs (image = dataset of one)
- Status: Proposed · Date: 24 Oct 2026

## Context
Master Plan: single-image `/api/analyze`. Architecture guide: labeled dataset, `/api/runs`.

## Decision
A run evaluates a dataset of 1…N images; labels optional. Dataset created via `POST /datasets`, then `POST /runs`.

## Consequences
+ One code path for both modes; labeled metrics reachable. − Two-step upload for the simplest case (mitigated by the UI sample button).
