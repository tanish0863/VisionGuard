"""Comprehensive Edge Case Test Suite for VisionGuard ML Engine.

Targets Phase 5 requirements:
5.1 Empty detections (clean/corrupted combinations, division-by-zero, null semantics)
5.2 Matching edge cases (identical, non-overlapping, boundary IoU, competing, duplicates)
5.3 Metric edge cases (all retained, none retained, all flips, conf deltas, manual pooled checks)
5.4 Corruption edge cases (min/max severity, RNG determinism, immutability, invalid shapes/kinds)
5.5 Pipeline edge cases (empty dataset, bad image, image limit, partial/failed status)
"""
from __future__ import annotations

import math
import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from visionguard.core.corruptions import apply as apply_corruption, CORRUPTION_PARAMS
from visionguard.core.matching import match, MatchRecord, _iou
from visionguard.core.metrics import (
    compute_metrics,
    compute_from_result,
    aggregate_condition,
    per_class_retention,
    per_severity_metrics,
)
from visionguard.core.model_adapter import FakeDetector
from visionguard.core.pipeline import evaluate_run, register_dataset, _DATASET_ROOTS
from visionguard_contracts.visionguard.core.types import (
    EvalConfig,
    CorruptionSpec,
    RunStatus,
    MetricSet,
)


def _box_pred(class_id: int, confidence: float, box: list[float], name: str = "obj") -> dict:
    return {
        "class_id": class_id,
        "class_name": name,
        "confidence": float(confidence),
        "bbox_xyxy": [float(x) for x in box],
    }


# =========================================================================
# 5.1 Empty Detections
# =========================================================================
class TestEmptyDetections:
    def test_both_empty(self):
        m = match([], [])
        assert len(m.matches) == 0
        assert m.unmatched_clean_indices == []
        assert m.unmatched_corrupted_indices == []
        
        metrics = compute_metrics(0, 0, [])
        assert metrics.n_clean == 0
        assert metrics.n_corrupted == 0
        assert metrics.n_matched == 0
        assert metrics.detection_retention is None
        assert "detection_retention" in metrics.unavailable
        assert metrics.mean_matched_iou is None
        assert "mean_matched_iou" in metrics.unavailable

    def test_clean_exists_corrupted_empty(self):
        clean = [_box_pred(1, 0.9, [0, 0, 50, 50])]
        m = match(clean, [])
        assert len(m.matches) == 0
        assert m.unmatched_clean_indices == [0]
        assert m.unmatched_corrupted_indices == []

        metrics = compute_metrics(1, 0, [])
        assert metrics.n_clean == 1
        assert metrics.n_corrupted == 0
        assert metrics.n_matched == 0
        assert metrics.detection_retention == 0.0
        assert metrics.mean_matched_iou is None
        assert "mean_matched_iou" in metrics.unavailable
        assert metrics.n_unmatched_clean == 1

    def test_clean_empty_corrupted_exists(self):
        corr = [_box_pred(1, 0.8, [0, 0, 50, 50])]
        m = match([], corr)
        assert len(m.matches) == 0
        assert m.unmatched_clean_indices == []
        assert m.unmatched_corrupted_indices == [0]

        metrics = compute_metrics(0, 1, [])
        assert metrics.n_clean == 0
        assert metrics.n_corrupted == 1
        assert metrics.n_matched == 0
        assert metrics.detection_retention is None
        assert "detection_retention" in metrics.unavailable
        assert metrics.n_unmatched_corrupted == 1


# =========================================================================
# 5.2 Matching Edge Cases
# =========================================================================
class TestMatchingEdgeCases:
    def test_identical_boxes(self):
        c = [_box_pred(1, 0.9, [10, 10, 50, 50])]
        k = [_box_pred(1, 0.85, [10, 10, 50, 50])]
        res = match(c, k, iou_threshold=0.5)
        assert len(res.matches) == 1
        assert res.matches[0].iou == 1.0
        assert not res.matches[0].class_flip
        assert res.matches[0].confidence_delta == pytest.approx(-0.05, abs=1e-4)

    def test_non_overlapping_boxes(self):
        c = [_box_pred(1, 0.9, [0, 0, 10, 10])]
        k = [_box_pred(1, 0.8, [100, 100, 110, 110])]
        res = match(c, k, iou_threshold=0.5)
        assert len(res.matches) == 0
        assert res.unmatched_clean_indices == [0]
        assert res.unmatched_corrupted_indices == [0]

    def test_iou_boundary_threshold(self):
        # A: [0, 0, 10, 10] area = 100
        # If B is [0, 0, 10, 15] area = 150, intersection = 100, union = 150 -> IoU = 0.6667
        # Let's set boxes with exact 0.5 IoU:
        # box A: [0, 0, 10, 20] area 200
        # box B: [0, 0, 10, 30] area 300, intersection [0,0,10,20] = 200, union = 300 -> IoU = 2/3 ≈ 0.667
        # box C: [0, 0, 10, 10] area 100
        # box D: [0, 0, 10, 19] area 190, inter 100, union 190 -> 100/190 = 0.526
        # Let's use exact coordinates:
        # A = [0, 0, 20, 10] area 200
        # B = [0, 0, 30, 10] area 300. intersection = [0,0,20,10] = 200. union = 200+300-200 = 300 -> IoU = 2/3
        # For exact 0.5: A = [0,0,10,10] area 100. B=[0,0,10,20] area 200. inter=100. union=200. IoU = 100/200 = 0.500000
        c = [_box_pred(1, 0.9, [0, 0, 10, 10])]
        k_exact = [_box_pred(1, 0.8, [0, 0, 10, 20])]
        res = match(c, k_exact, iou_threshold=0.5)
        assert len(res.matches) == 1
        assert res.matches[0].iou == 0.5

        # Just below 0.5: B=[0,0,10, 20.01] area 200.1, inter=100, union=200.1 -> IoU = 0.49975
        k_below = [_box_pred(1, 0.8, [0, 0, 10, 20.01])]
        res_below = match(c, k_below, iou_threshold=0.5)
        assert len(res_below.matches) == 0
        assert res_below.unmatched_clean_indices == [0]

    def test_competing_detections_optimal_assignment(self):
        # Two clean detections competing for one corrupted detection
        # clean 0 has IoU 0.9 with corrupted 0
        # clean 1 has IoU 0.6 with corrupted 0
        c = [
            _box_pred(1, 0.9, [0, 0, 10, 10]),     # high overlap
            _box_pred(1, 0.8, [0, 0, 10, 15]),     # lower overlap
        ]
        k = [_box_pred(1, 0.85, [0, 0, 10, 10])]  # identical to c[0]
        res = match(c, k, iou_threshold=0.5)
        assert len(res.matches) == 1
        assert res.matches[0].clean_index == 0
        assert res.matches[0].corrupted_index == 0
        assert res.unmatched_clean_indices == [1]

    def test_duplicate_boxes_in_predictions(self):
        c = [_box_pred(1, 0.9, [0, 0, 10, 10])]
        k = [
            _box_pred(1, 0.85, [0, 0, 10, 10]),
            _box_pred(1, 0.75, [0, 0, 10, 10]),
        ]
        res = match(c, k, iou_threshold=0.5)
        assert len(res.matches) == 1
        # Strictly one-to-one
        assert res.unmatched_corrupted_indices == [1]


# =========================================================================
# 5.3 Metric Edge Cases
# =========================================================================
class TestMetricEdgeCases:
    def test_all_retained_same_class(self):
        records = [
            MatchRecord(clean_index=0, corrupted_index=0, iou=0.9, confidence_delta=0.05, class_flip=False),
            MatchRecord(clean_index=1, corrupted_index=1, iou=0.85, confidence_delta=-0.05, class_flip=False),
        ]
        m = compute_metrics(2, 2, records)
        assert m.detection_retention == 1.0
        assert m.class_consistent_retention == 1.0
        assert m.class_flip_rate == 0.0
        assert m.mean_confidence_delta == 0.0

    def test_every_matched_changes_class(self):
        records = [
            MatchRecord(clean_index=0, corrupted_index=0, iou=0.9, confidence_delta=-0.1, class_flip=True),
            MatchRecord(clean_index=1, corrupted_index=1, iou=0.85, confidence_delta=-0.1, class_flip=True),
        ]
        m = compute_metrics(2, 2, records)
        assert m.detection_retention == 1.0
        assert m.class_consistent_retention == 0.0
        assert m.class_flip_rate == 1.0

    def test_manual_pooled_aggregation(self):
        # Image 1: 2 clean, 2 matched, 0 flips
        rec1 = [
            MatchRecord(clean_index=0, corrupted_index=0, iou=0.8, confidence_delta=0.1, class_flip=False),
            MatchRecord(clean_index=1, corrupted_index=1, iou=0.9, confidence_delta=0.1, class_flip=False),
        ]
        # Image 2: 4 clean, 1 matched, 1 flip
        rec2 = [
            MatchRecord(clean_index=0, corrupted_index=0, iou=0.7, confidence_delta=-0.2, class_flip=True),
        ]
        # Pool: Total clean = 6, total corrupted = 3, matched = 3, flips = 1
        per_img = [(2, 2, rec1), (4, 1, rec2)]
        pooled = aggregate_condition(per_img)
        assert pooled.n_clean == 6
        assert pooled.n_corrupted == 3
        assert pooled.n_matched == 3
        assert pooled.n_class_flips == 1
        assert pooled.detection_retention == pytest.approx(3 / 6, abs=1e-4)
        assert pooled.class_consistent_retention == pytest.approx((3 - 1) / 6, abs=1e-4)
        assert pooled.class_flip_rate == pytest.approx(1 / 3, abs=1e-4)
        assert pooled.mean_confidence_delta == pytest.approx((0.1 + 0.1 - 0.2) / 3, abs=1e-4)


# =========================================================================
# 5.4 Corruption Edge Cases
# =========================================================================
class TestCorruptionEdgeCases:
    @pytest.fixture
    def test_img(self):
        # Image with spatial gradients so blur produces distinct outputs across severities
        x = np.linspace(0, 255, 100, dtype=np.uint8)
        grid_x, grid_y = np.meshgrid(x, x)
        return np.stack([grid_x, grid_y, grid_x], axis=-1)

    def test_min_and_max_severities(self, test_img):
        for kind in ("blur", "low_light", "gaussian_noise"):
            s1 = apply_corruption(test_img, kind=kind, severity=1)
            s3 = apply_corruption(test_img, kind=kind, severity=3)
            assert s1.shape == test_img.shape
            assert s3.shape == test_img.shape
            assert not np.array_equal(s1, s3)

    def test_gaussian_noise_determinism(self, test_img):
        n1 = apply_corruption(test_img, kind="gaussian_noise", severity=2, seed=123)
        n2 = apply_corruption(test_img, kind="gaussian_noise", severity=2, seed=123)
        n3 = apply_corruption(test_img, kind="gaussian_noise", severity=2, seed=456)
        assert np.array_equal(n1, n2)
        assert not np.array_equal(n1, n3)

    def test_input_immutability(self, test_img):
        orig_copy = test_img.copy()
        _ = apply_corruption(test_img, kind="blur", severity=3)
        _ = apply_corruption(test_img, kind="low_light", severity=3)
        _ = apply_corruption(test_img, kind="gaussian_noise", severity=3)
        assert np.array_equal(test_img, orig_copy)

    def test_invalid_shape_or_type(self):
        gray = np.zeros((100, 100), dtype=np.uint8)
        with pytest.raises(ValueError, match="Expected H×W×3"):
            apply_corruption(gray, kind="blur", severity=1)

        float_img = np.zeros((100, 100, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="Expected uint8"):
            apply_corruption(float_img, kind="blur", severity=1)

    def test_invalid_severity_or_kind(self, test_img):
        with pytest.raises(ValueError, match="Invalid severity"):
            apply_corruption(test_img, kind="blur", severity=0)  # type: ignore

        with pytest.raises(ValueError, match="Invalid severity"):
            apply_corruption(test_img, kind="blur", severity=4)  # type: ignore

        with pytest.raises(ValueError, match="Unknown corruption kind"):
            apply_corruption(test_img, kind="fog", severity=1)  # type: ignore


# =========================================================================
# 5.5 Pipeline Edge Cases
# =========================================================================
class TestPipelineEdgeCases:
    def test_max_images_limit(self, tmp_path):
        # Create 5 images
        for i in range(5):
            img = np.full((50, 50, 3), 128, dtype=np.uint8)
            cv2.imwrite(str(tmp_path / f"img_{i}.png"), img)
        
        did = "test_max_images_ds"
        register_dataset(did, tmp_path)
        
        cfg = EvalConfig(
            model_id="fasterrcnn_resnet50_fpn",
            dataset_id=did,
            score_threshold=0.5,
            match_iou_threshold=0.5,
            corruptions=[CorruptionSpec(kind="blur", severities=[1])],
            max_images=2,
        )
        detector = FakeDetector([])
        rep = evaluate_run(cfg, detector=detector)
        assert rep.dataset.image_count == 2
        assert len(rep.clean_predictions) == 2

    def test_one_corrupted_file_among_valid_images_yields_partial_status(self, tmp_path):
        # Create 1 valid image and 1 corrupted file
        valid_img = np.full((50, 50, 3), 128, dtype=np.uint8)
        cv2.imwrite(str(tmp_path / "valid.png"), valid_img)
        (tmp_path / "corrupted.png").write_bytes(b"NOT_A_VALID_IMAGE_CONTENT")

        did = "test_partial_ds"
        register_dataset(did, tmp_path)

        cfg = EvalConfig(
            model_id="fasterrcnn_resnet50_fpn",
            dataset_id=did,
            score_threshold=0.5,
            match_iou_threshold=0.5,
            corruptions=[CorruptionSpec(kind="blur", severities=[1])],
        )
        detector = FakeDetector([_box_pred(1, 0.9, [0, 0, 10, 10])])
        rep = evaluate_run(cfg, detector=detector)
        assert rep.status == RunStatus.PARTIAL
        assert len(rep.errors) >= 1
        assert any("corrupted" in e.image_id for e in rep.errors)
