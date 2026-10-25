"""VisionGuard – matching.py

One-to-one matching between clean and corrupted detections.

Algorithm
---------
1. Compute an IoU matrix between every clean prediction and every corrupted
   prediction.

2. Class-aware pass:
   Build a cost matrix restricted to (clean, corrupted) pairs that share the
   SAME class.  Use ``scipy.optimize.linear_sum_assignment`` (minimum-cost
   bipartite matching) with cost = 1 - IoU.  Reject any assignment whose IoU
   is below ``iou_threshold``.

3. Class-agnostic pass:
   For the predictions that remain unmatched after step 2, repeat the
   assignment WITHOUT any class constraint.  Assignments accepted here with a
   class change are flagged as ``class_flip = True``.

4. Build ``MatchResult``:
   - ``matches``                  – list of ``MatchRecord`` (one per accepted pair)
   - ``unmatched_clean_indices``  – clean predictions with no counterpart
   - ``unmatched_corrupted_indices`` – corrupted predictions with no counterpart

Guarantees
----------
- Every prediction index appears in AT MOST ONE match (one-to-one).
- An index that is matched is NEVER in the unmatched list.
- ``matches + unmatched_clean == all clean indices``
- ``matches + unmatched_corrupted == all corrupted indices``

References
----------
- SciPy linear_sum_assignment:
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html
- Hendrycks & Dietterich robustness benchmark:
  https://github.com/hendrycks/robustness
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

# --------------------------------------------------------------------------- #
# Types (mirrors visionguard_contracts/visionguard/core/types.py)              #
# --------------------------------------------------------------------------- #

PredictionDict = dict  # class_id, class_name, confidence, bbox_xyxy


@dataclass
class MatchRecord:
    """One accepted clean↔corrupted pair."""
    clean_index: int         # index into the clean predictions list
    corrupted_index: int     # index into the corrupted predictions list
    iou: float               # IoU of the matched boxes, rounded to 4 dp
    confidence_delta: float  # corrupted.confidence - clean.confidence
    class_flip: bool         # True when class labels differ


@dataclass
class MatchResult:
    """Complete matching result for one (image, condition) pair."""
    matches: list[MatchRecord] = field(default_factory=list)
    unmatched_clean_indices: list[int] = field(default_factory=list)
    unmatched_corrupted_indices: list[int] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Public entry point                                                            #
# --------------------------------------------------------------------------- #

def match(
    clean: list[PredictionDict],
    corrupted: list[PredictionDict],
    *,
    iou_threshold: float = 0.5,
) -> MatchResult:
    """Match clean detections to corrupted detections.

    Parameters
    ----------
    clean:
        Predictions on the un-corrupted image.  Each dict must have keys:
        ``class_id`` (int), ``confidence`` (float), ``bbox_xyxy`` (list[float]).
    corrupted:
        Predictions on the corrupted image (same keys as above).
    iou_threshold:
        Minimum IoU for a match to be accepted.  Must be > 0.  Default 0.5.

    Returns
    -------
    MatchResult
        Contains ``matches``, ``unmatched_clean_indices``, and
        ``unmatched_corrupted_indices``.
    """
    if iou_threshold <= 0 or iou_threshold > 1:
        raise ValueError(f"iou_threshold must be in (0, 1], got {iou_threshold}")

    result = MatchResult()

    if not clean or not corrupted:
        result.unmatched_clean_indices = list(range(len(clean)))
        result.unmatched_corrupted_indices = list(range(len(corrupted)))
        return result

    iou_matrix = _compute_iou_matrix(clean, corrupted)

    unmatched_c = set(range(len(clean)))
    unmatched_k = set(range(len(corrupted)))

    # ------------------------------------------------------------------ #
    # Pass 1: class-aware matching                                         #
    # ------------------------------------------------------------------ #
    matched_c, matched_k = _run_assignment(
        clean, corrupted, iou_matrix,
        candidate_pairs=_same_class_pairs(clean, corrupted),
        iou_threshold=iou_threshold,
        result=result,
        class_flip=False,
    )
    unmatched_c -= matched_c
    unmatched_k -= matched_k

    # ------------------------------------------------------------------ #
    # Pass 2: class-agnostic matching on remaining predictions            #
    # ------------------------------------------------------------------ #
    if unmatched_c and unmatched_k:
        # Restrict IoU matrix to the remaining indices.
        remaining_pairs = {
            (ci, ki)
            for ci in unmatched_c
            for ki in unmatched_k
        }
        matched_c2, matched_k2 = _run_assignment(
            clean, corrupted, iou_matrix,
            candidate_pairs=remaining_pairs,
            iou_threshold=iou_threshold,
            result=result,
            class_flip=True,   # class_flip determined per-pair inside
        )
        unmatched_c -= matched_c2
        unmatched_k -= matched_k2

    result.unmatched_clean_indices = sorted(unmatched_c)
    result.unmatched_corrupted_indices = sorted(unmatched_k)
    return result


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #

def _compute_iou_matrix(
    clean: list[PredictionDict],
    corrupted: list[PredictionDict],
) -> np.ndarray:
    """Return an (n_clean × n_corrupted) float64 IoU matrix."""
    n, m = len(clean), len(corrupted)
    matrix = np.zeros((n, m), dtype=np.float64)
    for i, cp in enumerate(clean):
        for j, kp in enumerate(corrupted):
            matrix[i, j] = _iou(cp["bbox_xyxy"], kp["bbox_xyxy"])
    return matrix


def _iou(a: list[float], b: list[float]) -> float:
    """Compute IoU between two boxes in [x1, y1, x2, y2] format."""
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih

    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0.0 else 0.0


def _same_class_pairs(
    clean: list[PredictionDict],
    corrupted: list[PredictionDict],
) -> set[tuple[int, int]]:
    """Return all (i, j) pairs where clean[i] and corrupted[j] share a class."""
    pairs: set[tuple[int, int]] = set()
    for i, cp in enumerate(clean):
        for j, kp in enumerate(corrupted):
            if cp["class_id"] == kp["class_id"]:
                pairs.add((i, j))
    return pairs


def _run_assignment(
    clean: list[PredictionDict],
    corrupted: list[PredictionDict],
    iou_matrix: np.ndarray,
    candidate_pairs: set[tuple[int, int]],
    iou_threshold: float,
    result: MatchResult,
    *,
    class_flip: bool,  # unused hint; actual flip is always computed per-pair
) -> tuple[set[int], set[int]]:
    """Run linear_sum_assignment on the given candidate pairs.

    Non-candidate cells in the cost matrix are assigned a sentinel value of
    **2.0**, which is strictly above the maximum possible real cost (1.0,
    achieved when IoU = 0).  This guarantees the solver never prefers a
    non-candidate cell over any real candidate, even when IoU = 0.

    After the solver returns, pairs are accepted only if their IoU is at or
    above ``iou_threshold``.  Pairs below the threshold are left unmatched;
    they do NOT consume a slot in either set.

    Returns
    -------
    (matched_clean_indices, matched_corrupted_indices)
        Indices of predictions that were actually accepted (IoU >= threshold).
        An index that appears here will NOT appear in either unmatched list.
    """
    if not candidate_pairs:
        return set(), set()

    clean_indices = sorted({ci for ci, _ in candidate_pairs})
    corrupted_indices = sorted({ki for _, ki in candidate_pairs})

    ci_pos = {ci: pos for pos, ci in enumerate(clean_indices)}
    ki_pos = {ki: pos for pos, ki in enumerate(corrupted_indices)}

    # Non-candidate sentinel: 2.0 > max real cost (1.0 when IoU=0).
    # This prevents the solver from ever preferring a non-candidate cell.
    rows = len(clean_indices)
    cols = len(corrupted_indices)
    cost = np.full((rows, cols), fill_value=2.0, dtype=np.float64)

    for ci, ki in candidate_pairs:
        iou_val = iou_matrix[ci, ki]
        cost[ci_pos[ci], ki_pos[ki]] = 1.0 - iou_val  # cost in [0, 1]

    row_ind, col_ind = linear_sum_assignment(cost)

    matched_c: set[int] = set()
    matched_k: set[int] = set()

    for r, c in zip(row_ind, col_ind):
        ci = clean_indices[r]
        ki = corrupted_indices[c]

        # The solver may still return a non-candidate cell (sentinel) when
        # the matrix is non-square and all real options are exhausted.
        # Guard explicitly.
        if (ci, ki) not in candidate_pairs:
            continue

        iou_val = iou_matrix[ci, ki]

        # Reject pairs below the IoU threshold; they are left unmatched.
        if iou_val < iou_threshold:
            continue

        cp = clean[ci]
        kp = corrupted[ki]
        actual_flip = cp["class_id"] != kp["class_id"]

        result.matches.append(
            MatchRecord(
                clean_index=ci,
                corrupted_index=ki,
                iou=round(iou_val, 4),
                confidence_delta=round(kp["confidence"] - cp["confidence"], 4),
                class_flip=actual_flip,
            )
        )
        matched_c.add(ci)
        matched_k.add(ki)

    return matched_c, matched_k
