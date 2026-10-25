"""Unit tests for demo dataset registration and resolution.

Tests:
1. Automatic registration when the demo directory exists.
2. Missing directory behavior (raises FileNotFoundError with clear message).
3. Empty directory behavior (raises FileNotFoundError when no images present).
4. Idempotency and protection of user-registered paths.
5. Fallback registration during _load_image_paths() if available after import.
6. Full evaluate_run() execution with FakeDetector on a demo dataset.
"""
from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np
import pytest

from visionguard_contracts.visionguard.core.types import EvalConfig, RunStatus
from visionguard.core.model_adapter import FakeDetector
from visionguard.core.pipeline import (
    DEFAULT_DEMO_DATASET_ID,
    DEFAULT_DEMO_DIR,
    _DATASET_ROOTS,
    _load_image_paths,
    auto_register_default_datasets,
    evaluate_run,
    register_dataset,
)


@pytest.fixture(autouse=True)
def preserve_dataset_roots():
    """Isolate _DATASET_ROOTS between tests."""
    original = dict(_DATASET_ROOTS)
    yield
    _DATASET_ROOTS.clear()
    _DATASET_ROOTS.update(original)


def _create_dummy_image(path: Path, width: int = 100, height: int = 100) -> Path:
    img = np.full((height, width, 3), fill_value=128, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def test_auto_registration_when_directory_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When the default demo directory exists, auto_register_default_datasets registers it."""
    demo_dir = tmp_path / "mock_demo_dir"
    demo_dir.mkdir()

    monkeypatch.setattr("visionguard.core.pipeline.DEFAULT_DEMO_DIR", demo_dir)
    _DATASET_ROOTS.pop(DEFAULT_DEMO_DATASET_ID, None)

    auto_register_default_datasets()

    assert DEFAULT_DEMO_DATASET_ID in _DATASET_ROOTS
    assert _DATASET_ROOTS[DEFAULT_DEMO_DATASET_ID] == demo_dir


def test_missing_directory_behavior(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When the default demo directory is missing, it is not registered, and load raises FileNotFoundError."""
    nonexistent = tmp_path / "does_not_exist"
    monkeypatch.setattr("visionguard.core.pipeline.DEFAULT_DEMO_DIR", nonexistent)
    _DATASET_ROOTS.pop(DEFAULT_DEMO_DATASET_ID, None)

    auto_register_default_datasets()
    assert DEFAULT_DEMO_DATASET_ID not in _DATASET_ROOTS

    with pytest.raises(FileNotFoundError, match="is not registered"):
        _load_image_paths(DEFAULT_DEMO_DATASET_ID, max_images=None)


def test_empty_directory_behavior(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """When the demo directory exists but contains no valid images, loading raises FileNotFoundError."""
    empty_demo_dir = tmp_path / "empty_demo"
    empty_demo_dir.mkdir()
    # Add a non-image file (e.g. README.md)
    (empty_demo_dir / "README.md").write_text("dataset info")

    monkeypatch.setattr("visionguard.core.pipeline.DEFAULT_DEMO_DIR", empty_demo_dir)
    _DATASET_ROOTS.pop(DEFAULT_DEMO_DATASET_ID, None)

    auto_register_default_datasets()
    assert DEFAULT_DEMO_DATASET_ID in _DATASET_ROOTS

    with pytest.raises(FileNotFoundError, match="No images found in"):
        _load_image_paths(DEFAULT_DEMO_DATASET_ID, max_images=None)


def test_idempotency_and_protection_of_user_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Automatic registration must not overwrite an already registered custom dataset path."""
    user_custom_dir = tmp_path / "user_custom_dataset"
    user_custom_dir.mkdir()
    default_dir = tmp_path / "bundled_demo_dir"
    default_dir.mkdir()

    monkeypatch.setattr("visionguard.core.pipeline.DEFAULT_DEMO_DIR", default_dir)

    # User registers custom path for visionguard_demo first
    register_dataset(DEFAULT_DEMO_DATASET_ID, user_custom_dir)
    assert _DATASET_ROOTS[DEFAULT_DEMO_DATASET_ID] == user_custom_dir

    # Calling auto_register_default_datasets must not overwrite user registration
    auto_register_default_datasets()
    assert _DATASET_ROOTS[DEFAULT_DEMO_DATASET_ID] == user_custom_dir

    # Second call should also remain idempotent
    auto_register_default_datasets()
    assert _DATASET_ROOTS[DEFAULT_DEMO_DATASET_ID] == user_custom_dir


def test_fallback_registration_on_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """If the dataset directory is created after import, _load_image_paths registers it via fallback."""
    demo_dir = tmp_path / "late_created_demo"
    demo_dir.mkdir()
    _create_dummy_image(demo_dir / "sample.png")

    monkeypatch.setattr("visionguard.core.pipeline.DEFAULT_DEMO_DIR", demo_dir)
    _DATASET_ROOTS.pop(DEFAULT_DEMO_DATASET_ID, None)

    # Calling _load_image_paths should trigger fallback registration
    paths = _load_image_paths(DEFAULT_DEMO_DATASET_ID, max_images=None)
    assert len(paths) == 1
    assert paths[0].name == "sample.png"
    assert _DATASET_ROOTS[DEFAULT_DEMO_DATASET_ID] == demo_dir


def test_evaluate_run_with_demo_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """evaluate_run() executes successfully with FakeDetector on a populated demo dataset."""
    demo_dir = tmp_path / "populated_demo"
    demo_dir.mkdir()
    _create_dummy_image(demo_dir / "img1.jpg")
    _create_dummy_image(demo_dir / "img2.jpg")

    monkeypatch.setattr("visionguard.core.pipeline.DEFAULT_DEMO_DIR", demo_dir)
    _DATASET_ROOTS.pop(DEFAULT_DEMO_DATASET_ID, None)

    fake_preds = [
        {
            "class_id": 0,
            "class_name": "person",
            "confidence": 0.95,
            "bbox_xyxy": [10.0, 10.0, 50.0, 50.0],
        }
    ]
    detector = FakeDetector(fake_preds, score_threshold=0.5)

    config = EvalConfig.model_validate(
        {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": DEFAULT_DEMO_DATASET_ID,
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 42,
            "score_threshold": 0.5,
            "match_iou_threshold": 0.5,
        }
    )

    report = evaluate_run(config, detector=detector)

    assert report.status == RunStatus.COMPLETED
    assert report.dataset.dataset_id == DEFAULT_DEMO_DATASET_ID
    assert report.dataset.image_count == 2
    assert len(report.clean_predictions) == 2
    assert len(report.conditions) == 1
    assert report.conditions[0].metrics.n_matched == 2
    assert len(report.errors) == 0
