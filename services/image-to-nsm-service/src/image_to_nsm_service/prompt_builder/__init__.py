"""Prompt builder for versioned image-to-NSM extraction prompts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Optional

from ..validator.schema_loader import load_nsm_schema


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
    schema = load_nsm_schema()
    schema_version = str(schema.get("schema_version", "unknown"))

    top_level_keys = _sorted_unique(schema.keys())
    node_template = _first_dict(schema.get("nodes", []))
    edge_template = _first_dict(schema.get("edges", []))
    node_keys = _sorted_unique(node_template.keys()) if node_template else []
    edge_keys = _sorted_unique(edge_template.keys()) if edge_template else []

    trust_boundary_keys = _sorted_unique(_nested_keys(node_template, "trust_boundary"))
    provenance_keys = _sorted_unique(_nested_keys(node_template, "provenance"))
    unknowns_keys = _sorted_unique(_collect_list_item_keys(schema, "unknowns"))
    asset_keys = _sorted_unique(_collect_list_item_keys(schema, "assets"))
    control_keys = _sorted_unique(_collect_list_item_keys(schema, "controls"))

    node_kinds = _sorted_unique(node.get("kind") for node in schema.get("nodes", []) if isinstance(node, dict))
    node_types_by_kind = _collect_node_types(schema)
    trust_boundary_levels = _sorted_unique(
        node.get("trust_boundary", {}).get("level")
        for node in schema.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("trust_boundary"), dict)
    )
    edge_directions = _sorted_unique(
        edge.get("direction") for edge in schema.get("edges", []) if isinstance(edge, dict)
    )
    edge_protocols = _sorted_unique(
        edge.get("protocol") for edge in schema.get("edges", []) if isinstance(edge, dict)
    )
    authn_values = _sorted_unique(edge.get("authn") for edge in schema.get("edges", []) if isinstance(edge, dict))
    asset_sensitivities = _sorted_unique(_collect_list_values(schema, "assets", "sensitivity"))
    asset_directions = _sorted_unique(_collect_list_values(schema, "assets", "direction"))
    control_categories = _sorted_unique(_collect_list_values(schema, "controls", "category"))
    control_modes = _sorted_unique(_collect_list_values(schema, "controls", "mode"))
    control_statuses = _sorted_unique(_collect_list_values(schema, "controls", "status"))

    instructions = [
        "You are extracting a single architecture diagram image into strict NSM JSON.",
        "Return ONLY valid JSON. No markdown, no commentary, no code fences.",
        f"NSM schema version: {schema_version}.",
        f"Top-level object must contain only: {', '.join(top_level_keys)}.",
        "Do not create any other top-level entities besides nodes and edges.",
        f"Node objects must include: {', '.join(node_keys)}.",
        f"Edge objects must include: {', '.join(edge_keys)}.",
        "Represent components as nodes, identities as nodes, and data flows as edges.",
        "Represent trust boundaries as node.trust_boundary.",
        "Represent assets as node.assets or edge.assets.",
        "Represent logical controls as node.controls or edge.controls.",
        "Represent deployable controls (e.g., WAF, IDS) as object nodes only if clearly visible.",
        "Use only supported enum values where possible. If unsure, use 'unknown' and add an unknowns[] entry.",
        f"Allowed node kinds: {', '.join(node_kinds)}.",
    ]

    if trust_boundary_keys:
        instructions.append(f"trust_boundary fields: {', '.join(trust_boundary_keys)}.")
    if asset_keys:
        instructions.append(f"assets[] fields: {', '.join(asset_keys)}.")
    if control_keys:
        instructions.append(f"controls[] fields: {', '.join(control_keys)}.")
    if unknowns_keys:
        instructions.append(f"unknowns[] fields: {', '.join(unknowns_keys)}.")
    if provenance_keys:
        instructions.append(f"provenance fields: {', '.join(provenance_keys)}.")

    for kind, types in node_types_by_kind.items():
        instructions.append(f"Allowed {kind} types: {', '.join(types)}.")

    if trust_boundary_levels:
        instructions.append(f"Allowed trust_boundary.level values: {', '.join(trust_boundary_levels)}.")
    if edge_directions:
        instructions.append(f"Allowed edge direction values: {', '.join(edge_directions)}.")
    if edge_protocols:
        instructions.append(f"Allowed edge protocol values: {', '.join(edge_protocols)}.")
    if authn_values:
        instructions.append(f"Allowed authn values: {', '.join(authn_values)}.")
    if asset_sensitivities:
        instructions.append(f"Allowed asset sensitivity values: {', '.join(asset_sensitivities)}.")
    if asset_directions:
        instructions.append(f"Allowed asset direction values: {', '.join(asset_directions)}.")
    if control_categories:
        instructions.append(f"Allowed control category values: {', '.join(control_categories)}.")
    if control_modes:
        instructions.append(f"Allowed control mode values: {', '.join(control_modes)}.")
    if control_statuses:
        instructions.append(f"Allowed control status values: {', '.join(control_statuses)}.")

    instructions.extend(
        [
            "Do not hallucinate components or flows. Only include what is visible or explicitly stated.",
            "Preserve ambiguity by using unknowns[] with field, reason, and question_hint.",
            "Populate provenance.source='image_upload', provenance.method='llm_extraction', confidence in [0,1], and evidence strings.",
            "Example output (compact JSON):",
            _example_output(schema_version),
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


def _first_dict(items: Iterable[object]) -> dict:
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def _nested_keys(container: Optional[dict], key: str) -> list[str]:
    if not isinstance(container, dict):
        return []
    nested = container.get(key)
    if not isinstance(nested, dict):
        return []
    return list(nested.keys())


def _list_item_keys(container: Optional[dict], key: str) -> list[str]:
    if not isinstance(container, dict):
        return []
    items = container.get(key)
    if not isinstance(items, list):
        return []
    first_item = _first_dict(items)
    if not first_item:
        return []
    return list(first_item.keys())


def _collect_list_item_keys(schema: dict, list_key: str) -> list[str]:
    for node in schema.get("nodes", []):
        if isinstance(node, dict):
            keys = _list_item_keys(node, list_key)
            if keys:
                return keys
    for edge in schema.get("edges", []):
        if isinstance(edge, dict):
            keys = _list_item_keys(edge, list_key)
            if keys:
                return keys
    return []


def _collect_list_values(schema: dict, list_key: str, value_key: str) -> list[str]:
    values = []
    for node in schema.get("nodes", []):
        if isinstance(node, dict):
            values.extend(_list_values_from_item(node, list_key, value_key))
    for edge in schema.get("edges", []):
        if isinstance(edge, dict):
            values.extend(_list_values_from_item(edge, list_key, value_key))
    return values


def _list_values_from_item(item: dict, list_key: str, value_key: str) -> list[str]:
    values = []
    list_items = item.get(list_key)
    if not isinstance(list_items, list):
        return values
    for list_item in list_items:
        if isinstance(list_item, dict):
            value = list_item.get(value_key)
            if isinstance(value, str):
                values.append(value)
    return values


def _collect_node_types(schema: dict) -> dict[str, list[str]]:
    types_by_kind: dict[str, set[str]] = {}
    for node in schema.get("nodes", []):
        if not isinstance(node, dict):
            continue
        kind = node.get("kind")
        node_type = node.get("type")
        if not isinstance(kind, str) or not isinstance(node_type, str):
            continue
        types_by_kind.setdefault(kind, set()).add(node_type)
    return {kind: sorted(types) for kind, types in sorted(types_by_kind.items())}


def _example_output(schema_version: str) -> str:
    return (
        "{"
        f"\"schema_version\":\"{schema_version}\","
        "\"model_id\":\"model-001\","
        "\"title\":\"Example model\","
        "\"description\":\"Extracted from image\","
        "\"nodes\":["
        "{"
        "\"id\":\"n1\","
        "\"kind\":\"identity\","
        "\"name\":\"End user\","
        "\"type\":\"external_user\","
        "\"trust_boundary\":{\"level\":\"internet\",\"name\":\"Internet\",\"path\":[\"internet\"]},"
        "\"assets\":[],"
        "\"controls\":[],"
        "\"properties\":{},"
        "\"tags\":[],"
        "\"unknowns\":[],"
        "\"provenance\":{\"source\":\"image_upload\",\"method\":\"llm_extraction\","
        "\"confidence\":0.9,\"evidence\":[\"label:end user\"]}"
        "},"
        "{"
        "\"id\":\"n2\","
        "\"kind\":\"object\","
        "\"name\":\"Web service\","
        "\"type\":\"service\","
        "\"trust_boundary\":{\"level\":\"public_network\",\"name\":\"Public network\","
        "\"path\":[\"internet\",\"public_network\"]},"
        "\"assets\":[],"
        "\"controls\":[],"
        "\"properties\":{},"
        "\"tags\":[],"
        "\"unknowns\":[],"
        "\"provenance\":{\"source\":\"image_upload\",\"method\":\"llm_extraction\","
        "\"confidence\":0.85,\"evidence\":[\"label:web service\"]}"
        "}"
        "],"
        "\"edges\":["
        "{"
        "\"id\":\"e1\","
        "\"source\":\"n1\","
        "\"target\":\"n2\","
        "\"name\":\"User request\","
        "\"direction\":\"uni\","
        "\"protocol\":\"https\","
        "\"authn\":\"unknown\","
        "\"assets\":[],"
        "\"controls\":[],"
        "\"properties\":{},"
        "\"tags\":[],"
        "\"unknowns\":["
        "{"
        "\"field\":\"authn\","
        "\"reason\":\"Authentication method not shown\","
        "\"question_hint\":\"How do users authenticate?\""
        "}"
        "],"
        "\"provenance\":{\"source\":\"image_upload\",\"method\":\"llm_extraction\","
        "\"confidence\":0.8,\"evidence\":[\"arrow:end user -> web service\"]}"
        "}"
        "]"
        "}"
    )
