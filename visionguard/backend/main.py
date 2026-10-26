import base64, io, json, os, sqlite3, time, uuid
import cv2, numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from PIL import Image, ImageOps
from core import KINDS, compare, corrupt, report_md, warp_box

WEIGHTS = os.getenv("YOLO_WEIGHTS", "yolov8n.pt")
DB = os.getenv("DB_PATH", "data/visionguard.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)
db = sqlite3.connect(DB, check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created REAL, body TEXT)")

app = FastAPI(title="VisionGuard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_model = None


def model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(WEIGHTS)  # loads from disk; keep the .pt file in backend/ for offline use
    return _model


def detect(img):
    h, w = img.shape[:2]
    t = time.perf_counter()
    r = model()(img, verbose=False)[0]
    ms = (time.perf_counter() - t) * 1000
    dets = [{"label": r.names[int(c)], "conf": float(p), "box": [x1 / w, y1 / h, x2 / w, y2 / h]}
            for (x1, y1, x2, y2), p, c in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist())]
    return dets, ms


def data_uri(img):
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


@app.get("/api/health")
def health():
    return {"status": "ok", "weights": WEIGHTS, "corruptions": KINDS}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), corruption: str = Form("blur"),
                  levels: str = Form("0,0.2,0.4,0.6,0.8,1.0"), iou: float = Form(0.5), seed: int = Form(42)):
    if corruption not in KINDS:
        raise HTTPException(400, f"corruption must be one of {KINDS}")
    try:
        lv = sorted({max(0.0, min(1.0, float(x))) for x in levels.split(",")} | {0.0})
        pil = ImageOps.exif_transpose(Image.open(io.BytesIO(await file.read()))).convert("RGB")
    except Exception:
        raise HTTPException(400, "Upload a valid image (JPEG, PNG or WebP) and numeric severity levels.")
    pil.thumbnail((1280, 1280))
    img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    base, base_ms = detect(img)
    out = []
    for s in lv:
        alt_img, m = corrupt(img, corruption, s, seed)
        alt, ms = (base, base_ms) if s == 0 else detect(alt_img)
        ref = [dict(b, box=warp_box(b["box"], m, w, h)) for b in base] if m is not None else base
        out.append({"severity": s, "image": data_uri(alt_img), "detections": alt, "latency_ms": ms,
                    **compare(ref, alt, iou)})
    run = {"id": uuid.uuid4().hex[:10], "model": WEIGHTS,
           "config": {"corruption": corruption, "levels": lv, "iou": iou, "seed": seed, "filename": file.filename},
           "levels": out}
    db.execute("INSERT INTO runs VALUES (?,?,?)", (run["id"], time.time(), json.dumps(run)))
    db.commit()
    return run


def load(run_id):
    row = db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    return json.loads(row[0])


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return load(run_id)


@app.get("/api/runs/{run_id}/report", response_class=PlainTextResponse)
def report(run_id: str):
    return report_md(load(run_id))
