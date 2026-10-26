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


class DatasetMetadata(BaseModel):
    id: str
    name: str
    description: str
    image_count: int
    has_ground_truth: bool = False
    supported: bool = True


class DatasetsResponse(BaseModel):
    datasets: list[DatasetMetadata]


class ArtifactItem(BaseModel):
    artifact_id: str
    run_id: str
    image_id: str
    artifact_type: str
    corruption: str | None = None
    severity: int | None = None
    mime_type: str = "image/jpeg"
    available: bool = True
    details: str | None = None


class RunArtifactsResponse(BaseModel):
    run_id: str
    artifacts: list[ArtifactItem]
    total: int

