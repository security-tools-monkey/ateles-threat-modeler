from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationResult:
    schema_errors: List[str] = field(default_factory=list)
    semantic_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.schema_errors and not self.semantic_errors
