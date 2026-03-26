from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from ..models.api import JobStatus
from .models import JobRecord, ProcessingLogEntry


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
        job = self.update_job(job_id, status=status)
        if job is not None:
            self.append_log(job_id, "info", f"Status set to {status.value}.")
        return job

    def append_log(self, job_id: str, level: str, message: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.logs.append(
            ProcessingLogEntry(
                timestamp=datetime.now(timezone.utc),
                level=level,
                message=message,
            )
        )
