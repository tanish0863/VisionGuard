from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.database import RunDatabase, metadata
from backend.app.main import create_app
from backend.visionguard.core.pipeline import (
    DEFAULT_DEMO_DATASET_ID,
    _DATASET_ROOTS,
    get_registered_datasets,
    register_dataset,
)


def test_get_registered_datasets_metadata() -> None:
    datasets = get_registered_datasets()
    assert len(datasets) >= 1
    demo = next((d for d in datasets if d["id"] == DEFAULT_DEMO_DATASET_ID), None)
    assert demo is not None
    assert demo["name"] == "VisionGuard Demo Dataset"
    assert demo["image_count"] == 10
    assert demo["has_ground_truth"] is False
    assert demo["supported"] is True


def test_api_list_datasets_endpoint(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'datasets.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    app = create_app(database=db)

    with TestClient(app) as client:
        resp = client.get("/api/v1/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert "datasets" in data
        demo = next((d for d in data["datasets"] if d["id"] == DEFAULT_DEMO_DATASET_ID), None)
        assert demo is not None
        assert demo["image_count"] == 10

    db.dispose()


def test_create_run_rejects_unregistered_dataset(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'datasets_reject.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    app = create_app(database=db)

    with TestClient(app) as client:
        payload = {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": "completely_unregistered_and_unsupported_dataset",
            "corruptions": [{"kind": "blur", "severities": [1]}],
        }
        resp = client.post("/api/v1/runs", json=payload)
        assert resp.status_code == 422
        assert "unregistered" in resp.json()["detail"].lower()

    db.dispose()


def test_empty_or_missing_dataset_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Temporarily register an empty directory
    empty_dir = tmp_path / "empty_dataset"
    empty_dir.mkdir()
    monkeypatch.setitem(_DATASET_ROOTS, "test_empty_dataset", empty_dir)

    datasets = get_registered_datasets()
    entry = next((d for d in datasets if d["id"] == "test_empty_dataset"), None)
    assert entry is not None
    assert entry["image_count"] == 0
    assert entry["supported"] is False
