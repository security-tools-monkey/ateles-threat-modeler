from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.app import create_app
from image_to_nsm_service.job_manager import InMemoryJobManager
from image_to_nsm_service.llm_client import LlmClient, LlmRequest, LlmResponse
from image_to_nsm_service.pipeline import ImageToNsmPipeline


PNG_BYTES = b"\x89PNG\r\n\x1a\nmock"


class _InvalidEdgeLlmClient(LlmClient):
    def generate(self, request: LlmRequest) -> LlmResponse:
        payload = {
            "schema_version": "0.1",
            "model_id": "model-invalid",
            "title": "Invalid edges",
            "description": "Edges reference missing nodes.",
            "nodes": [],
            "edges": [
                {
                    "id": "e1",
                    "source": "n1",
                    "target": "n2",
                    "name": "Bad edge",
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
                        "confidence": 0.5,
                        "evidence": ["edge"],
                    },
                }
            ],
        }
        raw_output = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return LlmResponse(raw_output=raw_output, parsed_json=payload, model="invalid-llm")


def _post_image(client: TestClient) -> str:
    response = client.post(
        "/image-to-nsm",
        files={"image": ("diagram.png", PNG_BYTES, "image/png")},
        data={"context": "Sample context"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert "job_id" in payload
    return payload["job_id"]


def test_end_to_end_mock_flow_returns_valid_nsm() -> None:
    app = create_app()
    client = TestClient(app)

    job_id = _post_image(client)

    status_response = client.get(f"/image-to-nsm/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["job"]["status"] == "succeeded"

    nsm_response = client.get(f"/image-to-nsm/{job_id}/nsm")
    assert nsm_response.status_code == 200
    nsm_payload = nsm_response.json()
    assert nsm_payload["job"]["status"] == "succeeded"
    assert nsm_payload["nsm"]["schema_version"] == "0.1"
    assert nsm_payload["validation"]["valid"] is True

    raw_response = client.get(f"/image-to-nsm/{job_id}/raw")
    assert raw_response.status_code == 200
    assert raw_response.json()["raw_output"]


def test_end_to_end_flow_surfaces_validation_errors() -> None:
    app = create_app()
    job_manager = InMemoryJobManager()
    app.state.job_manager = job_manager
    app.state.pipeline = ImageToNsmPipeline(job_manager, llm_client=_InvalidEdgeLlmClient())
    client = TestClient(app)

    job_id = _post_image(client)

    status_response = client.get(f"/image-to-nsm/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["job"]["status"] == "failed"

    errors_response = client.get(f"/image-to-nsm/{job_id}/errors")
    assert errors_response.status_code == 200
    errors_payload = errors_response.json()
    assert errors_payload["job"]["status"] == "failed"
    assert errors_payload["validation"]["valid"] is False
    assert any(error["code"] == "NSM_SEMANTIC_ERROR" for error in errors_payload["errors"])
