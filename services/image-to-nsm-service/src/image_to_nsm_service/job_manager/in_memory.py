from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from ..models.api import JobStatus
from .metadata import build_artifact_metadata, format_log_message
from .models import ArtifactMetadata, JobRecord, ProcessingLogEntry


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
        metadata = build_artifact_metadata(job.__dict__, updates)
        now = datetime.now(timezone.utc)
        if "input_image_bytes" in updates:
            data = updates.get("input_image_bytes")
            content_type = updates.get("input_content_type") or job.input_content_type
            size_bytes = len(data) if isinstance(data, (bytes, bytearray)) else None
            job.artifacts["input_image"] = ArtifactMetadata(
                artifact_type="input_image",
                path=None,
                content_type=content_type,
                size_bytes=size_bytes,
                created_at=now,
                metadata=metadata,
            )
        if "raw_output" in updates:
            raw_output = updates.get("raw_output")
            if isinstance(raw_output, str):
                size_bytes = len(raw_output.encode("utf-8"))
                job.artifacts["raw_llm_output"] = ArtifactMetadata(
                    artifact_type="raw_llm_output",
                    path=None,
                    content_type="text/plain",
                    size_bytes=size_bytes,
                    created_at=now,
                    metadata=metadata,
                )
        if "normalized_output" in updates:
            normalized = updates.get("normalized_output")
            if normalized is not None:
                size_bytes = _json_size_bytes(normalized)
                job.artifacts["normalized_nsm"] = ArtifactMetadata(
                    artifact_type="normalized_nsm",
                    path=None,
                    content_type="application/json",
                    size_bytes=size_bytes,
                    created_at=now,
                    metadata=metadata,
                )
        if "nsm" in updates:
            nsm = updates.get("nsm")
            if nsm is not None:
                size_bytes = _json_size_bytes(nsm)
                job.artifacts["final_nsm"] = ArtifactMetadata(
                    artifact_type="final_nsm",
                    path=None,
                    content_type="application/json",
                    size_bytes=size_bytes,
                    created_at=now,
                    metadata=metadata,
                )
        if "validation_report" in updates:
            report = updates.get("validation_report")
            if report is not None:
                size_bytes = _json_size_bytes(report)
                job.artifacts["validation_report"] = ArtifactMetadata(
                    artifact_type="validation_report",
                    path=None,
                    content_type="application/json",
                    size_bytes=size_bytes,
                    created_at=now,
                    metadata=metadata,
                )
        for key, value in updates.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(timezone.utc)
        return job

    def set_status(self, job_id: str, status: JobStatus) -> Optional[JobRecord]:
        job = self.update_job(job_id, status=status)
        if job is not None:
            message = format_log_message(
                job_id=job_id,
                request_id=job.request_id,
                correlation_id=job.correlation_id,
                message=f"status set to {status.value}.",
            )
            self.append_log(job_id, "info", message)
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


def _json_size_bytes(payload: Any) -> Optional[int]:
    if payload is None:
        return None
    try:
        serialized = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    except (TypeError, ValueError):
        return None
    return len(serialized.encode("utf-8"))
