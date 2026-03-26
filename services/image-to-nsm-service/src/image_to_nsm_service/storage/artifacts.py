from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol


@dataclass(frozen=True)
class StoredArtifact:
    artifact_type: str
    path: str
    size_bytes: int
    content_type: Optional[str] = None


class ArtifactStorage(Protocol):
    def store_bytes(
        self,
        job_id: str,
        artifact_type: str,
        data: bytes,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> StoredArtifact:
        ...

    def store_text(self, job_id: str, artifact_type: str, text: str) -> StoredArtifact:
        ...

    def store_json(self, job_id: str, artifact_type: str, payload: Any) -> StoredArtifact:
        ...

    def read_bytes(self, path: str) -> Optional[bytes]:
        ...

    def read_text(self, path: str) -> Optional[str]:
        ...

    def read_json(self, path: str) -> Optional[Dict[str, Any]]:
        ...


class LocalArtifactStorage:
    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def store_bytes(
        self,
        job_id: str,
        artifact_type: str,
        data: bytes,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> StoredArtifact:
        resolved_suffix = suffix or _infer_suffix(filename, content_type)
        path = self._resolve_path(job_id, artifact_type, resolved_suffix)
        path.write_bytes(data)
        return StoredArtifact(
            artifact_type=artifact_type,
            path=str(path),
            size_bytes=len(data),
            content_type=content_type,
        )

    def store_text(self, job_id: str, artifact_type: str, text: str) -> StoredArtifact:
        data = text.encode("utf-8")
        path = self._resolve_path(job_id, artifact_type, ".txt")
        path.write_bytes(data)
        return StoredArtifact(artifact_type=artifact_type, path=str(path), size_bytes=len(data))

    def store_json(self, job_id: str, artifact_type: str, payload: Any) -> StoredArtifact:
        serialized = json.dumps(payload, sort_keys=True, indent=2)
        data = f"{serialized}\n".encode("utf-8")
        path = self._resolve_path(job_id, artifact_type, ".json")
        path.write_bytes(data)
        return StoredArtifact(artifact_type=artifact_type, path=str(path), size_bytes=len(data))

    def read_bytes(self, path: str) -> Optional[bytes]:
        target = Path(path)
        if not target.exists():
            return None
        return target.read_bytes()

    def read_text(self, path: str) -> Optional[str]:
        target = Path(path)
        if not target.exists():
            return None
        return target.read_text(encoding="utf-8")

    def read_json(self, path: str) -> Optional[Dict[str, Any]]:
        raw = self.read_text(path)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    def _resolve_path(self, job_id: str, artifact_type: str, suffix: str) -> Path:
        safe_job = _safe_token(job_id)
        safe_type = _safe_token(artifact_type)
        filename = f"{safe_type}{suffix}" if suffix else safe_type
        path = self._root / safe_job / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


_SAFE_TOKEN = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_token(value: str) -> str:
    cleaned = _SAFE_TOKEN.sub("_", value.strip())
    return cleaned or "unknown"


def _infer_suffix(filename: Optional[str], content_type: Optional[str]) -> str:
    if filename:
        suffix = Path(filename).suffix
        if suffix:
            return suffix.lower()
    if content_type:
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
        }
        return mapping.get(content_type.lower(), "")
    return ""
