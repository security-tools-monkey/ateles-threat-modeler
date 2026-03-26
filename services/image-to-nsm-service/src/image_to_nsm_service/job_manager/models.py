from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.api import ExtractionIssue, JobStatus


@dataclass(frozen=True)
class ProcessingLogEntry:
    timestamp: datetime
    level: str
    message: str


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    input_filename: Optional[str] = None
    input_content_type: Optional[str] = None
    input_size_bytes: Optional[int] = None
    input_context: Optional[str] = None
    input_image_bytes: Optional[bytes] = None
    input_image_path: Optional[str] = None
    raw_output: Optional[str] = None
    raw_output_path: Optional[str] = None
    normalized_output: Optional[Dict[str, Any]] = None
    normalized_output_path: Optional[str] = None
    nsm: Optional[Dict[str, Any]] = None
    nsm_path: Optional[str] = None
    validation_report: Optional[Dict[str, Any]] = None
    validation_report_path: Optional[str] = None
    errors: List[ExtractionIssue] = field(default_factory=list)
    unknowns: List[Dict[str, Any]] = field(default_factory=list)
    confidence: Optional[float] = None
    provenance: Optional[Dict[str, Any]] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_request_id: Optional[str] = None
    llm_response_id: Optional[str] = None
    prompt_version: Optional[str] = None
    normalization_version: Optional[str] = None
    schema_version: Optional[str] = None
    logs: List[ProcessingLogEntry] = field(default_factory=list)
