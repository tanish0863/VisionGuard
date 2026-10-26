"""Edge-case tests for the functions implemented in backend/core.py."""
import numpy as np
import pytest

from core import compare, corrupt, iou, report_md, warp_box


def test_zero_severity_returns_equal_but_independent_image():
    image = np.full((24, 32, 3), 120, dtype=np.uint8)

    result, matrix = corrupt(image, "blur", 0)

    assert np.array_equal(result, image)
    assert result is not image
    assert matrix is None


def test_unknown_corruption_raises_value_error():
    image = np.zeros((20, 20, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="unknown corruption"):
        corrupt(image, "not-a-real-corruption", 0.5)


def test_iou_for_identical_boxes_is_one():
    assert iou([0, 0, 1, 1], [0, 0, 1, 1]) == pytest.approx(1.0)


def test_iou_for_disjoint_boxes_is_zero():
    assert iou([0, 0, 0.4, 0.4], [0.6, 0.6, 1, 1]) == pytest.approx(0.0)


def test_warp_box_with_identity_transform_preserves_box():
    box = [0.1, 0.2, 0.7, 0.9]
    identity = np.array([[1, 0, 0], [0, 1, 0]], dtype=float)

    result = warp_box(box, identity, 100, 100)

    assert result == pytest.approx(box)


def test_compare_empty_lists_has_no_failures():
    result = compare([], [])

    assert result["retention"] is None
    assert result["conf_change"] is None
    assert result["lost"] == 0
    assert result["class_changes"] == 0
    assert result["spurious"] == 0
    assert result["failures"] == []


def test_compare_marks_unmatched_alternative_as_spurious():
    alternative = [
        {"label": "dog", "conf": 0.8, "box": [0.1, 0.1, 0.4, 0.4]}
    ]

    result = compare([], alternative)

    assert result["retention"] is None
    assert result["spurious"] == 1
    assert result["failures"][0]["kind"] == "spurious"


def test_report_contains_run_configuration_and_table():
    run = {
        "id": "test123",
        "model": "test-model.pt",
        "config": {
            "corruption": "blur",
            "levels": [0.0],
            "iou": 0.5,
            "seed": 42,
            "filename": "sample.png",
        },
        "levels": [{
            "severity": 0.0,
            "detections": [],
            "retention": None,
            "conf_change": None,
            "lost": 0,
            "class_changes": 0,
            "spurious": 0,
            "latency_ms": 1.0,
        }],
    }

    report = report_md(run)

    assert "# VisionGuard report test123" in report
    assert "Condition: blur" in report
    assert "sample.png" in report
    assert "| Severity | Detections | Retention |" in report
