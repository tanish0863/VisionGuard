import importlib
import os
from collections.abc import Callable

from backend.app.contracts import EvaluationReport


def get_evaluator() -> Callable[..., EvaluationReport]:
    target = os.getenv(
        "VISIONGUARD_EVALUATOR", "backend.visionguard.core.pipeline:evaluate_run"
    )
    module_name, separator, function_name = target.partition(":")
    if not separator or not module_name or not function_name:
        raise RuntimeError(
            "VISIONGUARD_EVALUATOR must use the format 'module.path:evaluate_run'"
        )

    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise RuntimeError(
            f"Could not import the ML evaluation module '{module_name}'"
        ) from error

    evaluator = getattr(module, function_name, None)
    if not callable(evaluator):
        raise RuntimeError(
            f"ML evaluation entry point '{target}' is missing or not callable"
        )
    return evaluator
