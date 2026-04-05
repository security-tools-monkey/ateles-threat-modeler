from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from ..models.api import ExtractionIssue, JobStatus
from ..storage.artifacts import ArtifactStorage
from ..storage.job_store import (
    ArtifactRow,
    JobLogRow,
    JobStore,
    serialize_errors,
    serialize_json,
    serialize_unknowns,
    utc_now_iso,
)
from .metadata import build_artifact_metadata, format_log_message
from .models import ArtifactMetadata, JobRecord, ProcessingLogEntry


class PersistentJobManager:
    def __init__(self, store: JobStore, artifacts: ArtifactStorage) -> None:
        self._store = store
        self._artifacts = artifacts

    def create_job(self, input_filename: Optional[str] = None) -> JobRecord:
        now = datetime.now(timezone.utc)
        job_id = str(uuid4())
        self._store.insert_job(job_id, JobStatus.accepted.value, now.isoformat(), now.isoformat(), input_filename)
        self.append_log(job_id, "info", f"job_id={job_id} job created.")
        return JobRecord(job_id=job_id, status=JobStatus.accepted, created_at=now, updated_at=now, input_filename=input_filename)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        row = self._store.get_job(job_id)
        if row is None:
            return None
        artifacts = self._store.list_artifacts(job_id)
        artifact_metadata = _parse_artifact_metadata(artifacts)
        raw_output_path = _artifact_path(artifacts, "raw_llm_output")
        normalized_path = _artifact_path(artifacts, "normalized_nsm")
        nsm_path = _artifact_path(artifacts, "final_nsm")
        validation_path = _artifact_path(artifacts, "validation_report")
        input_image_path = _artifact_path(artifacts, "input_image")
        raw_output = self._artifacts.read_text(raw_output_path) if raw_output_path else None
        normalized_output = self._artifacts.read_json(normalized_path) if normalized_path else None
        nsm = self._artifacts.read_json(nsm_path) if nsm_path else None
        validation_report = self._artifacts.read_json(validation_path) if validation_path else None
        errors = _parse_errors(row.errors_json)
        unknowns = _parse_unknowns(row.unknowns_json)
        provenance = _parse_json(row.provenance_json)
        logs = _parse_logs(self._store.list_logs(job_id))
        return JobRecord(
            job_id=row.job_id,
            status=_parse_status(row.status),
            created_at=_parse_datetime(row.created_at),
            updated_at=_parse_datetime(row.updated_at),
            request_id=row.request_id,
            correlation_id=row.correlation_id,
            processing_started_at=_parse_optional_datetime(row.processing_started_at),
            processing_completed_at=_parse_optional_datetime(row.processing_completed_at),
            input_filename=row.input_filename,
            input_content_type=row.input_content_type,
            input_size_bytes=row.input_size_bytes,
            input_context=row.input_context,
            input_image_path=input_image_path,
            raw_output=raw_output,
            raw_output_path=raw_output_path,
            normalized_output=normalized_output,
            normalized_output_path=normalized_path,
            nsm=nsm,
            nsm_path=nsm_path,
            validation_report=validation_report,
            validation_report_path=validation_path,
            errors=errors,
            unknowns=unknowns,
            confidence=row.confidence,
            provenance=provenance,
            llm_provider=row.llm_provider,
            llm_model=row.llm_model,
            llm_request_id=row.llm_request_id,
            llm_response_id=row.llm_response_id,
            prompt_version=row.prompt_version,
            normalization_version=row.normalization_version,
            schema_version=row.schema_version,
            artifacts=artifact_metadata,
            logs=logs,
        )

    def update_job(self, job_id: str, **updates: Any) -> Optional[JobRecord]:
        artifact_updates: Dict[str, ArtifactRow] = {}
        metadata_updates: Dict[str, Any] = {}
        base_metadata = _base_metadata(self._store.get_job(job_id))
        artifact_metadata = build_artifact_metadata(base_metadata, updates)
        if "input_image_bytes" in updates:
            stored = self._artifacts.store_bytes(
                job_id,
                "input_image",
                updates.pop("input_image_bytes"),
                filename=updates.get("input_filename"),
                content_type=updates.get("input_content_type"),
            )
            artifact_updates["input_image"] = _to_artifact_row(stored, artifact_metadata)
        if "raw_output" in updates:
            raw_output = updates.pop("raw_output")
            if raw_output is not None:
                stored = self._artifacts.store_text(
                    job_id,
                    "raw_llm_output",
                    raw_output,
                    suffix=".json",
                )
                artifact_updates["raw_llm_output"] = _to_artifact_row(stored, artifact_metadata)
        if "normalized_output" in updates:
            normalized = updates.pop("normalized_output")
            if normalized is not None:
                stored = self._artifacts.store_json(job_id, "normalized_nsm", normalized)
                artifact_updates["normalized_nsm"] = _to_artifact_row(stored, artifact_metadata)
        if "nsm" in updates:
            nsm = updates.pop("nsm")
            if nsm is not None:
                stored = self._artifacts.store_json(job_id, "final_nsm", nsm)
                artifact_updates["final_nsm"] = _to_artifact_row(stored, artifact_metadata)
        if "validation_report" in updates:
            report = updates.pop("validation_report")
            if report is not None:
                stored = self._artifacts.store_json(job_id, "validation_report", report)
                artifact_updates["validation_report"] = _to_artifact_row(stored, artifact_metadata)

        if "errors" in updates:
            errors = updates.pop("errors")
            metadata_updates["errors_json"] = serialize_errors(errors) if errors is not None else None
        if "unknowns" in updates:
            unknowns = updates.pop("unknowns")
            metadata_updates["unknowns_json"] = (
                serialize_unknowns(unknowns) if unknowns is not None else None
            )
        if "provenance" in updates:
            provenance = updates.pop("provenance")
            metadata_updates["provenance_json"] = serialize_json(provenance)

        for key in (
            "status",
            "request_id",
            "correlation_id",
            "processing_started_at",
            "processing_completed_at",
            "input_filename",
            "input_content_type",
            "input_size_bytes",
            "input_context",
            "confidence",
            "llm_provider",
            "llm_model",
            "llm_request_id",
            "llm_response_id",
            "prompt_version",
            "normalization_version",
            "schema_version",
        ):
            if key in updates:
                value = updates.pop(key)
                if isinstance(value, datetime):
                    metadata_updates[key] = value.isoformat()
                else:
                    metadata_updates[key] = value.value if isinstance(value, JobStatus) else value

        metadata_updates["updated_at"] = utc_now_iso()
        self._store.update_job(job_id, metadata_updates)

        for artifact in artifact_updates.values():
            self._store.upsert_artifact(job_id, artifact)

        if "status" in metadata_updates:
            request_id = metadata_updates.get("request_id") or base_metadata.get("request_id")
            correlation_id = metadata_updates.get("correlation_id") or base_metadata.get("correlation_id")
            message = format_log_message(
                job_id=job_id,
                request_id=request_id,
                correlation_id=correlation_id,
                message=f"status set to {metadata_updates['status']}.",
            )
            self.append_log(job_id, "info", message)

        return self.get_job(job_id)

    def set_status(self, job_id: str, status: JobStatus) -> Optional[JobRecord]:
        return self.update_job(job_id, status=status)

    def append_log(self, job_id: str, level: str, message: str) -> None:
        entry = JobLogRow(timestamp=utc_now_iso(), level=level, message=message)
        self._store.insert_log(job_id, entry)


def _artifact_path(artifacts: Dict[str, ArtifactRow], artifact_type: str) -> Optional[str]:
    artifact = artifacts.get(artifact_type)
    return artifact.path if artifact else None


def _to_artifact_row(stored, metadata: Dict[str, Any]) -> ArtifactRow:
    return ArtifactRow(
        artifact_type=stored.artifact_type,
        path=stored.path,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        created_at=utc_now_iso(),
        metadata_json=serialize_json(metadata),
    )


def _parse_datetime(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_optional_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return _parse_datetime(raw)


def _parse_status(raw: str) -> JobStatus:
    try:
        return JobStatus(raw)
    except ValueError:
        return JobStatus.failed


def _parse_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value}


def _parse_errors(raw: Optional[str]) -> list[ExtractionIssue]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    errors = []
    for item in payload:
        if isinstance(item, dict):
            errors.append(ExtractionIssue(**item))
    return errors


def _parse_unknowns(raw: Optional[str]) -> list[Dict[str, Any]]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _parse_logs(rows: Iterable[JobLogRow]) -> list[ProcessingLogEntry]:
    return [
        ProcessingLogEntry(
            timestamp=_parse_datetime(row.timestamp),
            level=row.level,
            message=row.message,
        )
        for row in rows
    ]


def _parse_artifact_metadata(artifacts: Dict[str, ArtifactRow]) -> Dict[str, ArtifactMetadata]:
    parsed: Dict[str, ArtifactMetadata] = {}
    for artifact_type, artifact in artifacts.items():
        metadata = _parse_json(artifact.metadata_json) or {}
        parsed[artifact_type] = ArtifactMetadata(
            artifact_type=artifact.artifact_type,
            path=artifact.path,
            content_type=artifact.content_type,
            size_bytes=artifact.size_bytes,
            created_at=_parse_datetime(artifact.created_at),
            metadata=metadata,
        )
    return parsed


def _base_metadata(row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "request_id": row.request_id,
        "correlation_id": row.correlation_id,
        "llm_provider": row.llm_provider,
        "llm_model": row.llm_model,
        "prompt_version": row.prompt_version,
        "normalization_version": row.normalization_version,
        "schema_version": row.schema_version,
    }
