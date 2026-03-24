from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    accepted = "accepted"
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class ImageToNsmJobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job: JobState


class ExtractionIssue(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    severity: str = "info"


class NsmResultResponse(BaseModel):
    job: JobState
    nsm: Optional[Dict[str, Any]] = None
    unknowns: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    provenance: Optional[Dict[str, Any]] = None


class RawOutputResponse(BaseModel):
    job: JobState
    raw_output: Optional[str] = None


class ErrorsResponse(BaseModel):
    job: JobState
    errors: List[ExtractionIssue] = Field(default_factory=list)


class InputErrorResponse(BaseModel):
    errors: List[ExtractionIssue] = Field(default_factory=list)
