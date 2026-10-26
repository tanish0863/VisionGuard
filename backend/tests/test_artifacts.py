from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts import RunStatus
from backend.app.database import RunDatabase, metadata
from backend.app.main import create_app
from backend.visionguard.core.pipeline import DEFAULT_DEMO_DIR


def make_test_report_with_demo_image(run_id: str) -> dict[str, Any]:
    demo_image = DEFAULT_DEMO_DIR / "01_street_urban.jpg"
    return {
        "schema_version": "1.0.0",
        "is_fixture": False,
        "run_id": run_id,
        "status": "COMPLETED",
        "created_at": "2026-10-25T15:00:00Z",
        "model": {
            "model_id": "fasterrcnn_resnet50_fpn",
            "name": "fasterrcnn_resnet50_fpn",
            "framework": "TorchvisionDetector",
            "weights": "DEFAULT",
            "weights_license": "PyTorch",
        },
        "dataset": {
            "dataset_id": "visionguard_demo",
            "name": "VisionGuard Demo Dataset",
            "image_count": 1,
            "has_ground_truth": False,
        },
        "config": {
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": "visionguard_demo",
            "corruptions": [{"kind": "blur", "severities": [1]}],
            "seed": 42,
            "score_threshold": 0.5,
            "match_iou_threshold": 0.5,
        },
        "clean_predictions": [
            {
                "image_id": "01_street_urban",
                "width": 1280,
                "height": 720,
                "image_path": str(demo_image),
                "predictions": [],
            }
        ],
        "conditions": [
            {
                "corruption": "blur",
                "severity": 1,
                "seed": 42,
                "metrics": {
                    "n_clean": 0,
                    "n_corrupted": 0,
                    "n_matched": 0,
                    "n_class_flips": 0,
                    "n_unmatched_clean": 0,
                    "n_unmatched_corrupted": 0,
                    "detection_retention": None,
                    "class_consistent_retention": None,
                    "mean_matched_iou": None,
                    "mean_confidence_delta": None,
                    "class_flip_rate": None,
                    "unavailable": {},
                },
                "per_image": [
                    {
                        "image_id": "01_street_urban",
                        "predictions": [],
                        "matches": [],
                        "unmatched_clean_indices": [],
                        "unmatched_corrupted_indices": [],
                        "metrics": {
                            "n_clean": 0,
                            "n_corrupted": 0,
                            "n_matched": 0,
                            "n_class_flips": 0,
                            "n_unmatched_clean": 0,
                            "n_unmatched_corrupted": 0,
                            "detection_retention": None,
                            "class_consistent_retention": None,
                            "mean_matched_iou": None,
                            "mean_confidence_delta": None,
                            "class_flip_rate": None,
                            "unavailable": {},
                        },
                    }
                ],
            }
        ],
        "failures": [],
        "errors": [],
    }


def seed_completed_run(db: RunDatabase, run_id: str, report: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    db.create_run({
        "run_id": run_id,
        "status": "QUEUED",
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "config": report["config"],
        "created_at": now,
        "updated_at": now,
    })
    db.start_run(run_id, now)
    db.complete_run(run_id, report, "COMPLETED", now)


def test_list_and_retrieve_clean_artifact(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'artifacts.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-art-run-1"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    app = create_app(database=db)
    with TestClient(app) as client:
        # List artifacts
        resp = client.get(f"/api/v1/runs/{run_id}/artifacts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["total"] >= 1
        artifact_ids = [a["artifact_id"] for a in data["artifacts"]]
        assert "clean_01_street_urban" in artifact_ids
        assert "corrupted_blur_1_01_street_urban" in artifact_ids

        # Fetch clean original image artifact
        img_resp = client.get(f"/api/v1/runs/{run_id}/artifacts/clean_01_street_urban")
        assert img_resp.status_code == 200
        assert img_resp.headers["content-type"] in ("image/jpeg", "image/jpg")
        assert len(img_resp.content) > 1000  # Valid binary content
        assert img_resp.content.startswith(b"\xff\xd8")  # JPEG magic bytes

    db.dispose()


def test_retrieve_corrupted_artifact(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'artifacts_corr.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-art-run-2"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    app = create_app(database=db)
    with TestClient(app) as client:
        corr_resp = client.get(f"/api/v1/runs/{run_id}/artifacts/corrupted_blur_1_01_street_urban")
        assert corr_resp.status_code == 200
        assert corr_resp.headers["content-type"] == "image/jpeg"
        assert corr_resp.content.startswith(b"\xff\xd8")  # Valid JPEG

    db.dispose()


def test_overlay_artifact_returns_404_with_explanation(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'artifacts_overlay.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-art-run-3"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    app = create_app(database=db)
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/runs/{run_id}/artifacts/overlay_01_street_urban")
        assert resp.status_code == 404
        assert "not yet implemented" in resp.json()["detail"].lower()

    db.dispose()


def test_missing_and_unauthorized_artifact_retrieval(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'artifacts_missing.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-art-run-4"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    app = create_app(database=db)
    with TestClient(app) as client:
        # Non-existent run
        assert client.get("/api/v1/runs/missing-run/artifacts").status_code == 404
        assert client.get("/api/v1/runs/missing-run/artifacts/clean_01").status_code == 404

        # Non-existent artifact ID on valid run
        missing_art = client.get(f"/api/v1/runs/{run_id}/artifacts/clean_nonexistent")
        assert missing_art.status_code == 404

        # Malformed artifact ID
        bad_art = client.get(f"/api/v1/runs/{run_id}/artifacts/unknown_artifact_format")
        assert bad_art.status_code == 404

    db.dispose()


def test_path_traversal_attempt_is_blocked(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'artifacts_traversal.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-art-run-traversal"
    report = make_test_report_with_demo_image(run_id)

    # Inject a malicious path into clean_predictions pointing outside the registered dataset directory
    malicious_path = Path(__file__).resolve().parents[2] / ".env"
    report["clean_predictions"][0]["image_path"] = str(malicious_path)

    seed_completed_run(db, run_id, report)

    app = create_app(database=db)
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/runs/{run_id}/artifacts/clean_01_street_urban")
        # Must be blocked (403 Forbidden or 404), never return 200 with .env contents
        assert resp.status_code in (403, 404)
    db.dispose()


def test_worker_creates_artifact_and_api_retrieves_content(tmp_path: Path, monkeypatch: Any) -> None:
    # Set shared artifacts directory to simulated shared volume
    shared_artifacts = tmp_path / "shared_artifacts"
    shared_artifacts.mkdir()
    monkeypatch.setenv("VISIONGUARD_ARTIFACTS_DIR", str(shared_artifacts))

    db = RunDatabase(f"sqlite:///{(tmp_path / 'shared_art.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-shared-art-run"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    # 1. Worker creates an artifact in the shared volume
    worker_artifact_dir = shared_artifacts / run_id
    worker_artifact_dir.mkdir(parents=True)
    expected_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00fake-jpeg-binary-artifact"
    artifact_file = worker_artifact_dir / "worker_heatmap.jpg"
    artifact_file.write_bytes(expected_content)

    # 2. API discovers and retrieves the artifact
    app = create_app(database=db)
    with TestClient(app) as client:
        # Check artifact listing includes the worker artifact
        list_resp = client.get(f"/api/v1/runs/{run_id}/artifacts")
        assert list_resp.status_code == 200
        data = list_resp.json()
        artifact_ids = [item["artifact_id"] for item in data["artifacts"]]
        assert "worker_heatmap" in artifact_ids

        # Check retrieval returns correct bytes and MIME type
        get_resp = client.get(f"/api/v1/runs/{run_id}/artifacts/worker_heatmap")
        assert get_resp.status_code == 200
        assert get_resp.headers["content-type"].startswith("image/jpeg")
        assert get_resp.content == expected_content

    db.dispose()

