"""Pipeline integration tests – visionguard/core/pipeline.py.

All tests use ``FakeDetector`` so torch/torchvision are NOT required.
A temporary directory with synthetic PNG images is created per test session.

Coverage
--------
1. COMPLETED run – no errors, report validates against the contracts schema.
2. PARTIAL run   – one image load fails; report status = PARTIAL.
3. FAILED run    – all images fail; report status = FAILED.
4. Progress callback receives correct (completed, total) pairs.
5. Bad config raises pydantic.ValidationError immediately.
6. Unregistered dataset raises FileNotFoundError.
7. Condition metrics pool correctly across images (micro-average).
8. Failure records are generated for missing / new / class-flip detections.
9. No prediction shares more than one slot in matches + unmatched.

Run from the backend directory:
    pytest tests/test_pipeline.py -v
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import numpy as np
import pytest

from visionguard_contracts.visionguard.core.types import (
    EvaluationReport, RunStatus, FailureType,
)
from visionguard.core.model_adapter import FakeDetector
from visionguard.core.pipeline import evaluate_run, register_dataset, _DATASET_ROOTS

# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def image_dir(tmp_path_factory) -> Path:
    """Create a temporary directory with three 100×100 RGB PNG images."""
    import cv2
    root = tmp_path_factory.mktemp("images")
    for name in ("img_a", "img_b", "img_c"):
        img = np.full((100, 100, 3), fill_value=128, dtype=np.uint8)
        cv2.imwrite(str(root / f"{name}.png"), img)
    return root


@pytest.fixture(scope="session")
def dataset_id(image_dir) -> str:
    did = "test_dataset_pipeline"
    register_dataset(did, image_dir)
    return did


@pytest.fixture
def base_config(dataset_id) -> dict:
    return {
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": dataset_id,
        "corruptions": [{"kind": "blur", "severities": [1]}],
        "seed": 0,
        "score_threshold": 0.5,
        "match_iou_threshold": 0.5,
    }


# Two predictions that overlap well (IoU ≈ 0.67) – used as the "surviving" pair.
_CLEAN_PRED = {
    "class_id": 0, "class_name": "person",
    "confidence": 0.9, "bbox_xyxy": [0.0, 0.0, 80.0, 80.0],
}
_CORR_PRED_SAME = {
    "class_id": 0, "class_name": "person",
    "confidence": 0.85, "bbox_xyxy": [5.0, 5.0, 85.0, 85.0],
}
_CORR_PRED_FLIP = {
    "class_id": 1, "class_name": "bicycle",
    "confidence": 0.80, "bbox_xyxy": [5.0, 5.0, 85.0, 85.0],
}
_CORR_PRED_EXTRA = {
    "class_id": 2, "class_name": "car",
    "confidence": 0.75, "bbox_xyxy": [50.0, 50.0, 99.0, 99.0],
}


# --------------------------------------------------------------------------- #
# 1. COMPLETED run                                                              #
# --------------------------------------------------------------------------- #

class TestCompletedRun:

    def test_status_is_completed(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert report.status == RunStatus.COMPLETED

    def test_no_errors(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert report.errors == []

    def test_report_validates_schema(self, base_config):
        """Round-trip through Pydantic to confirm the report is contract-valid."""
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        # Re-validate from dict (mirrors what the API does before sending JSON).
        EvaluationReport.model_validate(report.model_dump())

    def test_clean_predictions_cached(self, base_config, image_dir):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        # One entry per image in the directory.
        assert len(report.clean_predictions) == 3
        assert all(len(ip.predictions) == 1 for ip in report.clean_predictions)

    def test_conditions_present(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert len(report.conditions) == 1
        cond = report.conditions[0]
        assert cond.corruption.value == "blur"
        assert cond.severity == 1

    def test_run_id_propagated(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector, run_id="test-run-42")
        assert report.run_id == "test-run-42"

    def test_auto_run_id_generated(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert report.run_id.startswith("run-")

    def test_config_recorded(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert report.config.model_id == base_config["model_id"]
        assert report.config.dataset_id == base_config["dataset_id"]

    def test_metric_definitions_present(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert "detection_retention" in report.metric_definitions

    def test_limitations_present(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        assert len(report.limitations) > 0


# --------------------------------------------------------------------------- #
# 2. PARTIAL run                                                                #
# --------------------------------------------------------------------------- #

class TestPartialRun:
    """Simulate a broken image that causes a load error for one image."""

    def test_status_is_partial(self, tmp_path, dataset_id):
        """Register a dataset with one corrupt (zero-byte) file."""
        import shutil, cv2
        root = tmp_path / "partial_ds"
        root.mkdir()
        # Good image
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        cv2.imwrite(str(root / "good.png"), img)
        # Bad image: zero bytes → cv2.imread returns None
        (root / "bad.png").write_bytes(b"")

        did = "partial_test_dataset"
        register_dataset(did, root)
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": did,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }
        report = evaluate_run(cfg, detector=FakeDetector([_CLEAN_PRED]))
        assert report.status == RunStatus.PARTIAL

    def test_errors_recorded(self, tmp_path):
        import cv2
        root = tmp_path / "partial2"
        root.mkdir()
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        cv2.imwrite(str(root / "good.png"), img)
        (root / "bad.png").write_bytes(b"not_an_image")

        did = "partial_test_dataset2"
        register_dataset(did, root)
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": did,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }
        report = evaluate_run(cfg, detector=FakeDetector([_CLEAN_PRED]))
        assert len(report.errors) >= 1
        stages = {e.stage for e in report.errors}
        assert "load" in stages


# --------------------------------------------------------------------------- #
# 3. FAILED run                                                                 #
# --------------------------------------------------------------------------- #

class TestFailedRun:

    def test_status_is_failed_when_all_images_fail(self, tmp_path):
        """All images are zero-byte → every load fails → FAILED status."""
        root = tmp_path / "fail_ds"
        root.mkdir()
        (root / "a.png").write_bytes(b"")
        (root / "b.png").write_bytes(b"")

        did = "failed_test_dataset"
        register_dataset(did, root)
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": did,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }
        report = evaluate_run(cfg, detector=FakeDetector([_CLEAN_PRED]))
        assert report.status == RunStatus.FAILED

    def test_failed_report_has_errors(self, tmp_path):
        root = tmp_path / "fail_ds2"
        root.mkdir()
        (root / "a.png").write_bytes(b"")

        did = "failed_test_dataset2"
        register_dataset(did, root)
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": did,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }
        report = evaluate_run(cfg, detector=FakeDetector([_CLEAN_PRED]))
        assert len(report.errors) > 0


# --------------------------------------------------------------------------- #
# 4. Progress callback                                                          #
# --------------------------------------------------------------------------- #

class TestProgressCallback:

    def test_callback_called_once_per_image(self, base_config):
        calls = []
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(
            base_config, detector=detector,
            progress_callback=lambda done, total: calls.append((done, total)),
        )
        n = len(report.clean_predictions) + len(report.errors)
        assert len(calls) == n

    def test_callback_total_matches_image_count(self, base_config):
        totals = []
        evaluate_run(
            base_config,
            detector=FakeDetector([_CLEAN_PRED]),
            progress_callback=lambda done, total: totals.append(total),
        )
        assert all(t == totals[0] for t in totals), "total should be constant"

    def test_callback_sequence_is_ascending(self, base_config):
        dones = []
        evaluate_run(
            base_config,
            detector=FakeDetector([_CLEAN_PRED]),
            progress_callback=lambda done, total: dones.append(done),
        )
        assert dones == sorted(dones)
        assert dones[-1] == dones[0] + len(dones) - 1  # consecutive


# --------------------------------------------------------------------------- #
# 5. Bad config rejected immediately                                            #
# --------------------------------------------------------------------------- #

class TestBadConfig:

    def test_missing_required_fields(self, dataset_id):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            evaluate_run(
                {"dataset_id": dataset_id},   # missing model_id, corruptions
                detector=FakeDetector([]),
            )

    def test_invalid_severity(self, dataset_id):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            evaluate_run(
                {
                    "model_id": "fasterrcnn_resnet50_fpn",
                    "dataset_id": dataset_id,
                    "corruptions": [{"kind": "blur", "severities": [9]}],  # invalid
                },
                detector=FakeDetector([]),
            )

    def test_unknown_corruption_kind(self, dataset_id):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            evaluate_run(
                {
                    "model_id": "fasterrcnn_resnet50_fpn",
                    "dataset_id": dataset_id,
                    "corruptions": [{"kind": "fog", "severities": [1]}],  # unknown
                },
                detector=FakeDetector([]),
            )


# --------------------------------------------------------------------------- #
# 6. Unregistered dataset                                                       #
# --------------------------------------------------------------------------- #

class TestUnregisteredDataset:

    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not registered"):
            evaluate_run(
                {
                    "model_id": "fasterrcnn_resnet50_fpn",
                    "dataset_id": "nonexistent_dataset_xyz",
                    "corruptions": [{"kind": "blur", "severities": [1]}],
                },
                detector=FakeDetector([]),
            )


# --------------------------------------------------------------------------- #
# 7. Condition metrics pool correctly                                           #
# --------------------------------------------------------------------------- #

class TestConditionMetrics:
    """Verify micro-average pooling across images."""

    def test_retention_is_micro_average(self, base_config):
        """
        Each of 3 images has 1 clean prediction.
        Corrupted also returns 1 prediction with high IoU → 3/3 matched.
        Expected detection_retention = 1.0.
        """
        detector = FakeDetector([_CORR_PRED_SAME])
        # FakeDetector returns same preds for clean and corrupted – after corruption
        # the predictions have the same box, so IoU≈0.67 which is ≥0.5.
        # But FakeDetector always returns the same list regardless of input,
        # so clean preds = corrupted preds = [_CORR_PRED_SAME].
        # All boxes overlap – all get matched.
        report = evaluate_run(base_config, detector=detector)
        cond = report.conditions[0]
        assert cond.metrics.detection_retention == 1.0

    def test_n_clean_matches_sum_of_per_image(self, base_config):
        detector = FakeDetector([_CLEAN_PRED])
        report = evaluate_run(base_config, detector=detector)
        cond = report.conditions[0]
        sum_n_clean = sum(r.metrics.n_clean for r in cond.per_image)
        assert cond.metrics.n_clean == sum_n_clean

    def test_n_matched_matches_sum_of_per_image(self, base_config):
        detector = FakeDetector([_CORR_PRED_SAME])
        report = evaluate_run(base_config, detector=detector)
        cond = report.conditions[0]
        sum_n_matched = sum(r.metrics.n_matched for r in cond.per_image)
        assert cond.metrics.n_matched == sum_n_matched

    def test_multiple_severities_produce_multiple_conditions(self, dataset_id):
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": dataset_id,
            "corruptions": [{"kind": "blur", "severities": [1, 2, 3]}],
            "seed": 0,
        }
        report = evaluate_run(cfg, detector=FakeDetector([_CLEAN_PRED]))
        assert len(report.conditions) == 3
        severities = [c.severity for c in report.conditions]
        assert sorted(severities) == [1, 2, 3]

    def test_multiple_corruption_kinds(self, dataset_id):
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": dataset_id,
            "corruptions": [
                {"kind": "blur", "severities": [1]},
                {"kind": "gaussian_noise", "severities": [1]},
            ],
            "seed": 0,
        }
        report = evaluate_run(cfg, detector=FakeDetector([_CLEAN_PRED]))
        assert len(report.conditions) == 2
        kinds = {c.corruption.value for c in report.conditions}
        assert kinds == {"blur", "gaussian_noise"}


# --------------------------------------------------------------------------- #
# 8. Failure records                                                            #
# --------------------------------------------------------------------------- #

class TestFailureRecords:

    def test_missing_after_corruption_recorded(self, dataset_id):
        """Clean has 1 pred; corrupted has 0 → MISSING_AFTER_CORRUPTION."""
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": dataset_id,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }
        # Alternate: clean always sees _CLEAN_PRED, corrupted sees []
        # FakeDetector returns the same list for both → return []
        detector = FakeDetector([])  # no predictions for either clean or corrupted

        # With no clean predictions there's nothing to lose.
        # Use two FakeDetectors: one for clean, one for corrupted by patching predict.
        class ToggleDetector(FakeDetector):
            def __init__(self):
                super().__init__([_CLEAN_PRED])
                self._call = 0
            def predict(self, img):
                r = [_CLEAN_PRED] if self._call % 2 == 0 else []
                self._call += 1
                return r

        report = evaluate_run(cfg, detector=ToggleDetector())
        missing = [f for f in report.failures
                   if f.failure_type == FailureType.MISSING_AFTER_CORRUPTION]
        assert len(missing) > 0, "Expected MISSING_AFTER_CORRUPTION failures"

    def test_class_flip_recorded(self, dataset_id):
        """Clean predicts class 0; corrupted predicts class 1 at same location."""
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": dataset_id,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }

        class FlipDetector(FakeDetector):
            def __init__(self):
                super().__init__([_CLEAN_PRED])
                self._call = 0
            def predict(self, img):
                r = [_CLEAN_PRED] if self._call % 2 == 0 else [_CORR_PRED_FLIP]
                self._call += 1
                return r

        report = evaluate_run(cfg, detector=FlipDetector())
        flips = [f for f in report.failures if f.failure_type == FailureType.CLASS_FLIP]
        assert len(flips) > 0, "Expected CLASS_FLIP failures"

    def test_new_after_corruption_recorded(self, dataset_id):
        """Clean has 0 preds; corrupted has 1 → NEW_AFTER_CORRUPTION."""
        cfg = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": dataset_id,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 0,
        }

        class NewDetector(FakeDetector):
            def __init__(self):
                super().__init__([])
                self._call = 0
            def predict(self, img):
                r = [] if self._call % 2 == 0 else [_CORR_PRED_EXTRA]
                self._call += 1
                return r

        report = evaluate_run(cfg, detector=NewDetector())
        new_preds = [f for f in report.failures
                     if f.failure_type == FailureType.NEW_AFTER_CORRUPTION]
        assert len(new_preds) > 0, "Expected NEW_AFTER_CORRUPTION failures"


# --------------------------------------------------------------------------- #
# 9. Partition guarantee at pipeline level                                      #
# --------------------------------------------------------------------------- #

class TestPipelinePartition:
    """Every clean prediction index appears in exactly one slot per image-result."""

    def test_clean_partition_holds_in_report(self, base_config):
        detector = FakeDetector([_CLEAN_PRED, _CORR_PRED_EXTRA])
        report = evaluate_run(base_config, detector=detector)

        for cond in report.conditions:
            for img_result in cond.per_image:
                n_clean = img_result.metrics.n_clean
                matched_ci = {m.clean_index for m in img_result.matches}
                unmatched_ci = set(img_result.unmatched_clean_indices)

                assert matched_ci & unmatched_ci == set(), \
                    f"{img_result.image_id}: index in both matched and unmatched (clean)"
                assert matched_ci | unmatched_ci == set(range(n_clean)), \
                    f"{img_result.image_id}: clean indices do not cover 0..{n_clean-1}"

    def test_corrupted_partition_holds_in_report(self, base_config):
        detector = FakeDetector([_CORR_PRED_SAME])
        report = evaluate_run(base_config, detector=detector)

        for cond in report.conditions:
            for img_result in cond.per_image:
                n_corr = len(img_result.predictions)
                matched_ki = {m.corrupted_index for m in img_result.matches}
                unmatched_ki = set(img_result.unmatched_corrupted_indices)

                assert matched_ki & unmatched_ki == set(), \
                    f"{img_result.image_id}: index in both matched and unmatched (corrupted)"
                assert matched_ki | unmatched_ki == set(range(n_corr)), \
                    f"{img_result.image_id}: corrupted indices do not cover 0..{n_corr-1}"
