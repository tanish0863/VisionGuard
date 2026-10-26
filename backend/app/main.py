from __future__ import annotations

import json
import logging
import os

# Prevent OpenBLAS/MKL/OMP thread buffer exhaustion on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.artifacts import get_artifact_content, list_run_artifacts
from backend.app.storage import (
    ArtifactStorage,
    StorageObjectNotFoundError,
    StorageSecurityError,
    get_artifact_storage,
    validate_storage_key,
)
from backend.app.config import (
    ALLOW_CORS_CREDENTIALS,
    ALLOWED_CORS_HEADERS,
    ALLOWED_CORS_METHODS,
    configured_cors_origins,
    configured_models,
)
from backend.app.contracts import EvalConfig, EvaluationReport
from backend.app.database import (
    DatabaseUnavailableError,
    RunDatabase,
)
from backend.app.evaluation_adapter import get_evaluator
from backend.app.execution import (
    BackgroundTasksDispatcher,
    JobDispatcher,
)
from backend.app.schemas import (
    ArtifactDownloadUrlResponse,
    DatasetsResponse,
    ModelsResponse,
    ReportResponse,
    RunArtifactsResponse,
    RunCreateRequest,
    RunListResponse,
    RunResponse,
    RunStatus,
)
from backend.visionguard.core.pipeline import get_registered_datasets

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    database_url: str | None = None,
    database: RunDatabase | None = None,
    evaluator: Callable[..., EvaluationReport] | None = None,
    supported_models: list[str] | None = None,
    cors_origins: list[str] | None = None,
    dispatcher: JobDispatcher | None = None,
    storage: ArtifactStorage | None = None,
) -> FastAPI:
    models = configured_models() if supported_models is None else supported_models
    origins = configured_cors_origins() if cors_origins is None else cors_origins

    dispatcher_mode = os.getenv("VISIONGUARD_DISPATCHER", "background").strip().lower()
    if dispatcher_mode not in {"background", "worker"}:
        raise ValueError(
            f"Invalid VISIONGUARD_DISPATCHER '{dispatcher_mode}'; must be 'background' or 'worker'"
        )

    resolved_dispatcher: JobDispatcher | None = dispatcher
    if resolved_dispatcher is None and dispatcher_mode == "worker":
        from backend.app.execution import WorkerCliDispatcher
        resolved_dispatcher = WorkerCliDispatcher()

    resolved_storage: ArtifactStorage = storage if storage is not None else get_artifact_storage()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        run_database = database or (
            RunDatabase(database_url)
            if database_url is not None
            else RunDatabase.from_environment()
        )
        application.state.database = run_database
        application.state.dispatcher = resolved_dispatcher
        application.state.dispatcher_mode = dispatcher_mode
        application.state.evaluator = evaluator
        application.state.storage = resolved_storage
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
    application.state.dispatcher = resolved_dispatcher
    application.state.dispatcher_mode = dispatcher_mode
    application.state.evaluator = evaluator

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=ALLOW_CORS_CREDENTIALS,
        allow_methods=ALLOWED_CORS_METHODS,
        allow_headers=ALLOWED_CORS_HEADERS,
    )

    @application.exception_handler(DatabaseUnavailableError)
    async def database_error_handler(
        request: Request, error: DatabaseUnavailableError
    ) -> JSONResponse:
        _ = (request, error)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database is temporarily unavailable"},
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

    @application.get("/api/v1/datasets", response_model=DatasetsResponse)
    def list_datasets() -> DatasetsResponse:
        datasets_list = get_registered_datasets()
        return DatasetsResponse(datasets=datasets_list)

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

        available_datasets = {
            d["id"] for d in get_registered_datasets() if d.get("supported")
        }
        if available_datasets and request.dataset_id not in available_datasets:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported or unregistered dataset_id '{request.dataset_id}'",
            )

        run_id = str(uuid4())
        created_at = utc_now()
        config = request.model_dump(mode="json")
        database_inst: RunDatabase = application.state.database
        database_inst.create_run(
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

        job_dispatcher = application.state.dispatcher
        if job_dispatcher is not None:
            job_dispatcher.submit_evaluation(run_id)
        else:
            BackgroundTasksDispatcher(
                database=database_inst,
                evaluator=application.state.evaluator,
                background_tasks=background_tasks,
            ).submit_evaluation(run_id)

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
        database_inst: RunDatabase = request.app.state.database
        rows, total = database_inst.list_runs(limit, offset)
        return RunListResponse(
            runs=[RunResponse(**row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    @application.get("/api/v1/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str, request: Request) -> RunResponse:
        database_inst: RunDatabase = request.app.state.database
        run = database_inst.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        return RunResponse(**run)

    @application.get(
        "/api/v1/runs/{run_id}/report", response_model=ReportResponse
    )
    def get_report(run_id: str, request: Request) -> ReportResponse:
        database_inst: RunDatabase = request.app.state.database
        run = database_inst.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        report = database_inst.get_report(run_id)
        if report is None:
            raise HTTPException(
                status_code=409,
                detail=f"Report is not available for a {run['status']} run",
            )
        return ReportResponse(**report)

    @application.get(
        "/api/v1/runs/{run_id}/artifacts", response_model=RunArtifactsResponse
    )
    def list_artifacts(run_id: str, request: Request) -> RunArtifactsResponse:
        database_inst: RunDatabase = request.app.state.database
        run = database_inst.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        report_data = database_inst.get_report(run_id)
        if report_data is None:
            raise HTTPException(
                status_code=409,
                detail=f"Artifacts are not available for a {run['status']} run",
            )
        storage_inst = getattr(request.app.state, "storage", None)
        artifacts = list_run_artifacts(
            run_id, report_data, storage=storage_inst, database=database_inst
        )
        return RunArtifactsResponse(
            run_id=run_id, artifacts=artifacts, total=len(artifacts)
        )

    @application.get("/api/v1/runs/{run_id}/artifacts/{artifact_id}")
    def get_artifact(run_id: str, artifact_id: str, request: Request) -> Response:
        database_inst: RunDatabase = request.app.state.database
        run = database_inst.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")
        report_data = database_inst.get_report(run_id)
        if report_data is None:
            raise HTTPException(
                status_code=409,
                detail=f"Artifacts are not available for a {run['status']} run",
            )
        storage_inst = getattr(request.app.state, "storage", None)
        try:
            content, mime_type = get_artifact_content(
                run_id, artifact_id, report_data, storage=storage_inst, database=database_inst
            )
        except NotImplementedError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return Response(
            content=content,
            media_type=mime_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @application.get("/api/v1/artifacts/{artifact_path:path}")
    def get_raw_artifact(artifact_path: str, request: Request) -> Response:
        """Stream artifact by storage object key (used for local filesystem storage URLs)."""
        storage_inst = getattr(request.app.state, "storage", None) or get_artifact_storage()
        try:
            valid_key = validate_storage_key(artifact_path)
            content, mime_type = storage_inst.get_object(valid_key)
            return Response(
                content=content,
                media_type=mime_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )
        except (StorageObjectNotFoundError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="Artifact not found")
        except StorageSecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except Exception as exc:
            logger.error("Failed retrieving raw artifact '%s': %s", artifact_path, exc)
            raise HTTPException(status_code=500, detail="Internal storage error")


    @application.get(
        "/api/v1/runs/{run_id}/artifacts/{artifact_id}/download-url",
        response_model=ArtifactDownloadUrlResponse,
    )
    @application.get(
        "/api/runs/{run_id}/artifacts/{artifact_id}/download-url",
        response_model=ArtifactDownloadUrlResponse,
        include_in_schema=False,
    )
    def get_artifact_download_url(
        run_id: str,
        artifact_id: str,
        request: Request,
        expires_in: int = Query(default=900, ge=60, le=86400),
    ) -> ArtifactDownloadUrlResponse:
        database_inst: RunDatabase = request.app.state.database
        run = database_inst.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Evaluation run not found")

        # Check database for existing artifact metadata record
        art_record = database_inst.get_artifact(run_id, artifact_id)
        if art_record:
            object_key = art_record["object_key"]
            file_name = art_record["file_name"]
        else:
            try:
                valid_art_id = validate_storage_key(artifact_id)
            except Exception as val_exc:
                raise HTTPException(status_code=400, detail=str(val_exc))
            object_key = f"runs/{run_id}/{valid_art_id}.jpg"
            file_name = f"{valid_art_id}.jpg"

        storage_inst = getattr(request.app.state, "storage", None) or get_artifact_storage()
        try:
            download_url = storage_inst.generate_presigned_url(object_key, expires_in=expires_in)
        except Exception as exc:
            logger.error("Failed to generate presigned download URL for key '%s': %s", object_key, exc)
            raise HTTPException(status_code=500, detail="Failed to generate download URL")

        return ArtifactDownloadUrlResponse(
            artifact_id=artifact_id,
            file_name=file_name,
            download_url=download_url,
            expires_in=expires_in,
        )

    @application.post("/api/v1/runs/recover-stale")
    def recover_stale(
        request: Request,
        lease_timeout: float = Query(default=60.0, ge=5.0, le=3600.0),
        max_attempts: int = Query(default=3, ge=1, le=10),
    ) -> dict[str, int]:
        database_inst: RunDatabase = request.app.state.database
        result = database_inst.recover_stale_runs(
            now=utc_now(),
            lease_timeout_seconds=lease_timeout,
            max_attempts=max_attempts,
        )
        return result

    return application


app = create_app()
