# VisionGuard Datasets System

## Overview

VisionGuard manages test datasets via a central dataset catalog.

Endpoints:
- **List Datasets:** `GET /api/v1/datasets`

---

## Registered Datasets

In the current MVP release, VisionGuard registers the following dataset:

### `visionguard_demo`
- **ID:** `visionguard_demo`
- **Name:** VisionGuard Demo Dataset
- **Description:** Registered VisionGuard demo images with COCO-format ground truth annotations.
- **Directory:** `backend/visionguard/datasets/visionguard_demo`
- **Images:** 5 JPEG images covering urban traffic, road scenes, pedestrians, and vehicles.
- **Ground Truth:** `annotations.json` with standard COCO-format bounding boxes.
- **Status:** Supported and verified.

---

## Dataset Validation in Run Creation

When a client creates an evaluation run via `POST /api/v1/runs`:
```json
{
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "corruptions": [...]
}
```

The API validates `dataset_id` against the registered dataset catalog:
- If the dataset exists and is accessible, the run is accepted (`202 Accepted`).
- If `dataset_id` is unknown or unregistered, the API responds with `400 Bad Request` containing an explanatory error message:
  ```json
  {
    "detail": "Unknown or unregistered dataset 'invalid_dataset'. Available datasets: ['visionguard_demo']"
  }
  ```

---

## Registering New Datasets (Future Work)

To register a new dataset:
1. Place dataset images and COCO annotations in `backend/visionguard/datasets/<dataset_id>/`.
2. Register the dataset specification in `backend.visionguard.core.pipeline.get_registered_datasets()`.
3. The dataset will immediately be exposed through `GET /api/v1/datasets` and validated during run creation.
