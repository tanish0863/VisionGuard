# ADR-06 — Two metric families, never mixed
- Status: Proposed · Date: 24 Oct 2026

## Context
Confidence and baseline consistency are routinely mistaken for accuracy.

## Decision
Consistency (label-free) and ground-truth metrics are separated in schema, UI badges and report text. "False positive" and "false negative" are used only in labeled mode. `retention` and "prediction consistency" are the same metric.

## Consequences
+ Honest claims. − More UI/schema surface.
