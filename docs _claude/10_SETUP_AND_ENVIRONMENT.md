# 10 — Setup and Environment Guide

| Field | Value |
| --- | --- |
| Version | 1.0 (Draft) · 24 Oct 2026 |
| Owner | Member 5 (TBC) |
| Stage | 2 |
| Sources | Master Plan §N; Architecture §3.3, §4.4, §5.5 |

> ⚠ **These commands have NOT been executed yet** — the repository does not exist. They are templates derived from the Master Plan runbook. The guide's requirement is *tested* commands, so every step below has a verification row in §14; **do not mark this document final until each row is signed off on a clean machine (including Windows).** Items in `<angle brackets>` must be replaced once chosen.

## 1. Supported platforms

| Item | Requirement |
| --- | --- |
| OS | Windows 10/11 (primary dev, PowerShell), Linux; macOS not a stated target |
| Python | `<pin, e.g. 3.x>` — pick one version supported by OpenCV, NumPy, the chosen detector and `pycocotools` on Windows; record in `.python-version` |
| Node.js | `<pin LTS version>`; record in `.nvmrc` |
| Git | Recent version; line endings: `core.autocrlf` set per team agreement |
| GPU/CPU | CPU must work (fallback). GPU optional; measure memory before concurrency (task M-1) |
| CUDA / PyTorch | If using GPU: install the PyTorch build matching your CUDA driver from the official selector; record versions in `pyproject.toml`/lock. `ALLOW_CPU_FALLBACK=true` permits one retry on CPU after CUDA OOM (recorded in the report) |
| Disk | Space for weights, sample data, `storage/` |
| Browser | Current Chrome/Edge/Firefox |

## 2. Clone

```bash
git clone <repository URL>
cd visionguard
git checkout <your-branch>     # chinmay | tanish | vanashree | aditya | documentation
```

## 3. Backend setup

```powershell
# Windows PowerShell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt        # or: pip install -e ".[dev]"  (choose ONE approach)
copy .env.example .env
```

```bash
# Linux
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 4. Environment variables

`backend/.env.example` (starting defaults from the Master Plan; validate against the chosen model/runtime):

```ini
APP_ENV=development
HOST=0.0.0.0
PORT=8000
STORAGE_DIR=./storage
ARTIFACT_DIR=./storage/runs
INDEX_DB=sqlite:///./storage/index.sqlite
MAX_UPLOAD_MB=10
MAX_IMAGE_PIXELS=20000000
MAX_IMAGES=200               # placeholder; set after measurement M-1
MAX_CONDITIONS=24            # placeholder
MODEL_ID=yolo-nano-default
MODEL_WEIGHTS_PATH=./weights/<weights filename>      # pinned
MODEL_WEIGHTS_SHA256=<hex>
ALLOW_CPU_FALLBACK=false
ENABLE_MOCK_MODEL=false      # true only for frontend dev/CI
CONFIDENCE_THRESHOLD=0.25
IOU_MATCH_THRESHOLD=0.50
CORS_ORIGINS=http://localhost:5173
```

Notes: Master Plan lists `DATABASE_URL` and `ARTIFACT_DIR`; the architecture makes the filesystem authoritative with SQLite only as an index, hence `STORAGE_DIR`/`INDEX_DB`. Variable names are `[PROPOSED]` — reconcile in code review. Never commit `.env`.

## 5. Model weights setup

1. Choose and pin the detector package + weights (ADR-05). Re-check current version docs at implementation time; do not assume NMS settings apply to NMS-free models.
2. Download weights once to `backend/weights/` (git-ignored) — **before the event**, never relying on venue Wi-Fi.
3. Compute and record the checksum: `python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" weights/<file>`; set `MODEL_WEIGHTS_SHA256`.
4. Startup refuses to run with a checksum mismatch (`MODEL_UNAVAILABLE`).
5. Licensing: Ultralytics YOLO is AGPL-3.0 (Enterprise licence for commercial closed use). Fine for the hackathon; revisit before any closed-source/SaaS plan.

## 6. Dataset setup

```
samples/
├── street_01/            # single/sample images with licence/source notes
├── tiny_coco.zip         # 3–10 images + annotations.json (COCO detection format)
└── SOURCES.md            # license/source for every sample file
```
Use small, legally usable images; verify licences; keep them offline. Images must be < `MAX_UPLOAD_MB`. A bundled sample powers the UI quick-start button.

## 7. Backend startup

```bash
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000     # module path TBC to match repo
```
Verify: open `http://localhost:8000/api/v1/health` → `status: ok`, `model_loaded: true`; docs at `http://localhost:8000/docs`.

**Important:** run exactly **one** Uvicorn process (no `--workers N`). The job state and loaded model live in-process. `--reload` is for development only; do not use it during the demo.

## 8. Frontend setup and startup

```bash
cd frontend
npm install            # or npm ci with a committed lockfile
npm run gen:api        # regenerate src/types/api.gen.ts from the running backend OpenAPI
npm run dev            # http://localhost:5173 ; /api proxied to :8000
```
Production-like: `npm run build` then serve `dist/` (or have Vite preview). Build must succeed before release.

## 9. CLI

```bash
cd backend
visionguard catalog
visionguard run --dataset ../samples/street_01 --model default --preset night_driving --out ../storage
echo $?      # PowerShell: $LASTEXITCODE   → 0 PASS, 1 FAIL, 2 ERROR/FAILED/PARTIAL, 64 usage
```

## 10. Running tests

```bash
cd backend && pytest -q                     # use ENABLE_MOCK_MODEL=true to avoid weights
cd frontend && npm run build && npm test    # tests if configured
```

## 11. Pre-demo checklist

1. Fresh clone + documented commands only.
2. `/api/v1/health` is OK, real (non-mock) model loaded.
3. Load sample → run prepared configuration → check history and report export.
4. Network off: still works.
5. `storage/` cleaned or seeded with a known-good run.

## 12. Optional: Docker Compose

Only if already tested by the team — do **not** introduce on the final day. Check upload persistence, artifact paths, CORS, memory limits and cold-start time.

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `model_loaded: false` / `MODEL_UNAVAILABLE` | Weights missing or checksum mismatch | Re-download; recompute SHA-256; check `MODEL_WEIGHTS_PATH` |
| CUDA out-of-memory | Large image/batch, other GPU use | Reduce `imgsz`; set `device=cpu`; `ALLOW_CPU_FALLBACK=true` (recorded) |
| CORS error in browser | Origin not in `CORS_ORIGINS` | Add `http://localhost:5173` |
| Frontend 404 on `/api` | Proxy not configured / backend down | Check Vite proxy and `:8000` |
| `pip` fails building `pycocotools` on Windows | Missing build tools / wheel | Use a prebuilt wheel/compatible package version; note chosen fix here |
| PowerShell cannot activate venv | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Runs stuck `RUNNING` after restart | Process killed mid-run | Startup marks them `FAILED/INTERRUPTED`; start a new run |
| Different results between runs | Runtime nondeterminism | Check clean-vs-clean control; same seed ⇒ same corrupted pixels |
| Overlays misaligned on phone photos | EXIF orientation | Confirm loader applies `exif_transpose` (TC-011) |
| Types out of date | Backend schema changed | `npm run gen:api` |
| Slow inference | CPU only / large images | Cap size; use nano model; precompute demo run |

## 14. Verification log (fill in when tested)

| Step | Tested by | OS | Date | Result |
| --- | --- | --- | --- | --- |
| Clone + backend venv install | | | | |
| Weights download + checksum | | | | |
| Backend startup + `/health` | | | | |
| Frontend install + dev | | | | |
| `gen:api` | | | | |
| `pytest` (mock) | | | | |
| Sample run end to end | | | | |
| CLI exit codes | | | | |
| Offline run | | | | |
