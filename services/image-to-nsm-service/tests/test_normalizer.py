from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.normalizer import normalize_nsm_payload


def test_normalizer_assigns_ids_and_defaults() -> None:
    payload = {
        "schema_version": "0.1",
        "model_id": "model-1",
        "title": "Test",
        "description": "Test desc",
        "nodes": [
            {"name": "Client", "kind": "identity", "type": "external_user", "trust_boundary": "Internet"},
            {"name": "API", "type": "service", "trust_boundary": {"level": "Public Network"}},
        ],
        "edges": [
            {"from": "Client", "to": "API", "protocol": "HTTPS"},
        ],
    }

    result = normalize_nsm_payload(payload)
    nodes = result.payload["nodes"]
    edges = result.payload["edges"]

    assert nodes[0]["id"] == "n1"
    assert nodes[1]["id"] == "n2"
    assert nodes[0]["trust_boundary"]["level"] == "internet"
    assert nodes[1]["trust_boundary"]["level"] == "public_network"
    assert nodes[1]["trust_boundary"]["path"]
    assert nodes[0]["provenance"]["confidence"] <= 1.0
    assert nodes[0]["assets"] == []
    assert nodes[0]["controls"] == []
    assert nodes[0]["tags"] == []
    assert nodes[0]["unknowns"] == []

    assert edges[0]["id"] == "e1"
    assert edges[0]["source"] == "n1"
    assert edges[0]["target"] == "n2"
    assert edges[0]["protocol"] == "https"
    assert edges[0]["provenance"]["confidence"] <= 1.0


def test_normalizer_enum_synonyms_and_properties() -> None:
    payload = {
        "schema_version": "0.1",
        "model_id": "model-2",
        "title": "Enum test",
        "description": "Test desc",
        "nodes": [
            {
                "name": "DB",
                "kind": "Object",
                "type": "DB",
                "trust_boundary": {"level": "Public Network"},
                "legacy": True,
            }
        ],
        "edges": [],
    }

    result = normalize_nsm_payload(payload)
    node = result.payload["nodes"][0]

    assert node["kind"] == "object"
    assert node["type"] == "database"
    assert node["trust_boundary"]["level"] == "public_network"
    assert node["properties"]["legacy"] is True
    assert "legacy" not in node


def test_normalizer_controls_and_unknowns() -> None:
    payload = {
        "schema_version": "0.1",
        "model_id": "model-3",
        "title": "Controls test",
        "description": "Test desc",
        "nodes": [
            {
                "name": "Service",
                "kind": "object",
                "type": "service",
                "trust_boundary": {"level": "internet"},
                "controls": ["mfa"],
                "unknowns": ["auth method unclear"],
                "provenance": {"confidence": 85},
            }
        ],
        "edges": [],
    }

    result = normalize_nsm_payload(payload)
    node = result.payload["nodes"][0]

    assert node["controls"][0]["category"] == "authn"
    assert node["controls"][0]["mode"] == "preventive"
    assert node["unknowns"][0]["reason"] == "auth method unclear"
    assert node["provenance"]["confidence"] == 0.85
