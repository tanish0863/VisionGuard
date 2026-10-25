"""Public entry point. STUB: returns the demo fixture until the real pipeline replaces the body.
The signature is the contract and must not change."""
from __future__ import annotations

from typing import Callable, Optional, Union
from uuid import uuid4

from .fixtures import build_fixture_report
from .types import EvalConfig, EvaluationReport

ProgressCallback = Callable[[int, int], None]  # (images_completed, images_total)


def evaluate_run(
    config: Union[EvalConfig, dict],
    *,
    run_id: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> EvaluationReport:
    """The backend owns run_id and passes it in. Raises pydantic.ValidationError on a bad config.
    Never raises for per-image problems: those become report.errors and status PARTIAL."""
    EvalConfig.model_validate(config if isinstance(config, dict) else config.model_dump())
    report = build_fixture_report()  # STUB: ignores the config's contents
    total = len(report.clean_predictions)
    if progress_callback:
        for done in range(1, total + 1):
            progress_callback(done, total)
    return report.model_copy(update={"run_id": run_id or f"stub-{uuid4().hex[:8]}"})
