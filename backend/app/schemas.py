from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_id: str = Field(min_length=1, max_length=100)
    dataset_id: str = Field(min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("model_id", "dataset_id")
    @classmethod
    def strip_identifiers(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


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
    report: dict[str, Any]
