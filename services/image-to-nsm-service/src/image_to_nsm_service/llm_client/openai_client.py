from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

from openai import OpenAI

from . import ImagePayload, LlmClient, LlmClientError, LlmProviderConfig, LlmRequest, LlmResponse
from ..validator.schema_loader import load_llm_schema

logger = logging.getLogger("image_to_nsm_service.llm_client.openai")


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
        llm_schema = _sanitize_llm_schema(load_llm_schema())
        format_spec = {
            "type": "json_schema",
            "name": "nsm_llm_output",
            "schema": llm_schema,
            "strict": True,
        }
        request_payload = {
            "model": self._model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": request.prompt},
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
            "text": {"format": format_spec},
        }
        metadata: Dict[str, Any] = {
            "provider": "openai",
            "prompt_version": request.prompt_version,
            "model": self._model,
        }
        redacted_payload = _redact_image_payload(request_payload)
        try:
            logger.debug("OpenAI request payload: %s", redacted_payload)
            response = self._client.with_options(timeout=self._timeout_seconds).responses.create(
                model=request_payload["model"],
                input=request_payload["input"],
                text=request_payload["text"],
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
        logger.debug(
            "OpenAI response received request_id=%s response_id=%s model=%s",
            request_id,
            response_id,
            response_model,
        )

        usage = _extract_usage(getattr(response, "usage", None))
        if usage:
            metadata["usage"] = usage
            logger.debug("OpenAI token usage: %s", usage)

        raw_output = getattr(response, "output_text", None)
        if not isinstance(raw_output, str) or not raw_output.strip():
            raise LlmClientError(
                "LLM_EMPTY_RESPONSE",
                "OpenAI response contained no text output.",
                metadata=metadata,
            )
        logger.debug("OpenAI raw output: %s", raw_output)

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


def _redact_image_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    input_items = payload.get("input")
    if not isinstance(input_items, list):
        return payload
    redacted_inputs = []
    for item in input_items:
        if not isinstance(item, dict):
            redacted_inputs.append(item)
            continue
        content = item.get("content")
        if not isinstance(content, list):
            redacted_inputs.append(item)
            continue
        redacted_content = []
        for part in content:
            if not isinstance(part, dict):
                redacted_content.append(part)
                continue
            if part.get("type") == "input_image":
                redacted_part = dict(part)
                redacted_part["image_url"] = "<IMAGE_REDACTED>"
                redacted_content.append(redacted_part)
            else:
                redacted_content.append(part)
        redacted_item = dict(item)
        redacted_item["content"] = redacted_content
        redacted_inputs.append(redacted_item)
    redacted = dict(payload)
    redacted["input"] = redacted_inputs
    return redacted


def _extract_usage(usage: Any) -> Dict[str, int]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return _normalize_usage_map(usage)
    result: Dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens"):
        value = getattr(usage, key, None)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = int(value)
    return result


def _sanitize_llm_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    cleaned = _strip_schema_keyword(schema, "allOf")
    return _enforce_required_properties(cleaned)


def _enforce_required_properties(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            cleaned[key] = _enforce_required_properties(item)
        properties = cleaned.get("properties")
        if isinstance(properties, dict):
            cleaned["required"] = list(properties.keys())
        return cleaned
    if isinstance(value, list):
        return [_enforce_required_properties(item) for item in value]
    return value


def _strip_schema_keyword(value: Any, keyword: str) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            if key == keyword:
                continue
            cleaned[key] = _strip_schema_keyword(item, keyword)
        return cleaned
    if isinstance(value, list):
        return [_strip_schema_keyword(item, keyword) for item in value]
    return value


def _normalize_usage_map(usage: Dict[str, Any]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = int(value)
    return result
