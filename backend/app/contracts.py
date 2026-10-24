import sys
from pathlib import Path


_CONTRACTS_ROOT = Path(__file__).resolve().parents[2] / "visionguard_contracts"
if not _CONTRACTS_ROOT.is_dir():
    raise ModuleNotFoundError(f"VisionGuard contracts not found at {_CONTRACTS_ROOT}")

if str(_CONTRACTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_CONTRACTS_ROOT))

# The path is added above; Pylance cannot infer dynamic sys.path updates.
from visionguard.core.types import (  # type: ignore[reportMissingImports]
    EvalConfig,
    EvaluationReport,
    RunStatus,
)

__all__ = ["EvalConfig", "EvaluationReport", "RunStatus"]
