from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_to_nsm_service.prompt_builder import PromptRequest, VersionedPromptBuilder
from image_to_nsm_service.validator import load_nsm_schema


def test_prompt_builder_includes_schema_and_enum_hints() -> None:
    builder = VersionedPromptBuilder()
    prompt = builder.build(PromptRequest()).text
    schema = load_nsm_schema()

    assert f"NSM schema version: {schema['schema_version']}" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "Do not create any other top-level entities besides nodes and edges" in prompt

    node_kinds = sorted({node["kind"] for node in schema["nodes"] if isinstance(node, dict)})
    assert f"Allowed node kinds: {', '.join(node_kinds)}." in prompt

    for node in schema["nodes"]:
        if not isinstance(node, dict):
            continue
        kind = node.get("kind")
        node_type = node.get("type")
        if isinstance(kind, str) and isinstance(node_type, str):
            assert f"Allowed {kind} types:" in prompt
            assert node_type in prompt

    assert "\"schema_version\"" in prompt
    assert "\"nodes\"" in prompt
    assert "\"edges\"" in prompt
