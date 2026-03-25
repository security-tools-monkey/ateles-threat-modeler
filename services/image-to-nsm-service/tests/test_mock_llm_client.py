import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.llm_client import ImagePayload, LlmRequest, MockLlmClient


def test_mock_llm_client_returns_deterministic_payload() -> None:
    client = MockLlmClient()
    request = LlmRequest(
        image=ImagePayload(filename="diagram.png", content_type="image/png", data=b"fake"),
        prompt="placeholder prompt",
        prompt_version="v0.1",
        context="example context",
    )
    first = client.generate(request)
    second = client.generate(request)

    assert first.parsed_json == second.parsed_json
    assert first.raw_output == second.raw_output
    assert first.model == "mock-vision-llm"
    assert first.parsed_json["schema_version"] == "0.1"
    assert first.raw_output == json.dumps(first.parsed_json, sort_keys=True, separators=(",", ":"))
