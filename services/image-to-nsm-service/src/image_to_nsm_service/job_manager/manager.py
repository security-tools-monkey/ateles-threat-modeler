from __future__ import annotations

from typing import Any, Optional, Protocol

from ..models.api import JobStatus
from .models import JobRecord


class JobManager(Protocol):
    def create_job(self, input_filename: Optional[str] = None) -> JobRecord:
        ...

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        ...

    def update_job(self, job_id: str, **updates: Any) -> Optional[JobRecord]:
        ...

    def set_status(self, job_id: str, status: JobStatus) -> Optional[JobRecord]:
        ...

    def append_log(self, job_id: str, level: str, message: str) -> None:
        ...
