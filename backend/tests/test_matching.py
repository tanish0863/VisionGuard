"""Explicit verification tests for visionguard/core/matching.py.

Each test targets a specific behavioural guarantee:

1. One-to-one guarantee  – two overlapping objects cannot share a match.
2. Class-flip detection  – a different-class prediction with sufficient IoU
                           is identified as a class flip (not left unmatched).
3. Low-IoU rejection     – a pair below the threshold remains unmatched.
4. Partition guarantee   – every prediction index appears in exactly one of
                           {matched} or {unmatched_*}.

Additional edge-case tests:
5. Sentinel cost regression – non-candidate cells (cost=2.0) never chosen
                              when a real candidate exists, even if IoU=0.
6. Empty inputs             – no crash; everything goes to unmatched.
7. Asymmetric list sizes    – more clean than corrupted, and vice versa.

Run from the backend directory:
    pytest tests/test_matching.py -v
"""
from __future__ import annotations

import sys
import os

# Allow running from any directory
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import pytest
from visionguard.core.matching import MatchRecord, MatchResult, match, _iou


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

def _pred(class_id: int, confidence: float, box: list) -> dict:
    return {
        "class_id": class_id,
        "class_name": f"cls{class_id}",
        "confidence": float(confidence),
        "bbox_xyxy": list(map(float, box)),
    }


def _clean_index_set(result: MatchResult) -> set[int]:
    return {m.clean_index for m in result.matches} | set(result.unmatched_clean_indices)


def _corrupted_index_set(result: MatchResult) -> set[int]:
    return {m.corrupted_index for m in result.matches} | set(result.unmatched_corrupted_indices)


# --------------------------------------------------------------------------- #
# 1. One-to-one guarantee                                                       #
# --------------------------------------------------------------------------- #

class TestOneToOne:
    """Two overlapping objects must not share a single match.

    Layout:
        clean[0] A  = [0..100, 0..100]
        clean[1] B  = [150..250, 0..100]   (no overlap with A)

        corrupted[0] X = [10..110, 10..110]  high IoU with A, none with B
        corrupted[1] Y = [160..260, 10..110] high IoU with B, none with A
    """

    BOX_A = [0.0, 0.0, 100.0, 100.0]
    BOX_B = [150.0, 0.0, 250.0, 100.0]
    BOX_X = [10.0, 10.0, 110.0, 110.0]
    BOX_Y = [160.0, 10.0, 260.0, 110.0]

    def test_each_clean_index_at_most_once(self):
        clean     = [_pred(0, 0.9, self.BOX_A), _pred(0, 0.85, self.BOX_B)]
        corrupted = [_pred(0, 0.88, self.BOX_X), _pred(0, 0.82, self.BOX_Y)]
        result = match(clean, corrupted, iou_threshold=0.5)

        ci_list = [m.clean_index for m in result.matches]
        assert len(set(ci_list)) == len(ci_list), \
            "A clean index appeared in more than one match"

    def test_each_corrupted_index_at_most_once(self):
        clean     = [_pred(0, 0.9, self.BOX_A), _pred(0, 0.85, self.BOX_B)]
        corrupted = [_pred(0, 0.88, self.BOX_X), _pred(0, 0.82, self.BOX_Y)]
        result = match(clean, corrupted, iou_threshold=0.5)

        ki_list = [m.corrupted_index for m in result.matches]
        assert len(set(ki_list)) == len(ki_list), \
            "A corrupted index appeared in more than one match"

    def test_both_objects_matched(self):
        clean     = [_pred(0, 0.9, self.BOX_A), _pred(0, 0.85, self.BOX_B)]
        corrupted = [_pred(0, 0.88, self.BOX_X), _pred(0, 0.82, self.BOX_Y)]
        result = match(clean, corrupted, iou_threshold=0.5)

        assert len(result.matches) == 2, \
            f"Expected 2 matches, got {len(result.matches)}"
        assert result.unmatched_clean_indices == []
        assert result.unmatched_corrupted_indices == []

    def test_correct_spatial_pairing(self):
        """A→X and B→Y, not A→Y or B→X."""
        clean     = [_pred(0, 0.9, self.BOX_A), _pred(0, 0.85, self.BOX_B)]
        corrupted = [_pred(0, 0.88, self.BOX_X), _pred(0, 0.82, self.BOX_Y)]
        result = match(clean, corrupted, iou_threshold=0.5)

        pairs = {(m.clean_index, m.corrupted_index) for m in result.matches}
        assert (0, 0) in pairs, "clean[0] (A) must match corrupted[0] (X)"
        assert (1, 1) in pairs, "clean[1] (B) must match corrupted[1] (Y)"


# --------------------------------------------------------------------------- #
# 2. Class-flip detection                                                       #
# --------------------------------------------------------------------------- #

class TestClassFlip:
    """A different-class prediction with sufficient IoU is a class flip.

    clean[0]     = class 0 (dog), box [0..100, 0..100]
    corrupted[0] = class 1 (cat), box [10..110, 10..110]  IoU ≈ 0.67
    """

    BOX_CLEAN = [0.0, 0.0, 100.0, 100.0]
    BOX_CORR  = [10.0, 10.0, 110.0, 110.0]

    def test_precondition_iou_above_threshold(self):
        iou = _iou(self.BOX_CLEAN, self.BOX_CORR)
        assert iou >= 0.5, f"Precondition failed: IoU={iou:.4f} must be >= 0.5"

    def test_cross_class_high_iou_is_matched(self):
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(1, 0.8, self.BOX_CORR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert len(result.matches) == 1, \
            "A cross-class pair above IoU threshold must be matched (class flip)"
        assert result.unmatched_clean_indices == []
        assert result.unmatched_corrupted_indices == []

    def test_class_flip_flag_true(self):
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(1, 0.8, self.BOX_CORR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert result.matches[0].class_flip is True

    def test_same_class_flag_false(self):
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(0, 0.85, self.BOX_CORR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert result.matches[0].class_flip is False

    def test_cross_class_goes_through_pass2(self):
        """When no same-class partner exists the cross-class partner must still match."""
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(99, 0.75, self.BOX_CORR)]   # entirely different class

        result = match(clean, corrupted, iou_threshold=0.5)

        assert len(result.matches) == 1
        assert result.matches[0].class_flip is True

    def test_confidence_delta_correct(self):
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(0, 0.6, self.BOX_CORR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        expected_delta = round(0.6 - 0.9, 4)
        assert abs(result.matches[0].confidence_delta - expected_delta) < 1e-6


# --------------------------------------------------------------------------- #
# 3. Low-IoU rejection                                                          #
# --------------------------------------------------------------------------- #

class TestLowIoURejection:
    """A pair below the IoU threshold must remain unmatched.

    clean[0]     = [0..100, 0..100]
    corrupted[0] = [95..195, 95..195]   barely touching corner  IoU ≈ 0.003
    """

    BOX_CLEAN = [0.0, 0.0, 100.0, 100.0]
    BOX_CORR  = [95.0, 95.0, 195.0, 195.0]

    def test_precondition_iou_below_threshold(self):
        iou = _iou(self.BOX_CLEAN, self.BOX_CORR)
        assert iou < 0.5, f"Precondition failed: IoU={iou:.4f} must be < 0.5"

    def test_no_match_produced(self):
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(0, 0.8, self.BOX_CORR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert result.matches == [], \
            "A pair with IoU below threshold must not be matched"

    def test_both_go_to_unmatched(self):
        clean     = [_pred(0, 0.9, self.BOX_CLEAN)]
        corrupted = [_pred(0, 0.8, self.BOX_CORR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert 0 in result.unmatched_clean_indices
        assert 0 in result.unmatched_corrupted_indices

    def test_exact_threshold_accepted(self):
        """A pair whose IoU equals iou_threshold exactly is accepted (>= not >)."""
        box_a = [0.0, 0.0, 3.0, 3.0]
        box_b = [2.0, 0.0, 5.0, 3.0]
        iou_val = _iou(box_a, box_b)
        assert iou_val > 0, "Precondition: boxes must overlap"

        clean     = [_pred(0, 0.9, box_a)]
        corrupted = [_pred(0, 0.8, box_b)]

        result = match(clean, corrupted, iou_threshold=iou_val)

        assert len(result.matches) == 1, \
            "A pair at exactly iou_threshold must be accepted"

    def test_just_below_threshold_rejected(self):
        box_a = [0.0, 0.0, 3.0, 3.0]
        box_b = [2.0, 0.0, 5.0, 3.0]
        iou_val = _iou(box_a, box_b)

        clean     = [_pred(0, 0.9, box_a)]
        corrupted = [_pred(0, 0.8, box_b)]

        result = match(clean, corrupted, iou_threshold=iou_val + 1e-9)

        assert result.matches == [], \
            "A pair just below iou_threshold must be rejected"

    def test_zero_iou_always_rejected(self):
        """Non-overlapping boxes with IoU=0 must always be unmatched."""
        box_a = [0.0, 0.0, 10.0, 10.0]
        box_b = [500.0, 500.0, 510.0, 510.0]
        assert _iou(box_a, box_b) == 0.0

        clean     = [_pred(0, 0.9, box_a)]
        corrupted = [_pred(0, 0.8, box_b)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert result.matches == []
        assert 0 in result.unmatched_clean_indices
        assert 0 in result.unmatched_corrupted_indices


# --------------------------------------------------------------------------- #
# 4. Partition guarantee                                                         #
# --------------------------------------------------------------------------- #

class TestPartitionGuarantee:
    """Every index appears in exactly one category.

    Mixed scenario:
        clean[0]  class 0  box A  → should match corrupted[0] (same class, high IoU)
        clean[1]  class 0  box B  → should match corrupted[1] (class flip, high IoU)
        clean[2]  class 1  box C  → no spatial match → unmatched clean

        corrupted[0]  class 0  box A'  → matches clean[0]
        corrupted[1]  class 2  box B'  → class-flip matches clean[1]
        corrupted[2]  class 3  box D   → no spatial match → unmatched corrupted
    """

    BOX_A = [0.0,   0.0,  100.0, 100.0]
    BOX_B = [200.0, 0.0,  300.0, 100.0]
    BOX_C = [400.0, 0.0,  500.0, 100.0]
    BOX_A2 = [10.0,  10.0, 110.0, 110.0]
    BOX_B2 = [210.0, 10.0, 310.0, 110.0]
    BOX_D  = [700.0, 700.0, 800.0, 800.0]

    def _run(self):
        clean = [
            _pred(0, 0.9,  self.BOX_A),
            _pred(0, 0.85, self.BOX_B),
            _pred(1, 0.8,  self.BOX_C),
        ]
        corrupted = [
            _pred(0, 0.88, self.BOX_A2),
            _pred(2, 0.75, self.BOX_B2),
            _pred(3, 0.6,  self.BOX_D),
        ]
        return match(clean, corrupted, iou_threshold=0.5)

    def test_clean_partition_disjoint(self):
        result = self._run()
        matched = {m.clean_index for m in result.matches}
        unmatched = set(result.unmatched_clean_indices)
        assert matched & unmatched == set(), \
            f"Indices appear in both matched and unmatched (clean): {matched & unmatched}"

    def test_clean_partition_complete(self):
        result = self._run()
        all_ci = _clean_index_set(result)
        assert all_ci == {0, 1, 2}, \
            f"Not all clean indices accounted for: {all_ci}"

    def test_corrupted_partition_disjoint(self):
        result = self._run()
        matched = {m.corrupted_index for m in result.matches}
        unmatched = set(result.unmatched_corrupted_indices)
        assert matched & unmatched == set(), \
            f"Indices appear in both matched and unmatched (corrupted): {matched & unmatched}"

    def test_corrupted_partition_complete(self):
        result = self._run()
        all_ki = _corrupted_index_set(result)
        assert all_ki == {0, 1, 2}, \
            f"Not all corrupted indices accounted for: {all_ki}"

    def test_no_duplicate_in_matches(self):
        result = self._run()
        ci_list = [m.clean_index for m in result.matches]
        ki_list = [m.corrupted_index for m in result.matches]
        assert len(set(ci_list)) == len(ci_list), "Duplicate clean index in matches"
        assert len(set(ki_list)) == len(ki_list), "Duplicate corrupted index in matches"

    def test_expected_outcome(self):
        result = self._run()
        pairs = {(m.clean_index, m.corrupted_index) for m in result.matches}
        assert (0, 0) in pairs, "clean[0] ↔ corrupted[0] expected"
        assert (1, 1) in pairs, "clean[1] ↔ corrupted[1] expected (class flip)"
        assert 2 in result.unmatched_clean_indices
        assert 2 in result.unmatched_corrupted_indices

        flip_m = next(m for m in result.matches if m.clean_index == 1)
        assert flip_m.class_flip is True


# --------------------------------------------------------------------------- #
# 5. Sentinel cost regression                                                   #
# --------------------------------------------------------------------------- #

class TestSentinelCost:
    """Non-candidate cells must never win over any real candidate.

    If non-candidate cells used cost=1.0 (same as IoU=0 candidate),
    the solver could arbitrarily pick either.  With sentinel=2.0,
    any real candidate is always preferred.
    """

    def test_zero_iou_candidate_preferred_over_non_candidate(self):
        """
        Pass 1 sees (clean[0], corrupted[0]) as a same-class candidate with IoU=0.
        cost for that cell = 1.0.  Non-candidate cells have sentinel 2.0.
        Solver picks the real candidate; IoU<threshold so pair is rejected.
        Both end up unmatched — not consumed by a silent sentinel pick.
        """
        clean     = [_pred(0, 0.9, [0.0,   0.0,  10.0,  10.0])]
        corrupted = [
            _pred(0, 0.8, [500.0, 500.0, 510.0, 510.0]),  # class 0, no overlap
            _pred(1, 0.7, [600.0, 600.0, 610.0, 610.0]),  # class 1, no overlap
        ]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert result.matches == []
        assert 0 in result.unmatched_clean_indices
        assert 0 in result.unmatched_corrupted_indices
        assert 1 in result.unmatched_corrupted_indices

    def test_best_iou_wins_among_candidates(self):
        """
        clean[0] class=0 has two same-class candidates:
            corrupted[0]  IoU≈0.67  cost≈0.33  ← should win
            corrupted[1]  IoU=0     cost=1.0
        Solver must pick corrupted[0].
        """
        box_c   = [0.0, 0.0, 100.0, 100.0]
        box_hi  = [10.0, 10.0, 110.0, 110.0]
        box_far = [500.0, 500.0, 600.0, 600.0]

        assert _iou(box_c, box_hi) >= 0.5, "Precondition"
        assert _iou(box_c, box_far) == 0.0

        clean     = [_pred(0, 0.9, box_c)]
        corrupted = [_pred(0, 0.8, box_hi), _pred(0, 0.7, box_far)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert len(result.matches) == 1
        assert result.matches[0].corrupted_index == 0, \
            "Must match the high-IoU corrupted box (corrupted[0]), not the zero-IoU one"
        assert 1 in result.unmatched_corrupted_indices


# --------------------------------------------------------------------------- #
# 6. Empty inputs                                                               #
# --------------------------------------------------------------------------- #

class TestEmptyInputs:

    def test_empty_clean(self):
        result = match([], [_pred(0, 0.9, [0.0, 0.0, 10.0, 10.0])])
        assert result.matches == []
        assert result.unmatched_clean_indices == []
        assert result.unmatched_corrupted_indices == [0]

    def test_empty_corrupted(self):
        result = match([_pred(0, 0.9, [0.0, 0.0, 10.0, 10.0])], [])
        assert result.matches == []
        assert result.unmatched_clean_indices == [0]
        assert result.unmatched_corrupted_indices == []

    def test_both_empty(self):
        result = match([], [])
        assert result.matches == []
        assert result.unmatched_clean_indices == []
        assert result.unmatched_corrupted_indices == []


# --------------------------------------------------------------------------- #
# 7. Asymmetric list sizes                                                      #
# --------------------------------------------------------------------------- #

class TestAsymmetricLists:

    BOX      = [0.0, 0.0, 100.0, 100.0]
    BOX_NEAR = [5.0, 5.0, 105.0, 105.0]
    BOX_FAR  = [400.0, 400.0, 500.0, 500.0]

    def test_more_clean_than_corrupted_partition(self):
        clean = [
            _pred(0, 0.9, self.BOX),      # matches corrupted[0]
            _pred(0, 0.8, self.BOX_FAR),  # no match
        ]
        corrupted = [_pred(0, 0.85, self.BOX_NEAR)]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert len(result.matches) == 1
        assert result.matches[0].clean_index == 0
        assert 1 in result.unmatched_clean_indices
        assert result.unmatched_corrupted_indices == []
        assert _clean_index_set(result) == {0, 1}
        assert _corrupted_index_set(result) == {0}

    def test_more_corrupted_than_clean_partition(self):
        clean = [_pred(0, 0.9, self.BOX)]
        corrupted = [
            _pred(0, 0.85, self.BOX_NEAR),  # matches clean[0]
            _pred(0, 0.7,  self.BOX_FAR),   # no match
        ]

        result = match(clean, corrupted, iou_threshold=0.5)

        assert len(result.matches) == 1
        assert result.matches[0].corrupted_index == 0
        assert 1 in result.unmatched_corrupted_indices
        assert result.unmatched_clean_indices == []
        assert _clean_index_set(result) == {0}
        assert _corrupted_index_set(result) == {0, 1}
