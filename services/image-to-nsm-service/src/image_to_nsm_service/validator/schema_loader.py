from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


SCHEMA_RELATIVE_PATH = Path("libs/common/schemas/nsm.schema.v0.1.json")
LLM_SCHEMA_RELATIVE_PATH = Path("libs/common/schemas/nsm_llm_output.schema.v0.1.json")
LLM_SCHEMA_EXAMPLE_RELATIVE_PATH = Path("libs/common/schemas/simplified.schema-example.json")


def _resolve_schema_path(start: Path, relative_path: Path, env_override: Optional[str] = None) -> Path:
    if env_override:
        env_path = os.getenv(env_override)
        if env_path:
            candidate = Path(env_path)
            if candidate.exists() and candidate.is_file():
                return candidate

    for parent in start.parents:
        candidate = parent / relative_path
        if candidate.exists():
            return candidate

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / relative_path
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Schema not found at {relative_path}")


@lru_cache(maxsize=1)
def load_nsm_schema() -> Dict[str, Any]:
    start = Path(__file__).resolve()
    schema_path = _resolve_schema_path(start, SCHEMA_RELATIVE_PATH, env_override="NSM_SCHEMA_PATH")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_schema_version() -> str:
    schema = load_nsm_schema()
    version = schema.get("schema_version")
    return version if isinstance(version, str) and version.strip() else "unknown"


@lru_cache(maxsize=1)
def load_llm_schema() -> Dict[str, Any]:
    start = Path(__file__).resolve()
    schema_path = _resolve_schema_path(start, LLM_SCHEMA_RELATIVE_PATH)
    return json.loads(schema_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_llm_schema_example() -> Dict[str, Any]:
    start = Path(__file__).resolve()
    schema_path = _resolve_schema_path(start, LLM_SCHEMA_EXAMPLE_RELATIVE_PATH)
    return json.loads(schema_path.read_text(encoding="utf-8"))
