from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json

from image_to_nsm_service.prompt_builder import PromptRequest, VersionedPromptBuilder
from image_to_nsm_service.validator.schema_loader import load_llm_schema, load_llm_schema_example


def test_prompt_builder_includes_schema_and_enum_hints() -> None:
    builder = VersionedPromptBuilder()
    prompt = builder.build(PromptRequest()).text
    schema = load_llm_schema()
    example = load_llm_schema_example()

    schema_version = (
        schema.get("properties", {}).get("schema_version", {}).get("const")
        if isinstance(schema.get("properties"), dict)
        else None
    )
    expected_version = schema_version if isinstance(schema_version, str) and schema_version.strip() else "unknown"
    assert f"NSM LLM schema version: {expected_version}." in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "Do not create any other top-level entities besides nodes and edges" in prompt

    top_level_keys = ", ".join(sorted(schema.get("properties", {}).keys()))
    assert f"Top-level object must contain only: {top_level_keys}." in prompt

    node_kinds = sorted(schema.get("$defs", {}).get("node_kind", {}).get("enum", []))
    assert f"Allowed node kinds: {', '.join(node_kinds)}." in prompt

    object_types = sorted(schema.get("$defs", {}).get("object_type", {}).get("enum", []))
    identity_types = sorted(schema.get("$defs", {}).get("identity_type", {}).get("enum", []))
    assert f"Allowed object types: {', '.join(object_types)}." in prompt
    assert f"Allowed identity types: {', '.join(identity_types)}." in prompt

    example_json = json.dumps(example, ensure_ascii=False, separators=(",", ":"))
    assert example_json in prompt
