# VisionGuard API Reference

VisionGuard exposes a versioned REST API under `/api/v1`.

Base URL in local development: `http://127.0.0.1:8000`

---

## 1. System Endpoints

### 1.1 Root
- **Method:** `GET /`
- **Response:**
```json
{
  "name": "VisionGuard API",
  "status": "ok"
}
```

### 1.2 Health Check
- **Method:** `GET /health`
- **Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## 2. Models & Datasets

### 2.1 List Supported Models
- **Method:** `GET /api/v1/models`
- **Response:**
```json
{
  "models": [
    {
      "model_id": "fasterrcnn_resnet50_fpn",
      "name": "Faster R-CNN ResNet-50 FPN",
      "framework": "TorchvisionDetector",
      "task": "object_detection",
      "default_weights": "DEFAULT",
      "supported": true
    },
    {
      "model_id": "fasterrcnn_resnet50_fpn_v2",
      "name": "Faster R-CNN ResNet-50 FPN v2",
      "framework": "TorchvisionDetector",
      "task": "object_detection",
      "default_weights": "DEFAULT",
      "supported": true
    }
  ]
}
```

### 2.2 List Registered Datasets
- **Method:** `GET /api/v1/datasets`
- **Response:**
```json
{
  "datasets": [
    {
      "id": "visionguard_demo",
      "name": "VisionGuard Demo Dataset",
      "description": "Registered VisionGuard demo images with COCO-format ground truth annotations.",
      "image_count": 5,
      "has_ground_truth": true,
      "supported": true
    }
  ]
}
```

---

## 3. Evaluation Runs

### 3.1 Create and Enqueue Run
- **Method:** `POST /api/v1/runs`
- **Request Body:**
```json
{
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "corruptions": [
    {
      "name": "gaussian_noise",
      "severity": 2
    }
  ],
  "iou_threshold": 0.5,
  "confidence_threshold": 0.5,
  "seed": 42,
  "max_samples": 5
}
```
- **Response (202 Accepted):**
```json
{
  "run_id": "vg-20261025-a1b2c3d4",
  "status": "QUEUED",
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "created_at": "2026-10-25T16:50:00Z"
}
```
- **Error Responses:**
  - `400 Bad Request`: Unknown model or unregistered dataset.
  - `422 Unprocessable Entity`: Validation failure on request body.

### 3.2 List Runs
- **Method:** `GET /api/v1/runs?limit=20&offset=0`
- **Response:**
```json
{
  "runs": [
    {
      "run_id": "vg-20261025-a1b2c3d4",
      "status": "COMPLETED",
      "model_id": "fasterrcnn_resnet50_fpn",
      "dataset_id": "visionguard_demo",
      "created_at": "2026-10-25T16:50:00Z",
      "updated_at": "2026-10-25T16:50:15Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 3.3 Get Run Details
- **Method:** `GET /api/v1/runs/{run_id}`
- **Response:**
```json
{
  "run_id": "vg-20261025-a1b2c3d4",
  "status": "COMPLETED",
  "model_id": "fasterrcnn_resnet50_fpn",
  "dataset_id": "visionguard_demo",
  "config": {
    "model_id": "fasterrcnn_resnet50_fpn",
    "dataset_id": "visionguard_demo",
    "corruptions": [{"name": "gaussian_noise", "severity": 2}],
    "iou_threshold": 0.5,
    "confidence_threshold": 0.5,
    "seed": 42,
    "max_samples": 5
  },
  "created_at": "2026-10-25T16:50:00Z",
  "started_at": "2026-10-25T16:50:01Z",
  "finished_at": "2026-10-25T16:50:15Z",
  "error_message": null
}
```

### 3.4 Get Evaluation Report
- **Method:** `GET /api/v1/runs/{run_id}/report`
- **Response:**
```json
{
  "schema_version": "1.0.0",
  "is_fixture": false,
  "run_id": "vg-20261025-a1b2c3d4",
  "status": "COMPLETED",
  "model": {
    "model_id": "fasterrcnn_resnet50_fpn",
    "name": "Faster R-CNN ResNet-50 FPN",
    "framework": "TorchvisionDetector",
    "weights": "DEFAULT",
    "weights_license": "PyTorch"
  },
  "dataset": {
    "dataset_id": "visionguard_demo",
    "name": "VisionGuard Demo Dataset",
    "image_count": 5,
    "has_ground_truth": true
  },
  "summary": {
    "clean_map50": 0.78,
    "corrupted_map50": 0.52,
    "relative_drop": 0.333,
    "total_images": 5,
    "failure_count": 4,
    "error_count": 0
  },
  "conditions": [
    {
      "corruption_name": "gaussian_noise",
      "severity": 2,
      "map50": 0.52,
      "relative_drop": 0.333,
      "retention_rate": 0.67,
      "class_flip_rate": 0.05
    }
  ],
  "failures": [],
  "errors": []
}
```

---

## 4. Image Artifact Endpoints

### 4.1 List Run Artifacts
- **Method:** `GET /api/v1/runs/{run_id}/artifacts`
- **Response:**
```json
{
  "run_id": "vg-20261025-a1b2c3d4",
  "artifacts": [
    {
      "artifact_id": "01_street_urban__clean",
      "image_id": "01_street_urban",
      "artifact_type": "clean",
      "mime_type": "image/jpeg",
      "url": "/api/v1/runs/vg-20261025-a1b2c3d4/artifacts/01_street_urban__clean",
      "available": true,
      "corruption_name": null,
      "severity": null
    },
    {
      "artifact_id": "01_street_urban__gaussian_noise_s2",
      "image_id": "01_street_urban",
      "artifact_type": "corrupted",
      "mime_type": "image/jpeg",
      "url": "/api/v1/runs/vg-20261025-a1b2c3d4/artifacts/01_street_urban__gaussian_noise_s2",
      "available": true,
      "corruption_name": "gaussian_noise",
      "severity": 2
    },
    {
      "artifact_id": "01_street_urban__overlay",
      "image_id": "01_street_urban",
      "artifact_type": "overlay",
      "mime_type": "image/jpeg",
      "url": "/api/v1/runs/vg-20261025-a1b2c3d4/artifacts/01_street_urban__overlay",
      "available": false,
      "corruption_name": null,
      "severity": null
    }
  ]
}
```

### 4.2 Retrieve Binary Image Artifact
- **Method:** `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}`
- **Response (200 OK):**
  - Content-Type: `image/jpeg` or `image/png`
  - Body: Binary image stream
- **Security:**
  - Path traversal attempts (`../`) are detected and rejected with `403 Forbidden` / `404 Not Found`.
  - Only paths within registered dataset roots are served.
- **Unavailable Overlay Response (404 Not Found):**
```json
{
  "detail": "Overlay visualizations are not generated server-side in this release. Bounding boxes are available in the run report for client-side rendering."
}
```
