from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from image_to_nsm_service.models.api import ExtractionIssue, JobStatus


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    input_filename: Optional[str] = None
    raw_output: Optional[str] = None
    nsm: Optional[Dict[str, Any]] = None
    errors: List[ExtractionIssue] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
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
