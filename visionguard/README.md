# VisionGuard

Stress-tests an object detector (YOLOv8 nano) under blur, low light, noise, rotation, JPEG compression and occlusion,
then compares each degraded result to the clean baseline: detection retention, confidence change, lost / class-changed /
spurious detections and latency. Each run is stored in SQLite and exportable as a Markdown report.

## Run locally
    # once, with internet: download yolov8n.pt into backend/ (ultralytics does this on first use). After that it runs offline.
    cd backend && pip install -r requirements.txt && uvicorn main:app --reload      # API on :8000
    cd frontend && npm install && npm run dev                                       # UI on :5173
    # or: touch backend/yolov8n.pt is NOT enough, put the real weights there, then `docker compose up --build`

Tests: `cd backend && pytest`

## API
- `GET /api/health`
- `POST /api/analyze` (multipart: `file`, `corruption`, `levels`, `iou`, `seed`)
- `GET /api/runs/{id}` and `GET /api/runs/{id}/report`

## Method
A baseline detection counts as retained when a degraded detection has the same class and IoU >= threshold (greedy, highest
confidence first). Same position but another class = class change; no match = lost; unmatched new detection = spurious.
For rotation, baseline boxes are moved by the same transform as the image. Seeds make every run repeatable.
Retention is not accuracy: no ground-truth precision/recall yet.
