import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.extractor.raw_response_parser import RawResponseParser


def test_parse_valid_json_payload() -> None:
    parser = RawResponseParser()
    raw = '{"schema_version":"0.1","nodes":[],"edges":[]}'
    result = parser.parse(raw)

    assert not result.errors
    assert result.payload["schema_version"] == "0.1"


def test_parse_fenced_json_payload_when_enabled() -> None:
    parser = RawResponseParser(strip_code_fences=True)
    raw = "```json\n{\"schema_version\":\"0.1\",\"nodes\":[],\"edges\":[]}\n```"
    result = parser.parse(raw)

    assert not result.errors
    assert result.payload["schema_version"] == "0.1"


def test_parse_rejects_malformed_json() -> None:
    parser = RawResponseParser()
    raw = "{schema_version: 0.1, nodes: []"
    result = parser.parse(raw)

    assert result.errors
    assert result.errors[0].code == "LLM_RESPONSE_NOT_JSON"
