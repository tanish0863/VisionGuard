from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.database import RunDatabase
from backend.app.main import create_app


@pytest.fixture
def report() -> dict[str, Any]:
    return {"metrics": {"map50": 0.81}, "samples": 12}


def make_client(
    tmp_path: Path,
    evaluator: Any,
) -> TestClient:
    app = create_app(
        database_path=tmp_path / "test.sqlite3",
        evaluator=evaluator,
        supported_models=["yolov8n"],
    )
    return TestClient(app)


def test_health_and_supported_models(tmp_path: Path) -> None:
    with make_client(tmp_path, lambda config: {"config": config}) as client:
        assert client.get("/health").json() == {
            "status": "healthy",
            "service": "VisionGuard API",
        }
        assert client.get("/api/v1/models").json() == {"models": ["yolov8n"]}


def test_run_persists_status_and_report(
    tmp_path: Path, report: dict[str, Any]
) -> None:
    def evaluate(config: dict[str, Any]) -> dict[str, Any]:
        assert config == {
            "model_id": "yolov8n",
            "dataset_id": "validation",
            "parameters": {"corruption": "blur"},
        }
        return report

    with make_client(tmp_path, evaluate) as client:
        response = client.post(
            "/api/v1/runs",
            json={
                "model_id": "yolov8n",
                "dataset_id": "validation",
                "parameters": {"corruption": "blur"},
            },
        )
        assert response.status_code == 202
        created = response.json()
        assert created["status"] == "QUEUED"

        run_response = client.get(f"/api/v1/runs/{created['run_id']}")
        assert run_response.status_code == 200
        assert run_response.json()["status"] == "COMPLETED"

        report_response = client.get(
            f"/api/v1/runs/{created['run_id']}/report"
        )
        assert report_response.status_code == 200
        assert report_response.json()["report"] == report

        listing = client.get("/api/v1/runs").json()
        assert listing["total"] == 1
        assert listing["runs"][0]["run_id"] == created["run_id"]


def test_invalid_run_request_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path, lambda config: {"config": config}) as client:
        response = client.post(
            "/api/v1/runs",
            json={"model_id": " ", "dataset_id": "validation"},
        )
    assert response.status_code == 422


def test_unsupported_model_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path, lambda config: {"config": config}) as client:
        response = client.post(
            "/api/v1/runs",
            json={"model_id": "unknown", "dataset_id": "validation"},
        )
    assert response.status_code == 422


def test_unknown_run_returns_not_found(tmp_path: Path) -> None:
    with make_client(tmp_path, lambda config: {"config": config}) as client:
        assert client.get("/api/v1/runs/missing").status_code == 404
        assert client.get("/api/v1/runs/missing/report").status_code == 404


def test_failed_evaluation_is_persisted_and_report_is_unavailable(
    tmp_path: Path,
) -> None:
    def fail(_config: dict[str, Any]) -> dict[str, Any]:
        assert isinstance(_config, dict)
        raise RuntimeError("evaluation failed")

    with make_client(tmp_path, fail) as client:
        created = client.post(
            "/api/v1/runs",
            json={"model_id": "yolov8n", "dataset_id": "validation"},
        ).json()
        status = client.get(f"/api/v1/runs/{created['run_id']}").json()
        assert status["status"] == "FAILED"
        assert status["error_message"] == "Evaluation failed (RuntimeError)"
        assert client.get(
            f"/api/v1/runs/{created['run_id']}/report"
        ).status_code == 409


def test_incomplete_runs_are_marked_failed_after_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "restart.sqlite3"
    database = RunDatabase(database_path)
    database.create_run(
        {
            "run_id": "incomplete",
            "status": "RUNNING",
            "model_id": "yolov8n",
            "dataset_id": "validation",
            "config": {},
            "created_at": "2026-10-24T12:10:00+00:00",
        }
    )

    restarted_database = RunDatabase(database_path)
    run = restarted_database.get_run("incomplete")
    assert run is not None
    assert run["status"] == "FAILED"
    assert run["error_message"] == "Backend restarted before evaluation completed"
