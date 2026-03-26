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
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_request_id: Optional[str] = None
    llm_response_id: Optional[str] = None
    prompt_version: Optional[str] = None
    normalization_version: Optional[str] = None
    schema_version: Optional[str] = None


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


class NormalizationNote(BaseModel):
    path: str
    message: str
    original_value: Optional[Any] = None
    normalized_value: Optional[Any] = None


class ValidationReport(BaseModel):
    valid: bool
    schema_errors: List[str] = Field(default_factory=list)
    semantic_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    normalization_notes: List[NormalizationNote] = Field(default_factory=list)


class UnknownField(BaseModel):
    field: str
    reason: str
    question_hint: str = ""
    location: Optional[str] = None


class NsmResultResponse(BaseModel):
    job: JobState
    nsm: Optional[Dict[str, Any]] = None
    unknowns: List[UnknownField] = Field(default_factory=list)
    confidence: Optional[float] = None
    provenance: Optional[Dict[str, Any]] = None
    validation: Optional[ValidationReport] = None


class RawOutputResponse(BaseModel):
    job: JobState
    raw_output: Optional[str] = None


class ErrorsResponse(BaseModel):
    job: JobState
    errors: List[ExtractionIssue] = Field(default_factory=list)
    unknowns: List[UnknownField] = Field(default_factory=list)
    validation: Optional[ValidationReport] = None


class InputErrorResponse(BaseModel):
    errors: List[ExtractionIssue] = Field(default_factory=list)
