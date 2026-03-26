"""LLM client integration interfaces and mock implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ImagePayload:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class LlmRequest:
    image: ImagePayload
    prompt: str
    prompt_version: str
    context: Optional[str] = None


@dataclass(frozen=True)
class LlmResponse:
    raw_output: str
    parsed_json: Dict[str, Any]
    model: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class LlmClient(ABC):
    @abstractmethod
    def generate(self, request: LlmRequest) -> LlmResponse:
        """Generate structured output for the provided image and prompt."""


class LlmClientError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.metadata = metadata or {}
        self.retryable = retryable


@dataclass(frozen=True)
class LlmProviderConfig:
    provider: str
    model: str
    timeout_seconds: float
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_organization: Optional[str] = None
    openai_project: Optional[str] = None


class MockLlmClient(LlmClient):
    """Deterministic placeholder LLM client for Step 1 scaffolding."""

    def __init__(self, model: str = "mock-vision-llm") -> None:
        self._model = model

    def generate(self, request: LlmRequest) -> LlmResponse:
        payload = _placeholder_nsm_payload()
        raw_output = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return LlmResponse(
            raw_output=raw_output,
            parsed_json=payload,
            model=self._model,
            metadata={"prompt_version": request.prompt_version},
        )


def _placeholder_nsm_payload() -> Dict[str, Any]:
    return {
        "schema_version": "0.1",
        "model_id": "mock-model-001",
        "title": "Placeholder architecture model",
        "description": "Mock LLM output for image-to-NSM extraction.",
        "nodes": [
            {
                "id": "n1",
                "kind": "identity",
                "name": "End user",
                "type": "external_user",
                "trust_boundary": {"level": "internet", "name": "Internet", "path": ["internet", "public"]},
                "assets": [],
                "controls": [],
                "properties": {},
                "tags": [],
                "unknowns": ["node classification uncertain"],
                "provenance": {
                    "source": "image_upload",
                    "method": "llm_extraction",
                    "confidence": 0.3,
                    "evidence": ["label:end user"],
                },
            },
            {
                "id": "n2",
                "kind": "object",
                "name": "Service",
                "type": "service",
                "trust_boundary": {"level": "public", "name": "Public", "path": ["internet", "public"]},
                "assets": [],
                "controls": [],
                "properties": {},
                "tags": [],
                "unknowns": ["service role unspecified"],
                "provenance": {
                    "source": "image_upload",
                    "method": "llm_extraction",
                    "confidence": 0.3,
                    "evidence": ["label:service"],
                },
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n1",
                "target": "n2",
                "name": "Request",
                "direction": "uni",
                "protocol": "unknown",
                "authn": "unknown",
                "assets": [],
                "controls": [],
                "properties": {},
                "tags": [],
                "unknowns": ["protocol not visible"],
                "provenance": {
                    "source": "image_upload",
                    "method": "llm_extraction",
                    "confidence": 0.3,
                    "evidence": ["edge"],
                },
            }
        ],
    }


def create_llm_client(config: LlmProviderConfig) -> LlmClient:
    provider = config.provider.strip().lower()
    if provider in {"mock", "local"}:
        return MockLlmClient()
    if provider in {"openai", "openai-responses"}:
        if not config.openai_api_key:
            raise LlmClientError(
                "LLM_CONFIG_ERROR",
                "OPENAI_API_KEY is required for the OpenAI provider.",
                metadata={"provider": provider, "model": config.model},
            )
        from .openai_client import OpenAiLlmClient

        return OpenAiLlmClient.from_config(config)
    raise LlmClientError(
        "LLM_CONFIG_ERROR",
        f"Unsupported LLM provider '{config.provider}'.",
        metadata={"provider": config.provider},
    )
