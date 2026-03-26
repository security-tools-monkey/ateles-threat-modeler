from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..models.api import ExtractionIssue, JobStatus


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
    raw_output: Optional[str] = None
    normalized_output: Optional[Dict[str, Any]] = None
    nsm: Optional[Dict[str, Any]] = None
    validation_report: Optional[Dict[str, Any]] = None
    errors: List[ExtractionIssue] = field(default_factory=list)
    unknowns: List[Dict[str, Any]] = field(default_factory=list)
    confidence: Optional[float] = None
    provenance: Optional[Dict[str, Any]] = None


class InMemoryJobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}

    def create_job(self, input_filename: Optional[str] = None) -> JobRecord:
        now = datetime.now(timezone.utc)
        job_id = str(uuid4())
        job = JobRecord(
            job_id=job_id,
            status=JobStatus.accepted,
            created_at=now,
            updated_at=now,
            input_filename=input_filename,
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **updates: Any) -> Optional[JobRecord]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        for key, value in updates.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(timezone.utc)
        return job

    def set_status(self, job_id: str, status: JobStatus) -> Optional[JobRecord]:
        return self.update_job(job_id, status=status)
