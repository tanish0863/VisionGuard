from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.contracts import EvalConfig, EvaluationReport, RunStatus
from backend.app.database import RunDatabase
from backend.app.evaluation_adapter import get_evaluator
from backend.app.main import create_app
from visionguard_contracts.visionguard.core.fixtures import build_fixture_report


def valid_config() -> dict[str, Any]:
    return {
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "corruptions": [
            {"kind": "blur", "severities": [2]},
            {"kind": "low_light", "severities": [2]},
        ],
        "seed": 42,
        "score_threshold": 0.5,
        "match_iou_threshold": 0.5,
        "max_images": None,
    }


def make_report(run_id: str, status: RunStatus) -> EvaluationReport:
    report = build_fixture_report().model_dump(mode="json")
    report["run_id"] = run_id
    report["status"] = status.value
    if status in {RunStatus.PARTIAL, RunStatus.FAILED}:
        report["errors"] = [
            {"image_id": "image_001", "stage": "inference", "message": "fixture error"}
        ]
    return EvaluationReport.model_validate(report)


def make_client(
    tmp_path: Path,
    evaluator: Any,
) -> TestClient:
    app = create_app(
        database_path=tmp_path / "test.sqlite3",
        evaluator=evaluator,
        supported_models=["fasterrcnn_resnet50_fpn"],
    )
    return TestClient(app)


def unexpected_evaluation(
    config: EvalConfig, *, run_id: str
) -> EvaluationReport:
    raise AssertionError(
        f"Unexpected evaluator call for {config.model_id} in run {run_id}"
    )


def test_contract_evaluator_imports() -> None:
    assert get_evaluator().__module__ == "visionguard.core.api"


def test_health_and_supported_models(tmp_path: Path) -> None:
    with make_client(tmp_path, unexpected_evaluation) as client:
        assert client.get("/health").json() == {
            "status": "healthy",
            "service": "VisionGuard API",
        }
        assert client.get("/api/v1/models").json() == {
            "models": ["fasterrcnn_resnet50_fpn"]
        }


def test_run_persists_status_and_fixture_report(
    tmp_path: Path,
) -> None:
    calls: list[tuple[EvalConfig, str]] = []

    def evaluate(config: EvalConfig, *, run_id: str) -> EvaluationReport:
        calls.append((config, run_id))
        return make_report(run_id, RunStatus.COMPLETED)

    request = valid_config()
    with make_client(tmp_path, evaluate) as client:
        response = client.post("/api/v1/runs", json=request)
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
        body = report_response.json()
        assert body["report"]["is_fixture"] is True
        assert body["report"]["run_id"] == created["run_id"]

        listing = client.get("/api/v1/runs").json()
        assert listing["total"] == 1
        assert listing["runs"][0]["run_id"] == created["run_id"]

    assert len(calls) == 1
    assert calls[0][0].model_dump() == EvalConfig.model_validate(request).model_dump()
    assert calls[0][1] == created["run_id"]


@pytest.mark.parametrize(
    ("status", "expected_message"),
    [
        (RunStatus.PARTIAL, "Evaluation returned a PARTIAL report; see the report for details"),
        (RunStatus.FAILED, "Evaluation returned a FAILED report; see the report for details"),
    ],
)
def test_terminal_error_reports_are_persisted_and_retrievable(
    tmp_path: Path,
    status: RunStatus,
    expected_message: str,
) -> None:
    def evaluate(_config: EvalConfig, *, run_id: str) -> EvaluationReport:
        assert _config.dataset_id == "visionguard_demo"
        return make_report(run_id, status)

    with make_client(tmp_path, evaluate) as client:
        created = client.post("/api/v1/runs", json=valid_config()).json()
        run = client.get(f"/api/v1/runs/{created['run_id']}").json()
        assert run["status"] == status.value
        assert run["error_message"] == expected_message

        response = client.get(f"/api/v1/runs/{created['run_id']}/report")
        assert response.status_code == 200
        assert response.json()["report"]["errors"][0]["message"] == "fixture error"
        assert response.json()["report"]["status"] == status.value


@pytest.mark.parametrize(
    "patch",
    [
        {"corruptions": []},
        {"corruptions": [{"kind": "blur", "severities": [4]}]},
        {"corruptions": [{"kind": "fog", "severities": [1]}]},
        {
            "corruptions": [
                {"kind": "blur", "severities": [1]},
                {"kind": "blur", "severities": [2]},
            ]
        },
        {"score_threshold": 2},
        {"match_iou_threshold": 0},
        {"unexpected": True},
    ],
)
def test_invalid_config_is_rejected_without_creating_run(
    tmp_path: Path, patch: dict[str, Any]
) -> None:
    with make_client(
        tmp_path,
        unexpected_evaluation,
    ) as client:
        config = {**valid_config(), **patch}
        assert client.post("/api/v1/runs", json=config).status_code == 422
        assert client.get("/api/v1/runs").json()["total"] == 0


def test_unknown_run_returns_not_found(tmp_path: Path) -> None:
    with make_client(tmp_path, unexpected_evaluation) as client:
        assert client.get("/api/v1/runs/missing").status_code == 404
        assert client.get("/api/v1/runs/missing/report").status_code == 404


def test_evaluator_exception_is_sanitized_and_report_unavailable(
    tmp_path: Path,
) -> None:
    def fail(config: EvalConfig, *, run_id: str) -> EvaluationReport:
        raise RuntimeError(
            f"internal path leaked for {run_id} and {config.model_id}"
        )

    with make_client(tmp_path, fail) as client:
        created = client.post("/api/v1/runs", json=valid_config()).json()
        run = client.get(f"/api/v1/runs/{created['run_id']}").json()
        assert run["status"] == "FAILED"
        assert run["error_message"] == (
            "Evaluation failed before a valid report was produced"
        )
        assert "internal path" not in run["error_message"]
        assert client.get(
            f"/api/v1/runs/{created['run_id']}/report"
        ).status_code == 409


@pytest.mark.parametrize(
    "result_kind", ["missing_required_fields", "mismatched_run_id"]
)
def test_invalid_evaluator_report_fails_run(
    tmp_path: Path, result_kind: str
) -> None:
    def evaluate(config: EvalConfig, *, run_id: str) -> Any:
        assert config.dataset_id == "visionguard_demo"
        if result_kind == "mismatched_run_id":
            return make_report("wrong", RunStatus.COMPLETED)
        return {"run_id": run_id}

    with make_client(tmp_path, evaluate) as client:
        created = client.post("/api/v1/runs", json=valid_config()).json()
        run = client.get(f"/api/v1/runs/{created['run_id']}").json()
        assert run["status"] == "FAILED"
        assert run["error_message"] == (
            "Evaluation failed before a valid report was produced"
        )
        assert client.get(
            f"/api/v1/runs/{created['run_id']}/report"
        ).status_code == 409


def test_invalid_contract_report_is_rejected() -> None:
    invalid = build_fixture_report().model_dump(mode="json")
    invalid["status"] = "PARTIAL"
    invalid["errors"] = []
    with pytest.raises(ValidationError):
        EvaluationReport.model_validate(invalid)


def test_incomplete_runs_are_marked_failed_after_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "restart.sqlite3"
    database = RunDatabase(database_path)
    database.create_run(
        {
            "run_id": "incomplete",
            "status": "RUNNING",
            "model_id": "fasterrcnn_resnet50_fpn",
            "dataset_id": "visionguard_demo",
            "config": valid_config(),
            "created_at": "2026-10-24T12:10:00+00:00",
        }
    )

    restarted_database = RunDatabase(database_path)
    run = restarted_database.get_run("incomplete")
    assert run is not None
    assert run["status"] == "FAILED"
    assert run["error_message"] == "Backend restarted before evaluation completed"
