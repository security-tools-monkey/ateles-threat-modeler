from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


SCHEMA_RELATIVE_PATH = Path("libs/common/schemas/nsm.schema.v0.1.json")


def _find_repo_root(start: Path) -> Path:
    for parent in start.parents:
        candidate = parent / SCHEMA_RELATIVE_PATH
        if candidate.exists():
            return parent
    raise FileNotFoundError(f"NSM schema not found at {SCHEMA_RELATIVE_PATH}")


@lru_cache(maxsize=1)
def load_nsm_schema() -> Dict[str, Any]:
    start = Path(__file__).resolve()
    repo_root = _find_repo_root(start)
    schema_path = repo_root / SCHEMA_RELATIVE_PATH
    return json.loads(schema_path.read_text(encoding="utf-8"))
