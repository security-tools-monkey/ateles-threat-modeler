"""Extractor orchestration interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..llm_client import ImagePayload, LlmClient, LlmRequest
from ..prompt_builder import PromptBuilder, PromptRequest


@dataclass(frozen=True)
class ExtractionRequest:
    image: ImagePayload
    context: Optional[str] = None


@dataclass(frozen=True)
class ExtractionResult:
    prompt_version: str
    raw_output: str
    nsm: Dict[str, Any]
    model: str


class Extractor(ABC):
    @abstractmethod
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Run extraction and return the raw output and parsed NSM document."""


class LlmExtractor(Extractor):
    def __init__(self, llm_client: LlmClient, prompt_builder: PromptBuilder) -> None:
        self._llm_client = llm_client
        self._prompt_builder = prompt_builder

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        prompt_spec = self._prompt_builder.build(PromptRequest(context=request.context))
        llm_response = self._llm_client.generate(
            LlmRequest(
                image=request.image,
                prompt=prompt_spec.text,
                prompt_version=prompt_spec.version,
                context=request.context,
            )
        )
        return ExtractionResult(
            prompt_version=prompt_spec.version,
            raw_output=llm_response.raw_output,
            nsm=llm_response.parsed_json,
            model=llm_response.model,
        )
