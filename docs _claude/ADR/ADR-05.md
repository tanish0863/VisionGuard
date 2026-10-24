# ADR-05 — Detector behind an adapter; Ultralytics first
- Status: Proposed · Date: 24 Oct 2026

## Context
A pretrained detector keeps the MVP buildable. Ultralytics YOLO is AGPL-3.0 with an Enterprise licence for commercial closed use. Newer models may be NMS-free.

## Decision
Only `models/*_adapter.py` import a detector library. Adapters: `MockAdapter` (P0, dev/CI, never selectable in demo), `UltralyticsAdapter` (P0), `TorchvisionAdapter` (P1), `HFTransformersAdapter` (P2). Pin exact package and weights; checksum-verified.

## Consequences
+ Licence/model can change without rewriting the platform. − Output normalization per adapter. Re-check licence before any closed-source/SaaS plan (not legal advice).
