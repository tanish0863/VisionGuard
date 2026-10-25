"""VisionGuard backend package."""
import os

# Prevent OpenBLAS/MKL/OMP thread buffer exhaustion on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
