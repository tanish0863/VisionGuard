
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

from backend.app.database import RunDatabase
from backend.app.contracts import EvalConfig, EvaluationReport
from backend.app.evaluation_adapter import get_evaluator
from backend.app.schemas import (
    ModelsResponse,
    ReportResponse,
    RunCreateRequest,
    RunListResponse,
    RunResponse,
    RunStatus,
)

logger = logging.getLogger(__name__)
DEFAULT_DATABASE_PATH = Path(
    os.getenv(
        "VISIONGUARD_DATABASE_PATH",
        str(Path(__file__).resolve().parents[1] / "visionguard.sqlite3"),
    )
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configured_models() -> list[str]:
    values = os.getenv("VISIONGUARD_SUPPORTED_MODELS", "")
    return sorted({value.strip() for value in values.split(",") if value.strip()})


def create_app(
    database_path: Path | str = DEFAULT_DATABASE_PATH,
    evaluator: Callable[..., EvaluationReport] | None = None,
    supported_models: list[str] | None = None,
) -> FastAPI:
    database = RunDatabase(Path(database_path))
    models = configured_models() if supported_models is None else supported_models
    application = FastAPI(
        title="VisionGuard API",
        description="Backend API for the VisionGuard model evaluation platform",
        version="0.1.0",
    )
    application.state.database = database
    application.state.supported_models = models

    def execute_run(run_id: str, config: EvalConfig) -> None:
        database.start_run(run_id, utc_now())
        try:
            evaluator_function = evaluator if evaluator is not None else get_evaluator()
            result = evaluator_function(config, run_id=run_id)
            report = EvaluationReport.model_validate(result)
            if report.run_id != run_id:
                raise ValueError("Evaluator report run_id does not match the requested run")
            report_json = json.loads(report.model_dump_json())
        except Exception:
            logger.exception("Evaluation run %s failed", run_id)
            database.fail_run(
                run_id,
                "Evaluation failed before a valid report was produced",
                utc_now(),
            )
            return
        status = report.status.value
        error_message = (
            f"Evaluation returned a {status} report; see the report for details"
            if status in {"PARTIAL", "FAILED"}
            else None
        )
        database.complete_run(
            run_id,
            report_json,
            status,
            utc_now(),
            error_message,
        )

    @application.get("/")
    def home() -> dict[str, str]:
        return {"message": "VisionGuard backend is running"}

    @application.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy", "service": "VisionGuard API"}

    @application.get("/api/v1/models", response_model=ModelsResponse)
    def list_models() -> ModelsResponse:
        return ModelsResponse(models=application.state.supported_models)

    @application.post(
        "/api/v1/runs", response_model=RunResponse, status_code=202
    )
    def create_run(
        request: RunCreateRequest, background_tasks: BackgroundTasks
    ) -> RunResponse:
        models = application.state.supported_models
        if models and request.model_id not in models:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported model_id '{request.model_id}'",
            )

        run_id = str(uuid4())
        created_at = utc_now()
        config = request.model_dump(mode="json")
        database.create_run(
            {
                "run_id": run_id,
                "status": RunStatus.QUEUED.value,
                "model_id": request.model_id,
                "dataset_id": request.dataset_id,
                "config": config,
                "created_at": created_at,
            }
        )
        background_tasks.add_task(execute_run, run_id, request)
        return RunResponse(
            run_id=run_id,
            status=RunStatus.QUEUED,
            model_id=request.model_id,
            dataset_id=request.dataset_id,
            created_at=datetime.fromisoformat(created_at),
        )

    @application.get("/api/v1/runs", response_model=RunListResponse)
    def list_runs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> RunListResponse:
        rows, total = database.list_runs(limit, offset)
        return RunListResponse(
            runs=[RunResponse(**row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    @application.get("/api/v1/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str) -> RunResponse:
        run = database.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        return RunResponse(**run)

    @application.get(
        "/api/v1/runs/{run_id}/report", response_model=ReportResponse
    )
    def get_report(run_id: str) -> ReportResponse:
        run = database.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        report = database.get_report(run_id)
        if report is None:
            raise HTTPException(
                status_code=409,
                detail=f"Report is not available for a {run['status']} run",
            )
        return ReportResponse(**report)

    return application


app = create_app()
