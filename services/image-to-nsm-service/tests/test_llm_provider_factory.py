from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.llm_client import LlmClientError, LlmProviderConfig, MockLlmClient, create_llm_client


def test_factory_returns_mock_client() -> None:
    client = create_llm_client(
        LlmProviderConfig(provider="mock", model="ignored", timeout_seconds=30.0)
    )
    assert isinstance(client, MockLlmClient)


def test_factory_requires_api_key_for_openai() -> None:
    with pytest.raises(LlmClientError) as exc:
        create_llm_client(
            LlmProviderConfig(provider="openai", model="gpt-5.4", timeout_seconds=30.0)
        )
    assert exc.value.code == "LLM_CONFIG_ERROR"
