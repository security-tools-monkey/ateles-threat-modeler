from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Dict, Union

from .quality_warnings import warn_on_quality
from .schema_validation import validate_schema
from .semantic_validation import validate_semantics
from .types import ValidationResult


JsonInput = Union[str, Dict[str, Any]]


def validate_nsm_payload(payload: JsonInput) -> ValidationResult:
    """Validate payload against schema and semantic rules.

    payload is required and can be a JSON string or a dict.
    Returns a ValidationResult with schema_errors/semantic_errors/warnings.
    """
    result = ValidationResult()

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except JSONDecodeError as exc:
            result.schema_errors.append(f"Invalid JSON: {exc}")
            return result
    else:
        parsed = payload

    if not isinstance(parsed, dict):
        result.schema_errors.append("Top-level JSON value must be an object")
        return result

    result.schema_errors.extend(validate_schema(parsed))
    result.semantic_errors.extend(validate_semantics(parsed))
    result.warnings.extend(warn_on_quality(parsed))
    return result
