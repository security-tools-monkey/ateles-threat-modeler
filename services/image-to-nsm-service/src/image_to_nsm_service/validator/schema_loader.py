from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


SCHEMA_RELATIVE_PATH = Path("libs/common/schemas/nsm.schema.v0.1.json")


def _resolve_schema_path(start: Path) -> Path:
    env_path = os.getenv("NSM_SCHEMA_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists() and candidate.is_file():
            return candidate

    for parent in start.parents:
        candidate = parent / SCHEMA_RELATIVE_PATH
        if candidate.exists():
            return candidate

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / SCHEMA_RELATIVE_PATH
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"NSM schema not found at {SCHEMA_RELATIVE_PATH}")


@lru_cache(maxsize=1)
def load_nsm_schema() -> Dict[str, Any]:
    start = Path(__file__).resolve()
    schema_path = _resolve_schema_path(start)
    return json.loads(schema_path.read_text(encoding="utf-8"))


def load_schema_version() -> str:
    schema = load_nsm_schema()
    version = schema.get("schema_version")
    return version if isinstance(version, str) and version.strip() else "unknown"
