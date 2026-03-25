from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Any, Dict, Iterable, List, Optional

from ..models.api import ExtractionIssue


_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class RawResponseParseResult:
    payload: Optional[Dict[str, Any]]
    errors: List[ExtractionIssue] = field(default_factory=list)


class RawResponseParseError(Exception):
    def __init__(self, errors: Iterable[ExtractionIssue]) -> None:
        self.errors = list(errors)
        super().__init__("LLM response parsing failed")


class RawResponseParser:
    def __init__(self, *, strip_code_fences: bool = False) -> None:
        self._strip_code_fences = strip_code_fences

    def parse(self, raw_output: str) -> RawResponseParseResult:
        if not isinstance(raw_output, str):
            return RawResponseParseResult(
                payload=None,
                errors=[
                    _issue(
                        "LLM_RESPONSE_NOT_JSON",
                        "LLM response is not a text payload.",
                    )
                ],
            )

        candidate = raw_output
        match = _CODE_FENCE_RE.match(candidate)
        if match:
            if not self._strip_code_fences:
                return RawResponseParseResult(
                    payload=None,
                    errors=[
                        _issue(
                            "LLM_RESPONSE_NOT_JSON",
                            "LLM response is wrapped in markdown code fences.",
                        )
                    ],
                )
            candidate = match.group(1)

        try:
            parsed = json.loads(candidate)
        except JSONDecodeError as exc:
            message = (
                "LLM response is not valid JSON: "
                f"{exc.msg} (line {exc.lineno}, column {exc.colno})."
            )
            return RawResponseParseResult(
                payload=None,
                errors=[_issue("LLM_RESPONSE_NOT_JSON", message)],
            )

        if not isinstance(parsed, dict):
            return RawResponseParseResult(
                payload=None,
                errors=[
                    _issue(
                        "LLM_RESPONSE_NOT_JSON",
                        "Top-level JSON value must be an object.",
                    )
                ],
            )

        return RawResponseParseResult(payload=parsed)


def _issue(code: str, message: str) -> ExtractionIssue:
    return ExtractionIssue(code=code, message=message, severity="error")
