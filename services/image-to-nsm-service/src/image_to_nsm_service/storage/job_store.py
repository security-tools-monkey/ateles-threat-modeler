from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass(frozen=True)
class JobRow:
    job_id: str
    status: str
    created_at: str
    updated_at: str
    request_id: Optional[str]
    correlation_id: Optional[str]
    processing_started_at: Optional[str]
    processing_completed_at: Optional[str]
    input_filename: Optional[str]
    input_content_type: Optional[str]
    input_size_bytes: Optional[int]
    input_context: Optional[str]
    errors_json: Optional[str]
    unknowns_json: Optional[str]
    confidence: Optional[float]
    provenance_json: Optional[str]
    llm_provider: Optional[str]
    llm_model: Optional[str]
    llm_request_id: Optional[str]
    llm_response_id: Optional[str]
    prompt_version: Optional[str]
    normalization_version: Optional[str]
    schema_version: Optional[str]


@dataclass(frozen=True)
class ArtifactRow:
    artifact_type: str
    path: str
    content_type: Optional[str]
    size_bytes: Optional[int]
    created_at: str
    metadata_json: Optional[str]


@dataclass(frozen=True)
class JobLogRow:
    timestamp: str
    level: str
    message: str


class JobStore(Protocol):
    def insert_job(self, job_id: str, status: str, created_at: str, updated_at: str, input_filename: str | None) -> None:
        ...

    def get_job(self, job_id: str) -> Optional[JobRow]:
        ...

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        ...

    def upsert_artifact(self, job_id: str, artifact: ArtifactRow) -> None:
        ...

    def list_artifacts(self, job_id: str) -> Dict[str, ArtifactRow]:
        ...

    def insert_log(self, job_id: str, entry: JobLogRow) -> None:
        ...

    def list_logs(self, job_id: str) -> List[JobLogRow]:
        ...


class SqliteJobStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def insert_job(self, job_id: str, status: str, created_at: str, updated_at: str, input_filename: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, status, created_at, updated_at, input_filename)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, status, created_at, updated_at, input_filename),
            )

    def get_job(self, job_id: str) -> Optional[JobRow]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return JobRow(
            job_id=row["job_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            request_id=row["request_id"],
            correlation_id=row["correlation_id"],
            processing_started_at=row["processing_started_at"],
            processing_completed_at=row["processing_completed_at"],
            input_filename=row["input_filename"],
            input_content_type=row["input_content_type"],
            input_size_bytes=row["input_size_bytes"],
            input_context=row["input_context"],
            errors_json=row["errors_json"],
            unknowns_json=row["unknowns_json"],
            confidence=row["confidence"],
            provenance_json=row["provenance_json"],
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            llm_request_id=row["llm_request_id"],
            llm_response_id=row["llm_response_id"],
            prompt_version=row["prompt_version"],
            normalization_version=row["normalization_version"],
            schema_version=row["schema_version"],
        )

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        fields = []
        values: List[Any] = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.append(job_id)
        statement = f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?"
        with self._connect() as conn:
            conn.execute(statement, values)

    def upsert_artifact(self, job_id: str, artifact: ArtifactRow) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_artifacts (
                    job_id, artifact_type, path, content_type, size_bytes, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, artifact_type) DO UPDATE SET
                    path = excluded.path,
                    content_type = excluded.content_type,
                    size_bytes = excluded.size_bytes,
                    created_at = excluded.created_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    job_id,
                    artifact.artifact_type,
                    artifact.path,
                    artifact.content_type,
                    artifact.size_bytes,
                    artifact.created_at,
                    artifact.metadata_json,
                ),
            )

    def list_artifacts(self, job_id: str) -> Dict[str, ArtifactRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT artifact_type, path, content_type, size_bytes, created_at, metadata_json
                FROM job_artifacts WHERE job_id = ?
                """,
                (job_id,),
            ).fetchall()
        artifacts: Dict[str, ArtifactRow] = {}
        for row in rows:
            artifacts[row["artifact_type"]] = ArtifactRow(
                artifact_type=row["artifact_type"],
                path=row["path"],
                content_type=row["content_type"],
                size_bytes=row["size_bytes"],
                created_at=row["created_at"],
                metadata_json=row["metadata_json"],
            )
        return artifacts

    def insert_log(self, job_id: str, entry: JobLogRow) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_logs (job_id, timestamp, level, message)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, entry.timestamp, entry.level, entry.message),
            )

    def list_logs(self, job_id: str) -> List[JobLogRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT timestamp, level, message FROM job_logs WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            ).fetchall()
        return [
            JobLogRow(timestamp=row["timestamp"], level=row["level"], message=row["message"])
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    request_id TEXT,
                    correlation_id TEXT,
                    processing_started_at TEXT,
                    processing_completed_at TEXT,
                    input_filename TEXT,
                    input_content_type TEXT,
                    input_size_bytes INTEGER,
                    input_context TEXT,
                    errors_json TEXT,
                    unknowns_json TEXT,
                    confidence REAL,
                    provenance_json TEXT,
                    llm_provider TEXT,
                    llm_model TEXT,
                    llm_request_id TEXT,
                    llm_response_id TEXT,
                    prompt_version TEXT,
                    normalization_version TEXT,
                    schema_version TEXT
                );
                CREATE TABLE IF NOT EXISTS job_artifacts (
                    job_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content_type TEXT,
                    size_bytes INTEGER,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT,
                    PRIMARY KEY (job_id, artifact_type)
                );
                CREATE TABLE IF NOT EXISTS job_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        expected = {
            "request_id": "TEXT",
            "correlation_id": "TEXT",
            "processing_started_at": "TEXT",
            "processing_completed_at": "TEXT",
            "llm_provider": "TEXT",
            "llm_model": "TEXT",
            "llm_request_id": "TEXT",
            "llm_response_id": "TEXT",
            "prompt_version": "TEXT",
            "normalization_version": "TEXT",
            "schema_version": "TEXT",
        }
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        for column, column_type in expected.items():
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {column_type}")

        artifact_expected = {
            "metadata_json": "TEXT",
        }
        artifact_existing = {
            row["name"] for row in conn.execute("PRAGMA table_info(job_artifacts)").fetchall()
        }
        for column, column_type in artifact_expected.items():
            if column in artifact_existing:
                continue
            conn.execute(f"ALTER TABLE job_artifacts ADD COLUMN {column} {column_type}")


def serialize_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def serialize_errors(errors: Iterable[Any]) -> Optional[str]:
    payload = []
    for error in errors:
        if hasattr(error, "model_dump"):
            payload.append(error.model_dump())
        elif isinstance(error, dict):
            payload.append(error)
    return serialize_json(payload)


def serialize_unknowns(unknowns: Iterable[Any]) -> Optional[str]:
    payload = []
    for unknown in unknowns:
        if hasattr(unknown, "model_dump"):
            payload.append(unknown.model_dump())
        elif isinstance(unknown, dict):
            payload.append(unknown)
    return serialize_json(payload)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
