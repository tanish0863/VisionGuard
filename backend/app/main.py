
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.app.contracts import EvalConfig, EvaluationReport
from backend.app.database import (
    DatabaseUnavailableError,
    RunDatabase,
)
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def configured_models() -> list[str]:
    values = os.getenv("VISIONGUARD_SUPPORTED_MODELS", "")
    return sorted({value.strip() for value in values.split(",") if value.strip()})


def create_app(
    database_url: str | None = None,
    database: RunDatabase | None = None,
    evaluator: Callable[..., EvaluationReport] | None = None,
    supported_models: list[str] | None = None,
) -> FastAPI:
    models = configured_models() if supported_models is None else supported_models

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        run_database = database or (
            RunDatabase(database_url)
            if database_url is not None
            else RunDatabase.from_environment()
        )
        application.state.database = run_database
        try:
            run_database.check_connection()
            run_database.fail_incomplete_runs(utc_now())
        except DatabaseUnavailableError:
            logger.error(
                "Database startup check failed; verify DATABASE_URL, connectivity, and migrations"
            )
            run_database.dispose()
            raise RuntimeError(
                "Could not initialize the database. Check DATABASE_URL and apply migrations."
            ) from None
        try:
            yield
        finally:
            run_database.dispose()

    application = FastAPI(
        title="VisionGuard API",
        description="Backend API for the VisionGuard model evaluation platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.supported_models = models

    @application.exception_handler(DatabaseUnavailableError)
    async def database_error_handler(
        request: Request, error: DatabaseUnavailableError
    ) -> JSONResponse:
        _ = (request, error)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database is temporarily unavailable"},
        )

    def execute_run(run_id: str, config: EvalConfig) -> None:
        run_database: RunDatabase = application.state.database
        try:
            run_database.start_run(run_id, utc_now())
        except DatabaseUnavailableError:
            logger.error("Could not start evaluation run %s due to database error", run_id)
            return
        try:
            evaluator_function = evaluator if evaluator is not None else get_evaluator()
            result = evaluator_function(config, run_id=run_id)
            report = EvaluationReport.model_validate(result)
            if report.run_id != run_id:
                raise ValueError("Evaluator report run_id does not match the requested run")
            report_json = json.loads(report.model_dump_json())
        except Exception:
            logger.exception("Evaluation run %s failed", run_id)
            run_database.fail_run(
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
        run_database.complete_run(
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
    def health_check(request: Request) -> dict[str, str]:
        request.app.state.database.check_connection()
        return {
            "status": "healthy",
            "service": "VisionGuard API",
            "database": "connected",
        }

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
        database: RunDatabase = application.state.database
        database.create_run(
            {
                "run_id": run_id,
                "status": RunStatus.QUEUED.value,
                "model_id": request.model_id,
                "dataset_id": request.dataset_id,
                "config": config,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
        background_tasks.add_task(execute_run, run_id, request)
        return RunResponse(
            run_id=run_id,
            status=RunStatus.QUEUED,
            model_id=request.model_id,
            dataset_id=request.dataset_id,
            created_at=created_at,
        )

    @application.get("/api/v1/runs", response_model=RunListResponse)
    def list_runs(
        request: Request,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> RunListResponse:
        database: RunDatabase = request.app.state.database
        rows, total = database.list_runs(limit, offset)
        return RunListResponse(
            runs=[RunResponse(**row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    @application.get("/api/v1/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str, request: Request) -> RunResponse:
        database: RunDatabase = request.app.state.database
        run = database.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        return RunResponse(**run)

    @application.get(
        "/api/v1/runs/{run_id}/report", response_model=ReportResponse
    )
    def get_report(run_id: str, request: Request) -> ReportResponse:
        database: RunDatabase = request.app.state.database
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
