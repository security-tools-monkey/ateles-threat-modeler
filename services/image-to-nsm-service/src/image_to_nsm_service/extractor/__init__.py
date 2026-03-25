"""Extractor orchestration interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..llm_client import ImagePayload, LlmClient, LlmRequest
from ..prompt_builder import PromptBuilder, PromptRequest
from .raw_response_parser import RawResponseParseError, RawResponseParser


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
    def __init__(
        self,
        llm_client: LlmClient,
        prompt_builder: PromptBuilder,
        parser: RawResponseParser | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._prompt_builder = prompt_builder
        self._parser = parser or RawResponseParser()

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
        parse_result = self._parser.parse(llm_response.raw_output)
        if parse_result.errors:
            raise RawResponseParseError(parse_result.errors)

        return ExtractionResult(
            prompt_version=prompt_spec.version,
            raw_output=llm_response.raw_output,
            nsm=parse_result.payload or {},
            model=llm_response.model,
        )
