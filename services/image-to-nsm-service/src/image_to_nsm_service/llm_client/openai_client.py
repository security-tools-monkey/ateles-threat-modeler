from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from openai import OpenAI

from . import ImagePayload, LlmClient, LlmClientError, LlmProviderConfig, LlmRequest, LlmResponse


class OpenAiLlmClient(LlmClient):
    def __init__(self, client: OpenAI, model: str, timeout_seconds: float) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, config: LlmProviderConfig) -> "OpenAiLlmClient":
        client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            organization=config.openai_organization,
            project=config.openai_project,
            timeout=config.timeout_seconds,
        )
        return cls(client, config.model, config.timeout_seconds)

    def generate(self, request: LlmRequest) -> LlmResponse:
        image_url = _encode_image_data_url(request.image)
        metadata: Dict[str, Any] = {
            "provider": "openai",
            "prompt_version": request.prompt_version,
            "model": self._model,
        }
        try:
            response = self._client.with_options(timeout=self._timeout_seconds).responses.create(
                model=self._model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": request.prompt},
                            {"type": "input_image", "image_url": image_url},
                        ],
                    }
                ],
            )
        except Exception as exc:
            raise LlmClientError(
                "LLM_REQUEST_FAILED",
                f"OpenAI request failed: {exc}",
                metadata=metadata,
            ) from exc

        request_id = _extract_request_id(response)
        response_id = getattr(response, "id", None)
        response_model = getattr(response, "model", None)
        if isinstance(request_id, str):
            metadata["request_id"] = request_id
        if isinstance(response_id, str):
            metadata["response_id"] = response_id
        if isinstance(response_model, str):
            metadata["model"] = response_model

        raw_output = getattr(response, "output_text", None)
        if not isinstance(raw_output, str) or not raw_output.strip():
            raise LlmClientError(
                "LLM_EMPTY_RESPONSE",
                "OpenAI response contained no text output.",
                metadata=metadata,
            )

        parsed_json: Dict[str, Any] = {}
        return LlmResponse(
            raw_output=raw_output,
            parsed_json=parsed_json,
            model=response_model if isinstance(response_model, str) else self._model,
            metadata=metadata,
        )


def _encode_image_data_url(image: ImagePayload) -> str:
    if not image.data:
        raise LlmClientError(
            "LLM_REQUEST_FAILED",
            "Image payload is empty.",
            metadata={"provider": "openai"},
        )
    content_type = image.content_type or "application/octet-stream"
    encoded = base64.b64encode(image.data).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


def _extract_request_id(response: Any) -> Optional[str]:
    request_id = getattr(response, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    request_id = getattr(response, "_request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return None
