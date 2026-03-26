from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Mapping, Optional


_METADATA_KEYS = (
    "request_id",
    "correlation_id",
    "llm_provider",
    "llm_model",
    "prompt_version",
    "normalization_version",
    "schema_version",
)


def build_artifact_metadata(
    base: Optional[Mapping[str, Any]],
    updates: Mapping[str, Any],
) -> Dict[str, Any]:
    def _pick(key: str) -> Any:
        if key in updates:
            value = updates.get(key)
        else:
            value = base.get(key) if base else None
        if isinstance(value, Enum):
            return value.value
        return value

    return {key: _pick(key) for key in _METADATA_KEYS}


def format_log_message(
    *,
    job_id: str,
    request_id: Optional[str],
    correlation_id: Optional[str],
    message: str,
) -> str:
    parts = [f"job_id={job_id}"]
    if request_id:
        parts.append(f"request_id={request_id}")
    if correlation_id:
        parts.append(f"correlation_id={correlation_id}")
    prefix = " ".join(parts)
    return f"{prefix} {message}"
