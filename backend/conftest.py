"""Root conftest for the VisionGuard backend test suite.

Adds the project root (parent of this file) and the visionguard_contracts
package to sys.path so that both ``visionguard`` and
``visionguard_contracts`` are importable without a pip install.
"""
import os
import sys
from pathlib import Path

# Prevent OpenBLAS/MKL thread buffer exhaustion on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# Project root: d:/Projects/VisionGuard/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# visionguard_contracts lives at <project_root>/visionguard_contracts/
# but the import path expected by the codebase is:
#   visionguard_contracts.visionguard.core.types
# which requires the *project root* (not the package dir) to be on sys.path.
for _p in [
    str(Path(__file__).resolve().parent),   # backend/
    str(_PROJECT_ROOT),                     # VisionGuard/ (contains visionguard_contracts/)
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass
