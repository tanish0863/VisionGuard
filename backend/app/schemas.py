from datetime import datetime

from pydantic import BaseModel

from backend.app.contracts import EvalConfig, EvaluationReport, RunStatus


class RunCreateRequest(EvalConfig):
    pass


class RunResponse(BaseModel):
    run_id: str
    status: RunStatus
    model_id: str
    dataset_id: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class RunListResponse(BaseModel):
    runs: list[RunResponse]
    total: int
    limit: int
    offset: int


class ModelsResponse(BaseModel):
    models: list[str]


class ReportResponse(BaseModel):
    run_id: str
    created_at: datetime
    report: EvaluationReport
