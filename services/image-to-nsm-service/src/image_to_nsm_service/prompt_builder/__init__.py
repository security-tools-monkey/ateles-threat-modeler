"""Prompt builder for versioned image-to-NSM extraction prompts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from typing import Iterable, Optional

from ..validator.schema_loader import load_llm_schema, load_llm_schema_example


@dataclass(frozen=True)
class PromptRequest:
    context: Optional[str] = None


@dataclass(frozen=True)
class PromptSpec:
    version: str
    text: str


class PromptBuilder(ABC):
    @abstractmethod
    def build(self, request: PromptRequest) -> PromptSpec:
        """Build a versioned prompt for image-to-NSM extraction."""


class VersionedPromptBuilder(PromptBuilder):
    def __init__(self, version: str = "v0.1") -> None:
        self._version = version

    def build(self, request: PromptRequest) -> PromptSpec:
        prompt_text = _build_extraction_prompt(request.context)
        return PromptSpec(version=self._version, text=prompt_text)


def _build_extraction_prompt(context: Optional[str]) -> str:
    schema = load_llm_schema()
    example = load_llm_schema_example()
    schema_version = _schema_const(schema, "schema_version") or "unknown"

    top_level_keys = _sorted_unique(_schema_property_keys(schema))
    node_keys = _sorted_unique(_schema_def_property_keys(schema, "node"))
    edge_keys = _sorted_unique(_schema_def_property_keys(schema, "edge"))

    node_kinds = _sorted_unique(_schema_def_enum(schema, "node_kind"))
    object_types = _sorted_unique(_schema_def_enum(schema, "object_type"))
    identity_types = _sorted_unique(_schema_def_enum(schema, "identity_type"))
    trust_boundary_levels = _sorted_unique(_schema_def_enum(schema, "trust_boundary_level"))
    edge_directions = _sorted_unique(_schema_def_enum(schema, "direction"))
    edge_protocols = _sorted_unique(_schema_def_enum(schema, "protocol_type"))
    authn_values = _sorted_unique(_schema_def_enum(schema, "authn_type"))
    asset_types = _sorted_unique(_schema_def_enum(schema, "asset_type"))
    control_types = _sorted_unique(_schema_def_enum(schema, "control_type"))

    instructions = [
        "You are extracting a single architecture diagram image into simplified NSM JSON.",
        "Return ONLY valid JSON. No markdown, no commentary, no code fences.",
        f"NSM LLM schema version: {schema_version}.",
        f"Top-level object must contain only: {', '.join(top_level_keys)}.",
        "Do not create any other top-level entities besides nodes and edges.",
        f"Node objects must include: {', '.join(node_keys)}.",
        f"Edge objects must include: {', '.join(edge_keys)}.",
        "Represent components as nodes, identities as nodes, and data flows as edges.",
        "Represent trust boundaries as a single node.trust_boundary string.",
        "Represent assets as node.assets or edge.assets (arrays of strings).",
        "Represent controls as node.controls or edge.controls (arrays of strings).",
        "Represent unknowns as node.unknowns or edge.unknowns (arrays of strings).",
        "Include confidence on nodes and edges as a number in [0,1].",
        "Represent deployable controls (e.g., WAF, IDS) as object nodes only if clearly visible.",
        "Use only supported enum values where possible. If unsure, use 'unknown' and add an unknowns[] entry.",
    ]

    if node_kinds:
        instructions.append(f"Allowed node kinds: {', '.join(node_kinds)}.")
    if object_types:
        instructions.append(f"Allowed object types: {', '.join(object_types)}.")
    if identity_types:
        instructions.append(f"Allowed identity types: {', '.join(identity_types)}.")
    if trust_boundary_levels:
        instructions.append(f"Allowed trust_boundary.level values: {', '.join(trust_boundary_levels)}.")
    if edge_directions:
        instructions.append(f"Allowed edge direction values: {', '.join(edge_directions)}.")
    if edge_protocols:
        instructions.append(f"Allowed edge protocol values: {', '.join(edge_protocols)}.")
    if authn_values:
        instructions.append(f"Allowed authn values: {', '.join(authn_values)}.")
    if asset_types:
        instructions.append(f"Allowed asset types: {', '.join(asset_types)}.")
    if control_types:
        instructions.append(f"Allowed control types: {', '.join(control_types)}.")

    instructions.extend(
        [
            "Do not hallucinate components or flows. Only include what is visible or explicitly stated.",
            "Preserve ambiguity by using unknowns[] strings that explain what is missing.",
            "Example output (compact JSON):",
            _example_output(example),
        ]
    )

    if context:
        instructions.append(f"Additional context: {context}")

    return "\n".join(instructions)


def _sorted_unique(values: Iterable[object]) -> list[str]:
    items = []
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                items.append(cleaned)
    return sorted(set(items))


def _schema_property_keys(schema: dict) -> list[str]:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return []
    return list(props.keys())


def _schema_def_property_keys(schema: dict, def_name: str) -> list[str]:
    definition = _schema_definition(schema, def_name)
    props = definition.get("properties") if isinstance(definition, dict) else None
    if not isinstance(props, dict):
        return []
    return list(props.keys())


def _schema_def_enum(schema: dict, def_name: str) -> list[str]:
    definition = _schema_definition(schema, def_name)
    if not isinstance(definition, dict):
        return []
    values = definition.get("enum")
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]


def _schema_definition(schema: dict, def_name: str) -> dict:
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return {}
    definition = defs.get(def_name)
    return definition if isinstance(definition, dict) else {}


def _schema_const(schema: dict, property_name: str) -> Optional[str]:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    prop = props.get(property_name)
    if not isinstance(prop, dict):
        return None
    value = prop.get("const")
    return value if isinstance(value, str) and value.strip() else None


def _example_output(example: dict) -> str:
    return json.dumps(example, ensure_ascii=False, separators=(",", ":"))
