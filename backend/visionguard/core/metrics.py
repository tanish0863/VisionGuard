"""VisionGuard – metrics.py

Metric computation for prediction-consistency evaluation.

This module produces ``MetricSet`` objects that are compatible with the
shared contract in ``visionguard_contracts/visionguard/core/types.py``.
That class is the authoritative implementation of the formulas; this module
delegates to it and adds aggregation helpers.

Core metrics
------------
Detection retention
    ``matched_clean / clean``  (None when clean == 0).
    Measures how many clean predictions survive under corruption.
    Uses the term *prediction consistency* – NOT accuracy; no ground truth
    is available.

Class-consistent retention
    ``(matched_clean - class_flips) / clean``

Mean matched IoU
    Mean IoU over all matched (clean, corrupted) pairs.

Mean confidence delta
    Mean of ``(corrupted_conf - clean_conf)`` over matched pairs.
    Negative = the model becomes less confident under corruption.

Class-flip rate
    ``class_flips / matched``

Unmatched clean / corrupted
    Counts of predictions with no counterpart.

Important edge cases
---------------------
- Zero clean detections → ``detection_retention`` and
  ``class_consistent_retention`` are **null** (not 0% or 100%).
  The ``unavailable`` dict carries the reason.
- Zero matched pairs → ``mean_matched_iou``, ``mean_confidence_delta``, and
  ``class_flip_rate`` are **null**.
- NaN is never returned; null (Python ``None``) is used instead.

Additional aggregation helpers (section 4.5)
--------------------------------------------
``aggregate_condition``   – Pool metrics from a list of per-image ``MatchResult``.
``per_class_retention``   – Retention per predicted class.
``per_severity_metrics``  – Returns a dict[severity → MetricSet].
"""
from __future__ import annotations

import sys
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from .matching import MatchRecord, MatchResult

if TYPE_CHECKING:
    pass

# ---- re-export the contracts type so callers can do `from metrics import MetricSet`
try:
    # When run from within the backend package
    from visionguard_contracts.visionguard.core.types import MetricSet  # type: ignore
except ModuleNotFoundError:
    # Lightweight fallback so this file is importable in isolation
    # (e.g. when the contracts package is not on PYTHONPATH).
    # In production, visionguard_contracts MUST be installed.
    MetricSet = None  # type: ignore


# --------------------------------------------------------------------------- #
# Core computation                                                              #
# --------------------------------------------------------------------------- #

def compute_metrics(
    n_clean: int,
    n_corrupted: int,
    matches: list[MatchRecord],
) -> dict:
    """Compute all core metrics from raw match data.

    This is a thin wrapper around ``MetricSet.from_matches`` that also
    works when the contracts package is unavailable by returning a plain dict.

    Parameters
    ----------
    n_clean:
        Number of detections on the clean image.
    n_corrupted:
        Number of detections on the corrupted image.
    matches:
        List of ``MatchRecord`` from ``matching.match()``.

    Returns
    -------
    MetricSet | dict
        A ``MetricSet`` when the contracts package is available,
        otherwise a plain dict with the same keys.
    """
    if MetricSet is not None:
        # Adapt our MatchRecord dataclass to the contracts MatchRecord if needed.
        contract_matches = _to_contract_matches(matches)
        return MetricSet.from_matches(n_clean, n_corrupted, contract_matches)

    # Fallback: compute manually (same formulas as contracts MetricSet.from_matches)
    return _compute_dict(n_clean, n_corrupted, matches)


def compute_from_result(
    n_clean: int,
    match_result: MatchResult,
    corrupted_predictions: list,
) -> dict:
    """Convenience wrapper: compute metrics directly from a ``MatchResult``.

    Parameters
    ----------
    n_clean:
        Number of clean detections for this image.
    match_result:
        Output of ``matching.match()``.
    corrupted_predictions:
        List of corrupted predictions (used to count n_corrupted).

    Returns
    -------
    MetricSet | dict
    """
    n_corrupted = len(corrupted_predictions)
    return compute_metrics(n_clean, n_corrupted, match_result.matches)


# --------------------------------------------------------------------------- #
# Aggregation helpers (section 4.5)                                            #
# --------------------------------------------------------------------------- #

def aggregate_condition(
    per_image_results: list[tuple[int, int, list[MatchRecord]]],
) -> dict:
    """Pool metrics across all images in one condition (micro-average).

    Parameters
    ----------
    per_image_results:
        List of ``(n_clean, n_corrupted, matches)`` tuples, one per image.

    Returns
    -------
    MetricSet | dict
        Pooled metrics over all images.

    Notes
    -----
    This is a micro-average: all matches from all images are pooled into a
    single list before computing ratios.  It is NOT an average of per-image
    ratios.
    """
    total_clean = 0
    total_corrupted = 0
    all_matches: list[MatchRecord] = []

    for n_clean, n_corrupted, matches in per_image_results:
        total_clean += n_clean
        total_corrupted += n_corrupted
        all_matches.extend(matches)

    return compute_metrics(total_clean, total_corrupted, all_matches)


def per_class_retention(
    clean_predictions: list[dict],
    matches: list[MatchRecord],
) -> dict[str, Optional[float]]:
    """Compute detection retention separately for each predicted class.

    Parameters
    ----------
    clean_predictions:
        Full list of clean predictions; each must have ``class_name`` and
        ``class_id``.
    matches:
        Matched pairs from ``matching.match()``.

    Returns
    -------
    dict[str, float | None]
        Maps class name → retention rate.  ``None`` when no clean detections
        exist for that class (should not happen in practice, but guard anyway).

    Notes
    -----
    Per-class retention uses the same definition as overall retention:
        class_retention = matched_for_class / clean_for_class
    A class-flip is NOT counted as a retained detection for the original class.
    """
    matched_ci = {m.clean_index for m in matches}
    # Only count non-flip matches as "retained with same class".
    retained_ci = {m.clean_index for m in matches if not m.class_flip}

    class_total: dict[str, int] = defaultdict(int)
    class_retained: dict[str, int] = defaultdict(int)

    for i, pred in enumerate(clean_predictions):
        cname = pred.get("class_name", str(pred.get("class_id", "?")))
        class_total[cname] += 1
        if i in retained_ci:
            class_retained[cname] += 1

    return {
        cname: (class_retained[cname] / total if total > 0 else None)
        for cname, total in class_total.items()
    }


def per_severity_metrics(
    severity_results: dict[int, list[tuple[int, int, list[MatchRecord]]]],
) -> dict[int, dict]:
    """Aggregate metrics per severity level.

    Parameters
    ----------
    severity_results:
        Maps severity (1, 2, or 3) → list of ``(n_clean, n_corrupted, matches)``
        tuples, one tuple per image.

    Returns
    -------
    dict[int, MetricSet | dict]
        Maps severity → pooled metrics.

    Example
    -------
    Report retention separately for blur severity 1, 2, and 3 to build a
    degradation curve::

        for severity, metrics in per_severity_metrics(results).items():
            print(f"severity={severity}  retention={metrics['detection_retention']}")
    """
    return {
        severity: aggregate_condition(image_results)
        for severity, image_results in severity_results.items()
    }


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #

def _to_contract_matches(matches: list[MatchRecord]):
    """Convert local MatchRecord dataclasses to contracts MatchRecord objects.

    If both happen to be the same class (e.g. imported from the same source),
    this is a no-op.
    """
    try:
        from visionguard_contracts.visionguard.core.types import (  # type: ignore
            MatchRecord as ContractMatchRecord,
        )
    except ModuleNotFoundError:
        return matches  # already compatible

    result = []
    for m in matches:
        if isinstance(m, ContractMatchRecord):
            result.append(m)
        else:
            result.append(
                ContractMatchRecord(
                    clean_index=m.clean_index,
                    corrupted_index=m.corrupted_index,
                    iou=m.iou,
                    confidence_delta=m.confidence_delta,
                    class_flip=m.class_flip,
                )
            )
    return result


def _compute_dict(
    n_clean: int,
    n_corrupted: int,
    matches: list[MatchRecord],
) -> dict:
    """Fallback metric computation that returns a plain dict.

    Implements identical formulas to ``MetricSet.from_matches``.
    """
    m = len(matches)
    flips = sum(1 for x in matches if x.class_flip)
    un: dict[str, str] = {}
    vals: dict[str, Optional[float]] = {}

    if n_clean == 0:
        for k in ("detection_retention", "class_consistent_retention"):
            vals[k] = None
            un[k] = "no clean detections"
    else:
        vals["detection_retention"] = round(m / n_clean, 4)
        vals["class_consistent_retention"] = round((m - flips) / n_clean, 4)

    if m == 0:
        for k in ("mean_matched_iou", "mean_confidence_delta", "class_flip_rate"):
            vals[k] = None
            un[k] = "no matched pairs"
    else:
        vals["mean_matched_iou"] = round(sum(x.iou for x in matches) / m, 4)
        vals["mean_confidence_delta"] = round(
            sum(x.confidence_delta for x in matches) / m, 4
        )
        vals["class_flip_rate"] = round(flips / m, 4)

    return {
        "n_clean": n_clean,
        "n_corrupted": n_corrupted,
        "n_matched": m,
        "n_class_flips": flips,
        "n_unmatched_clean": n_clean - m,
        "n_unmatched_corrupted": n_corrupted - m,
        "unavailable": un,
        **vals,
    }
