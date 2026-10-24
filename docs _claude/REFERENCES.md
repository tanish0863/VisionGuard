# Research References and Licensing Notes

Version 1.0 · 24 Oct 2026 · Owner: Member 5 (TBC). Drawn from the sources' research summary; **bibliographic details below are as cited in the architecture text and have not been re-verified here — confirm before publishing.**

## Papers and benchmarks

| Reference | Relevance |
| --- | --- |
| Hendrycks & Dietterich — corruption robustness benchmark (ImageNet-C) | Corruption taxonomy (noise / blur / weather / digital) |
| Michaelis et al. (2019) — benchmarking robustness in object detection (Pascal-C, COCO-C, Cityscapes-C; 15 corruptions × 5 severities) | Motivation: detectors reportedly lost performance down to 30–60 % of original on corrupted images; relative-performance idea. Verify the exact `relative` definition before using the name (M-3) |
| Wang et al. — survey of corruption robustness | Inconsistent evaluation practices; supports fixed, recorded protocol |
| DeepBench (2025) | LLM-assisted domain-specific corruption selection (vision-language focus) |

## Tools and libraries

| Item | Use | Licence / note |
| --- | --- | --- |
| `imagecorruptions` | Possible P2 corruption backend | **Verify** licence, NumPy/Python compatibility and offline assets |
| Deepchecks `RobustnessReport` | Closest analogue to the gate | Library/notebook-style |
| FiftyOne community plugin | Corrupted image generation helper | Dataset helper, not an evaluation-and-gate product |
| Ultralytics YOLO | Fast-path detector | **AGPL-3.0**; separate Enterprise licence for closed/commercial use. Not legal advice |
| `pycocotools` / TorchMetrics | Standard mAP evaluation | Pin versions; record in manifest |
| `faster-coco-eval` | Alternative mAP backend | |
| FastAPI, Pydantic, OpenCV, Pillow, NumPy, SciPy | Core stack | Check each licence |
| React, Vite, Recharts, TanStack Query, `openapi-typescript` | Frontend | Check each licence |

## Data

| Dataset | Status |
| --- | --- |
| Demo images / tiny COCO set | Licences to be verified and listed in `samples/SOURCES.md` |

## Positioning statement

A search-based review (not an exhaustive prior-art study) found the *general idea* is established. We did not find a tool that combines the six differentiators in the searches performed; absence of evidence in a limited search is not proof of absence.
