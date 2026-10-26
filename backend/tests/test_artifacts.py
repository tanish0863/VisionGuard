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


def test_worker_uploads_artifacts_and_api_serves_from_storage(tmp_path: Path) -> None:
    from backend.app.artifacts import upload_run_artifacts
    from backend.app.storage import FileSystemArtifactStorage

    storage_root = tmp_path / "custom_storage_root"
    storage = FileSystemArtifactStorage(storage_root)

    db = RunDatabase(f"sqlite:///{(tmp_path / 'worker_storage.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-worker-storage-run"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    # 1. Worker uploads clean and corrupted artifacts to storage
    uploaded = upload_run_artifacts(run_id, report, storage=storage)
    assert len(uploaded) >= 2
    assert f"runs/{run_id}/clean_01_street_urban.jpg" in uploaded
    assert f"runs/{run_id}/corrupted_blur_1_01_street_urban.jpg" in uploaded

    # 2. Verify stored files exist in storage backend
    assert storage.object_exists(f"runs/{run_id}/clean_01_street_urban.jpg") is True
    assert storage.object_exists(f"runs/{run_id}/corrupted_blur_1_01_street_urban.jpg") is True

    # 3. API serves artifacts directly from storage
    app = create_app(database=db, storage=storage)
    with TestClient(app) as client:
        # List artifacts
        list_resp = client.get(f"/api/v1/runs/{run_id}/artifacts")
        assert list_resp.status_code == 200
        data = list_resp.json()
        art_ids = [item["artifact_id"] for item in data["artifacts"]]
        assert "clean_01_street_urban" in art_ids
        assert "corrupted_blur_1_01_street_urban" in art_ids

        # Retrieve clean image
        clean_resp = client.get(f"/api/v1/runs/{run_id}/artifacts/clean_01_street_urban")
        assert clean_resp.status_code == 200
        assert clean_resp.headers["content-type"] in ("image/jpeg", "image/jpg")
        assert len(clean_resp.content) > 1000

        # Retrieve corrupted image
        corr_resp = client.get(f"/api/v1/runs/{run_id}/artifacts/corrupted_blur_1_01_street_urban")
        assert corr_resp.status_code == 200
        assert corr_resp.headers["content-type"] in ("image/jpeg", "image/jpg")
        assert len(corr_resp.content) > 1000

    db.dispose()


def test_download_url_endpoint_and_database_metadata_persistence(tmp_path: Path) -> None:
    from backend.app.artifacts import upload_run_artifacts
    from backend.app.storage import FileSystemArtifactStorage

    storage_root = tmp_path / "custom_storage_root"
    storage = FileSystemArtifactStorage(storage_root)

    db = RunDatabase(f"sqlite:///{(tmp_path / 'download_url.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    run_id = "test-download-url-run"
    report = make_test_report_with_demo_image(run_id)
    seed_completed_run(db, run_id, report)

    # Worker uploads artifacts passing database
    uploaded = upload_run_artifacts(run_id, report, storage=storage, database=db)
    assert len(uploaded) >= 2

    # Verify metadata persisted in Neon/SQLite
    db_artifacts = db.list_artifacts_for_run(run_id)
    assert len(db_artifacts) >= 2
    art_map = {a["artifact_id"]: a for a in db_artifacts}
    assert "clean_01_street_urban" in art_map
    assert art_map["clean_01_street_urban"]["object_key"] == f"runs/{run_id}/clean_01_street_urban.jpg"
    assert art_map["clean_01_street_urban"]["size_bytes"] > 0

    # Test download-url endpoint
    app = create_app(database=db, storage=storage)
    with TestClient(app) as client:
        dl_resp = client.get(f"/api/v1/runs/{run_id}/artifacts/clean_01_street_urban/download-url?expires_in=600")
        assert dl_resp.status_code == 200
        dl_data = dl_resp.json()
        assert dl_data["artifact_id"] == "clean_01_street_urban"
        assert dl_data["expires_in"] == 600
        assert "clean_01_street_urban" in dl_data["download_url"]

        # Alias route /api/runs/...
        alias_resp = client.get(f"/api/runs/{run_id}/artifacts/clean_01_street_urban/download-url")
        assert alias_resp.status_code == 200
        assert alias_resp.json()["artifact_id"] == "clean_01_street_urban"

    db.dispose()


def test_artifact_metadata_composite_key_and_idempotent_retry(tmp_path: Path) -> None:
    """Verifies that artifact_id can exceed 36 chars, is scoped per run, and is idempotent on retries."""
    db = RunDatabase(f"sqlite:///{(tmp_path / 'composite_art.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    run_1 = "test-run-composite-01"
    run_2 = "test-run-composite-02"
    report_1 = make_test_report_with_demo_image(run_1)
    report_2 = make_test_report_with_demo_image(run_2)
    seed_completed_run(db, run_1, report_1)
    seed_completed_run(db, run_2, report_2)

    # 1. Long artifact_id exceeding 36 characters
    long_art_id = "corrupted_defocus_blur_5_01_street_urban_extra_long_identifier"
    assert len(long_art_id) > 36

    art_1 = db.record_artifact(
        run_id=run_1,
        artifact_id=long_art_id,
        artifact_type="corrupted",
        file_name=f"{long_art_id}.jpg",
        object_key=f"runs/{run_1}/{long_art_id}.jpg",
        content_type="image/jpeg",
        size_bytes=12345,
    )
    assert art_1["artifact_id"] == long_art_id

    # 2. Same artifact_id on run_2 should succeed (composite primary key)
    art_2 = db.record_artifact(
        run_id=run_2,
        artifact_id=long_art_id,
        artifact_type="corrupted",
        file_name=f"{long_art_id}.jpg",
        object_key=f"runs/{run_2}/{long_art_id}.jpg",
        content_type="image/jpeg",
        size_bytes=54321,
    )
    assert art_2["artifact_id"] == long_art_id
    assert db.get_artifact(run_1, long_art_id)["size_bytes"] == 12345
    assert db.get_artifact(run_2, long_art_id)["size_bytes"] == 54321

    # 3. Idempotent re-record (simulating worker retry)
    updated_art = db.record_artifact(
        run_id=run_1,
        artifact_id=long_art_id,
        artifact_type="corrupted",
        file_name=f"{long_art_id}.jpg",
        object_key=f"runs/{run_1}/{long_art_id}.jpg",
        content_type="image/jpeg",
        size_bytes=99999,
    )
    assert updated_art["size_bytes"] == 99999
    assert db.get_artifact(run_1, long_art_id)["size_bytes"] == 99999

    db.dispose()


def test_direct_artifact_streaming_endpoint(tmp_path: Path) -> None:
    """Verifies that /api/v1/artifacts/{artifact_path:path} streams objects and enforces security."""
    from backend.app.storage import FileSystemArtifactStorage

    storage_root = tmp_path / "raw_storage"
    storage = FileSystemArtifactStorage(storage_root)
    test_key = "runs/raw-run/sample.jpg"
    storage.put_object(test_key, b"\xFF\xD8\xFF\xE0RAW_IMAGE_DATA", content_type="image/jpeg")

    db = RunDatabase(f"sqlite:///{(tmp_path / 'raw_stream.sqlite3').as_posix()}")
    metadata.create_all(db.engine)

    app = create_app(database=db, storage=storage)
    with TestClient(app) as client:
        # 1. Successful stream
        resp = client.get(f"/api/v1/artifacts/{test_key}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.content == b"\xFF\xD8\xFF\xE0RAW_IMAGE_DATA"

        # 2. Missing object -> 404
        missing_resp = client.get("/api/v1/artifacts/runs/raw-run/missing.jpg")
        assert missing_resp.status_code == 404

        # 3. Path traversal attempt -> 403
        traversal_resp = client.get("/api/v1/artifacts/runs/raw-run/%2e%2e/secret.txt")
        assert traversal_resp.status_code == 403

    db.dispose()
