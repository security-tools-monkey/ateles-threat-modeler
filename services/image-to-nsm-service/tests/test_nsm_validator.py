from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.validator import validate_nsm_payload


def _base_payload() -> dict:
    return {
        "schema_version": "0.1",
        "model_id": "model-001",
        "title": "Test model",
        "description": "Test description",
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
                "unknowns": [],
                "provenance": {
                    "source": "image_upload",
                    "method": "llm_extraction",
                    "confidence": 0.7,
                    "evidence": ["label:end user"],
                },
            },
            {
                "id": "n2",
                "kind": "object",
                "name": "Service",
                "type": "service",
                "trust_boundary": {
                    "level": "public_network",
                    "name": "Public",
                    "path": ["internet", "public_network"],
                },
                "assets": [],
                "controls": [],
                "properties": {},
                "tags": [],
                "unknowns": [],
                "provenance": {
                    "source": "image_upload",
                    "method": "llm_extraction",
                    "confidence": 0.7,
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
                "protocol": "https",
                "authn": "unknown",
                "assets": [],
                "controls": [],
                "properties": {},
                "tags": [],
                "unknowns": [],
                "provenance": {
                    "source": "image_upload",
                    "method": "llm_extraction",
                    "confidence": 0.7,
                    "evidence": ["edge"],
                },
            }
        ],
    }


def test_valid_payload_passes_schema_and_semantics() -> None:
    result = validate_nsm_payload(_base_payload())
    assert result.valid
    assert not result.schema_errors
    assert not result.semantic_errors


def test_schema_validation_catches_missing_required_fields() -> None:
    payload = _base_payload()
    payload["nodes"][0].pop("trust_boundary")
    result = validate_nsm_payload(payload)
    assert not result.valid
    assert any(
        "trust_boundary" in message and "required" in message for message in result.schema_errors
    )


def test_semantic_validation_catches_missing_node_reference() -> None:
    payload = _base_payload()
    payload["edges"][0]["target"] = "n99"
    result = validate_nsm_payload(payload)
    assert not result.valid
    assert any("edges[0].target references unknown node id n99" in message for message in result.semantic_errors)


def test_quality_warnings_surface_unknowns() -> None:
    payload = _base_payload()
    payload["nodes"] = [
        {
            "id": "n1",
            "kind": "object",
            "name": "Unknown service",
            "type": "unknown",
            "trust_boundary": {"level": "internet", "name": "Internet", "path": ["internet"]},
            "assets": [],
            "controls": [],
            "properties": {},
            "tags": [],
            "unknowns": [],
            "provenance": {
                "source": "image_upload",
                "method": "llm_extraction",
                "confidence": 0.2,
                "evidence": ["label:unknown"],
            },
        },
        {
            "id": "n2",
            "kind": "object",
            "name": "Unknown service 2",
            "type": "unknown",
            "trust_boundary": {"level": "internet", "name": "Internet", "path": ["internet"]},
            "assets": [],
            "controls": [],
            "properties": {},
            "tags": [],
            "unknowns": [],
            "provenance": {
                "source": "image_upload",
                "method": "llm_extraction",
                "confidence": 0.2,
                "evidence": ["label:unknown2"],
            },
        },
    ]
    payload["edges"] = [
        {
            "id": "e1",
            "source": "n1",
            "target": "n2",
            "name": "edge",
            "direction": "uni",
            "protocol": "unknown",
            "authn": "unknown",
            "assets": [],
            "controls": [],
            "properties": {},
            "tags": [],
            "unknowns": [],
            "provenance": {
                "source": "image_upload",
                "method": "llm_extraction",
                "confidence": 0.2,
                "evidence": ["edge"],
            },
        }
    ]
    result = validate_nsm_payload(payload)
    assert result.valid
    assert any("type=unknown" in message for message in result.warnings)
    assert any("protocol=unknown" in message for message in result.warnings)
    assert any("No identity nodes" in message for message in result.warnings)
    assert any("trust boundary path hierarchy" in message for message in result.warnings)
    assert any("provenance confidence values" in message for message in result.warnings)
