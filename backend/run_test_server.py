"""Launch local FastAPI server configured for E2E tests with isolated SQLite database."""
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

os.environ["TEST_DATABASE_URL"] = "sqlite:///D:/Projects/VisionGuard/scratch/test_e2e.db"
os.environ["VISIONGUARD_DISPATCHER"] = "background"

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, log_level="info")
