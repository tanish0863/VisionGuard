# ADR-08 — VisionGuard's own 1–3 severity scale
- Status: Proposed · Date: 24 Oct 2026

## Context
Published benchmarks use 5-level severities with different parameterizations.

## Decision
Severities 1–3 (Mild/Moderate/Severe) with parameters defined at a 640-px reference short side and calibrated (M-2). Reports must not imply comparability with ImageNet-C or published benchmark numbers.

## Consequences
+ Simple, resolution-independent. − Not comparable to the literature; optional `imagecorruptions` provider is P2.
