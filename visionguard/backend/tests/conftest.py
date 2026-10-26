"""Shared test setup for VisionGuard.

Run tests from backend/ with: python -m pytest tests -v
The test database is isolated from the development database.
"""
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Never let API tests write to the normal development database.
os.environ["DB_PATH"] = str(
    Path(tempfile.gettempdir()) / f"visionguard_pytest_{os.getpid()}.db"
)
