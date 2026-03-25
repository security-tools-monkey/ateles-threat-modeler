"""Prompt builder interface with versioned placeholder prompt."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PromptRequest:
    context: Optional[str] = None


@dataclass(frozen=True)
class PromptSpec:
    version: str
    text: str


class PromptBuilder(ABC):
    @abstractmethod
    def build(self, request: PromptRequest) -> PromptSpec:
        """Build a versioned prompt for image-to-NSM extraction."""


class VersionedPromptBuilder(PromptBuilder):
    def __init__(self, version: str = "v0.1") -> None:
        self._version = version

    def build(self, request: PromptRequest) -> PromptSpec:
        prompt_text = _build_placeholder_prompt(request.context)
        return PromptSpec(version=self._version, text=prompt_text)


def _build_placeholder_prompt(context: Optional[str]) -> str:
    instructions = [
        "You are extracting an architecture diagram into strict NSM JSON (schema v0.1).",
        "Identify entities and relationships visible in the image.",
        "Map all findings into the NSM schema with required fields.",
        "Preserve ambiguity as unknowns instead of inventing facts.",
        "Attach provenance and confidence for each node and edge.",
        "Return ONLY valid JSON (no markdown, no commentary).",
    ]
    if context:
        instructions.append(f"Additional context: {context}")
    return "\n".join(instructions)
