from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import copy
import re

from ..validator.schema_loader import load_nsm_schema
from ..validator.semantic_validation import IDENTITY_TYPES


@dataclass(frozen=True)
class NormalizationNote:
    path: str
    message: str
    original_value: Optional[Any] = None
    normalized_value: Optional[Any] = None


@dataclass(frozen=True)
class NormalizationResult:
    payload: Dict[str, Any]
    notes: List[NormalizationNote] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizationConfig:
    schema_version: str
    default_model_id: str = "model-unknown"
    default_title: str = "Unknown architecture"
    default_description: str = "Extracted from image"
    default_provenance_source: str = "image_upload"
    default_provenance_method: str = "llm_extraction"
    default_confidence: float = 0.3
    default_evidence: List[str] = field(default_factory=lambda: ["normalizer:defaulted"])
    synonyms: Dict[str, Dict[str, str]] = field(default_factory=dict)
    control_mappings: Dict[str, Dict[str, str]] = field(default_factory=dict)
    control_field_aliases: Dict[str, str] = field(default_factory=dict)
    key_aliases_node: Dict[str, str] = field(default_factory=dict)
    key_aliases_edge: Dict[str, str] = field(default_factory=dict)
    key_aliases_trust_boundary: Dict[str, str] = field(default_factory=dict)
    key_aliases_provenance: Dict[str, str] = field(default_factory=dict)


NORMALIZATION_VERSION = "v0.1"


class _IdAssigner:
    def __init__(self, prefix: str, existing: Iterable[str]) -> None:
        self._prefix = prefix
        self._existing = {value for value in existing if isinstance(value, str)}
        self._counter = 1

    def next_id(self) -> str:
        while True:
            candidate = f"{self._prefix}{self._counter}"
            self._counter += 1
            if candidate not in self._existing:
                self._existing.add(candidate)
                return candidate


_ENUM_CLEAN_RE = re.compile(r"[^a-z0-9_]+")


def normalize_nsm_payload(
    payload: Any, config: Optional[NormalizationConfig] = None
) -> NormalizationResult:
    config = config or _default_config()
    notes: List[NormalizationNote] = []
    if not isinstance(payload, dict):
        notes.append(
            NormalizationNote(
                path="",
                message="Top-level payload is not an object; replaced with defaults.",
                original_value=payload,
            )
        )
        payload = {}

    normalized = copy.deepcopy(payload)
    _normalize_top_level(normalized, config, notes)

    node_template, edge_template, list_item_templates = _schema_templates()
    node_keys = set(node_template.keys())
    edge_keys = set(edge_template.keys())
    assets_keys = list_item_templates.get("assets", {"type", "name", "sensitivity", "direction"})
    controls_keys = list_item_templates.get("controls", {"name", "category", "mode", "status"})
    unknowns_keys = list_item_templates.get("unknowns", {"field", "reason", "question_hint"})

    nodes_raw = normalized.get("nodes")
    if not isinstance(nodes_raw, list):
        notes.append(
            NormalizationNote(
                path="nodes",
                message="nodes must be an array; replaced with empty list.",
                original_value=nodes_raw,
            )
        )
        nodes_raw = []
    edges_raw = normalized.get("edges")
    if not isinstance(edges_raw, list):
        notes.append(
            NormalizationNote(
                path="edges",
                message="edges must be an array; replaced with empty list.",
                original_value=edges_raw,
            )
        )
        edges_raw = []

    node_id_assigner = _IdAssigner("n", _collect_ids(nodes_raw))
    edge_id_assigner = _IdAssigner("e", _collect_ids(edges_raw))

    normalized_nodes: List[Dict[str, Any]] = []
    for index, node in enumerate(nodes_raw):
        normalized_nodes.append(
            _normalize_node(
                node,
                index,
                config,
                notes,
                node_id_assigner,
                node_keys,
                assets_keys,
                controls_keys,
                unknowns_keys,
            )
        )

    name_to_id = _node_name_index(normalized_nodes)

    normalized_edges: List[Dict[str, Any]] = []
    for index, edge in enumerate(edges_raw):
        normalized_edges.append(
            _normalize_edge(
                edge,
                index,
                config,
                notes,
                edge_id_assigner,
                edge_keys,
                assets_keys,
                controls_keys,
                unknowns_keys,
                name_to_id,
            )
        )

    normalized["nodes"] = normalized_nodes
    normalized["edges"] = normalized_edges
    return NormalizationResult(payload=normalized, notes=notes)


def _default_config() -> NormalizationConfig:
    schema = load_nsm_schema()
    schema_version = str(schema.get("schema_version", "0.1"))
    return NormalizationConfig(
        schema_version=schema_version,
        synonyms=_default_synonyms(),
        control_mappings=_default_control_mappings(),
        control_field_aliases=_default_control_field_aliases(),
        key_aliases_node={
            "label": "name",
            "title": "name",
            "node_type": "type",
            "node_kind": "kind",
            "trustBoundary": "trust_boundary",
            "boundary": "trust_boundary",
            "boundary_zone": "trust_boundary",
        },
        key_aliases_edge={
            "from": "source",
            "to": "target",
            "src": "source",
            "dst": "target",
            "directionality": "direction",
            "auth": "authn",
        },
        key_aliases_trust_boundary={
            "boundary_level": "level",
            "tb_level": "level",
            "zone": "name",
        },
        key_aliases_provenance={
            "confidence_score": "confidence",
        },
    )


def _default_synonyms() -> Dict[str, Dict[str, str]]:
    return {
        "node.kind": {
            "actor": "identity",
            "user": "identity",
            "person": "identity",
            "component": "object",
            "service": "object",
        },
        "node.type": {
            "db": "database",
            "database": "database",
            "data_store": "database",
            "datastore": "database",
            "external_service": "third_party_saas",
            "third_party_service": "third_party_saas",
            "saas": "third_party_saas",
            "employee": "internal_user",
            "internal_employee": "internal_user",
            "user": "external_user",
            "end_user": "external_user",
            "external_user": "external_user",
            "service_account": "service_account",
            "svc_account": "service_account",
            "workload": "workload_identity",
            "third_party": "third_party",
        },
        "trust_boundary.level": {
            "public": "public_network",
            "public_network": "public_network",
            "internet_public": "internet",
            "internet_public_network": "internet",
            "dmz": "public_network",
            "private": "private_network",
            "internal": "private_network",
        },
        "edge.direction": {
            "uni_directional": "uni",
            "unidirectional": "uni",
            "bi_directional": "bi",
            "bidirectional": "bi",
        },
        "edge.protocol": {
            "https_tls": "https",
            "http_https": "https",
        },
        "edge.authn": {
            "no_auth": "none",
            "basic_auth": "basic",
            "oauth2": "oauth",
            "oidc": "oauth",
            "mtls": "mtls",
            "api_key": "api_key",
        },
        "asset.sensitivity": {"hi": "high"},
        "asset.direction": {
            "ingress": "transmits",
            "egress": "transmits",
            "store": "stores",
            "process": "processes",
        },
        "control.category": {
            "mfa": "authn",
            "2fa": "authn",
            "tls": "tls",
            "encryption_at_rest": "encryption",
            "encryption": "encryption",
            "waf": "waf",
            "rbac": "rbac",
        },
        "control.mode": {"prevent": "preventive", "detect": "detective"},
        "control.status": {"assume": "assumed"},
    }


def _default_control_mappings() -> Dict[str, Dict[str, str]]:
    return {
        "mfa": {"name": "MFA", "category": "authn", "mode": "preventive", "status": "unknown"},
        "2fa": {"name": "2FA", "category": "authn", "mode": "preventive", "status": "unknown"},
        "tls": {"name": "TLS", "category": "tls", "mode": "preventive", "status": "assumed"},
        "encryption": {
            "name": "Encryption",
            "category": "encryption",
            "mode": "preventive",
            "status": "unknown",
        },
        "waf": {"name": "WAF", "category": "waf", "mode": "preventive", "status": "unknown"},
        "rbac": {"name": "RBAC", "category": "rbac", "mode": "preventive", "status": "unknown"},
    }


def _default_control_field_aliases() -> Dict[str, str]:
    return {
        "mfa": "mfa",
        "2fa": "2fa",
        "multi_factor_auth": "mfa",
        "multi_factor_authentication": "mfa",
        "tls": "tls",
        "encryption": "encryption",
        "encryption_at_rest": "encryption",
        "waf": "waf",
        "rbac": "rbac",
    }


def _schema_templates() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, set[str]]]:
    schema = load_nsm_schema()
    node_template = _first_dict(schema.get("nodes", []))
    edge_template = _first_dict(schema.get("edges", []))

    def list_item_keys(container: Dict[str, Any], key: str) -> set[str]:
        items = container.get(key)
        if not isinstance(items, list):
            return set()
        item = _first_dict(items)
        return set(item.keys()) if item else set()

    list_item_templates = {
        "assets": list_item_keys(node_template, "assets") or list_item_keys(edge_template, "assets"),
        "controls": list_item_keys(node_template, "controls") or list_item_keys(edge_template, "controls"),
        "unknowns": list_item_keys(node_template, "unknowns") or list_item_keys(edge_template, "unknowns"),
    }
    return node_template, edge_template, list_item_templates


def _first_dict(items: Iterable[Any]) -> Dict[str, Any]:
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def _normalize_top_level(payload: Dict[str, Any], config: NormalizationConfig, notes: List[NormalizationNote]) -> None:
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        notes.append(
            NormalizationNote(
                path="schema_version",
                message="schema_version missing or invalid; defaulted.",
                original_value=schema_version,
                normalized_value=config.schema_version,
            )
        )
        payload["schema_version"] = config.schema_version
    else:
        payload["schema_version"] = schema_version.strip()

    for key, default, message in [
        ("model_id", config.default_model_id, "model_id missing or invalid; defaulted."),
        ("title", config.default_title, "title missing or invalid; defaulted."),
        ("description", config.default_description, "description missing or invalid; defaulted."),
    ]:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            notes.append(NormalizationNote(path=key, message=message, original_value=value, normalized_value=default))
            payload[key] = default
        else:
            payload[key] = value.strip()


def _normalize_node(
    node: Any,
    index: int,
    config: NormalizationConfig,
    notes: List[NormalizationNote],
    id_assigner: _IdAssigner,
    node_keys: set[str],
    asset_keys: set[str],
    control_keys: set[str],
    unknowns_keys: set[str],
) -> Dict[str, Any]:
    if not isinstance(node, dict):
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}]",
                message="Node entry is not an object; replaced with defaults.",
                original_value=node,
            )
        )
        node = {}

    node = dict(node)
    _apply_key_aliases(node, config.key_aliases_node, notes, f"nodes[{index}]")

    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id.strip():
        node_id = id_assigner.next_id()
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}].id",
                message="Node id missing or invalid; generated.",
                original_value=node.get("id"),
                normalized_value=node_id,
            )
        )
    node["id"] = node_id

    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        name = "unknown"
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}].name",
                message="Node name missing or invalid; defaulted.",
                original_value=node.get("name"),
                normalized_value=name,
            )
        )
    node["name"] = name.strip() if isinstance(name, str) else name

    node_type = _normalize_enum_value(node.get("type"), "node.type", config)
    if not node_type:
        node_type = "unknown"
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}].type",
                message="Node type missing or invalid; defaulted.",
                original_value=node.get("type"),
                normalized_value=node_type,
            )
        )
    node["type"] = node_type

    kind = _normalize_enum_value(node.get("kind"), "node.kind", config)
    if not kind:
        kind = "identity" if node_type in IDENTITY_TYPES else "object"
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}].kind",
                message="Node kind missing or invalid; inferred.",
                original_value=node.get("kind"),
                normalized_value=kind,
            )
        )
    if kind not in {"identity", "object"}:
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}].kind",
                message="Node kind unsupported; defaulted to object.",
                original_value=kind,
                normalized_value="object",
            )
        )
        kind = "object"
    node["kind"] = kind

    if kind == "identity" and node_type not in IDENTITY_TYPES and node_type != "unknown":
        notes.append(
            NormalizationNote(
                path=f"nodes[{index}].type",
                message="Identity node type unsupported; defaulted to unknown.",
                original_value=node_type,
                normalized_value="unknown",
            )
        )
        node["type"] = "unknown"

    node["trust_boundary"] = _normalize_trust_boundary(
        node.get("trust_boundary"), config, notes, f"nodes[{index}].trust_boundary"
    )

    node["assets"] = _normalize_assets(
        node.get("assets"), config, notes, f"nodes[{index}].assets", asset_keys
    )
    node["controls"] = _normalize_controls(
        node.get("controls"), config, notes, f"nodes[{index}].controls", control_keys
    )
    node["tags"] = _normalize_tags(node.get("tags"), notes, f"nodes[{index}].tags")
    node["unknowns"] = _normalize_unknowns(
        node.get("unknowns"), notes, f"nodes[{index}].unknowns", unknowns_keys
    )

    node["properties"] = _normalize_properties(node.get("properties"), notes, f"nodes[{index}].properties")
    node["provenance"] = _normalize_provenance(
        node.get("provenance"), config, notes, f"nodes[{index}].provenance"
    )

    _move_unsupported_fields(
        node,
        node_keys,
        node["properties"],
        config,
        notes,
        f"nodes[{index}]",
        node["controls"],
    )

    return node


def _normalize_edge(
    edge: Any,
    index: int,
    config: NormalizationConfig,
    notes: List[NormalizationNote],
    id_assigner: _IdAssigner,
    edge_keys: set[str],
    asset_keys: set[str],
    control_keys: set[str],
    unknowns_keys: set[str],
    name_to_id: Dict[str, str],
) -> Dict[str, Any]:
    if not isinstance(edge, dict):
        notes.append(
            NormalizationNote(
                path=f"edges[{index}]",
                message="Edge entry is not an object; replaced with defaults.",
                original_value=edge,
            )
        )
        edge = {}

    edge = dict(edge)
    _apply_key_aliases(edge, config.key_aliases_edge, notes, f"edges[{index}]")

    edge_id = edge.get("id")
    if not isinstance(edge_id, str) or not edge_id.strip():
        edge_id = id_assigner.next_id()
        notes.append(
            NormalizationNote(
                path=f"edges[{index}].id",
                message="Edge id missing or invalid; generated.",
                original_value=edge.get("id"),
                normalized_value=edge_id,
            )
        )
    edge["id"] = edge_id

    edge["source"] = _normalize_edge_endpoint(
        edge.get("source"), name_to_id, notes, f"edges[{index}].source"
    )
    edge["target"] = _normalize_edge_endpoint(
        edge.get("target"), name_to_id, notes, f"edges[{index}].target"
    )

    name = edge.get("name")
    if not isinstance(name, str) or not name.strip():
        name = "unknown"
        notes.append(
            NormalizationNote(
                path=f"edges[{index}].name",
                message="Edge name missing or invalid; defaulted.",
                original_value=edge.get("name"),
                normalized_value=name,
            )
        )
    edge["name"] = name.strip() if isinstance(name, str) else name

    direction = _normalize_enum_value(edge.get("direction"), "edge.direction", config)
    edge["direction"] = direction or "unknown"

    protocol = _normalize_enum_value(edge.get("protocol"), "edge.protocol", config)
    edge["protocol"] = protocol or "unknown"

    authn = _normalize_enum_value(edge.get("authn"), "edge.authn", config)
    edge["authn"] = authn or "unknown"

    edge["assets"] = _normalize_assets(
        edge.get("assets"), config, notes, f"edges[{index}].assets", asset_keys
    )
    edge["controls"] = _normalize_controls(
        edge.get("controls"), config, notes, f"edges[{index}].controls", control_keys
    )
    edge["tags"] = _normalize_tags(edge.get("tags"), notes, f"edges[{index}].tags")
    edge["unknowns"] = _normalize_unknowns(
        edge.get("unknowns"), notes, f"edges[{index}].unknowns", unknowns_keys
    )
    edge["properties"] = _normalize_properties(edge.get("properties"), notes, f"edges[{index}].properties")
    edge["provenance"] = _normalize_provenance(
        edge.get("provenance"), config, notes, f"edges[{index}].provenance"
    )

    _move_unsupported_fields(
        edge,
        edge_keys,
        edge["properties"],
        config,
        notes,
        f"edges[{index}]",
        edge["controls"],
    )

    return edge


def _normalize_edge_endpoint(
    value: Any, name_to_id: Dict[str, str], notes: List[NormalizationNote], path: str
) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("id"), str):
            return value["id"]
        value = value.get("name")

    if isinstance(value, str) and value.strip():
        candidate = value.strip()
        if candidate in name_to_id:
            notes.append(
                NormalizationNote(
                    path=path,
                    message="Edge endpoint matched node name; replaced with node id.",
                    original_value=candidate,
                    normalized_value=name_to_id[candidate],
                )
            )
            return name_to_id[candidate]
        lowered = candidate.lower()
        if lowered in name_to_id:
            notes.append(
                NormalizationNote(
                    path=path,
                    message="Edge endpoint matched node name (case-insensitive); replaced with node id.",
                    original_value=candidate,
                    normalized_value=name_to_id[lowered],
                )
            )
            return name_to_id[lowered]
        return candidate

    notes.append(
        NormalizationNote(
            path=path,
            message="Edge endpoint missing or invalid; defaulted to 'unknown'.",
            original_value=value,
            normalized_value="unknown",
        )
    )
    return "unknown"


def _normalize_trust_boundary(
    value: Any, config: NormalizationConfig, notes: List[NormalizationNote], path: str
) -> Dict[str, Any]:
    if isinstance(value, str):
        level = _normalize_enum_value(value, "trust_boundary.level", config) or "unknown"
        return {"level": level, "name": _title_from_enum(level), "path": [level]}

    if not isinstance(value, dict):
        notes.append(
            NormalizationNote(
                path=path,
                message="trust_boundary missing or invalid; defaulted.",
                original_value=value,
            )
        )
        return {"level": "unknown", "name": "Unknown", "path": ["unknown"]}

    trust_boundary = dict(value)
    _apply_key_aliases(trust_boundary, config.key_aliases_trust_boundary, notes, path)
    level = _normalize_enum_value(trust_boundary.get("level"), "trust_boundary.level", config) or "unknown"
    name = trust_boundary.get("name")
    if not isinstance(name, str) or not name.strip():
        name = _title_from_enum(level)
    path_value = trust_boundary.get("path")
    if not isinstance(path_value, list) or not path_value:
        path_value = [level]
    else:
        path_value = [
            _normalize_enum_value(item, "trust_boundary.level", config) or "unknown"
            for item in path_value
            if isinstance(item, str)
        ] or [level]

    return {"level": level, "name": name, "path": path_value}


def _normalize_assets(
    value: Any,
    config: NormalizationConfig,
    notes: List[NormalizationNote],
    path: str,
    asset_keys: set[str],
) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        notes.append(
            NormalizationNote(path=path, message="assets must be an array; defaulted.", original_value=value)
        )
        return []

    assets: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            assets.append(
                {
                    "type": _normalize_enum_value(item, "asset.type", config) or "unknown",
                    "name": item.strip(),
                    "sensitivity": "unknown",
                    "direction": "unknown",
                }
            )
            continue
        if not isinstance(item, dict):
            notes.append(
                NormalizationNote(
                    path=f"{path}[{index}]",
                    message="asset entry invalid; skipped.",
                    original_value=item,
                )
            )
            continue
        asset = dict(item)
        asset_type = _normalize_enum_value(asset.get("type"), "asset.type", config) or "unknown"
        name = asset.get("name")
        if not isinstance(name, str) or not name.strip():
            name = asset_type
        asset["type"] = asset_type
        asset["name"] = name
        asset["sensitivity"] = (
            _normalize_enum_value(asset.get("sensitivity"), "asset.sensitivity", config) or "unknown"
        )
        asset["direction"] = _normalize_enum_value(asset.get("direction"), "asset.direction", config) or "unknown"
        _strip_extra_fields(asset, asset_keys, notes, f"{path}[{index}]")
        assets.append(asset)

    return assets


def _normalize_controls(
    value: Any,
    config: NormalizationConfig,
    notes: List[NormalizationNote],
    path: str,
    control_keys: set[str],
) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    if not isinstance(value, list):
        notes.append(
            NormalizationNote(path=path, message="controls must be an array; defaulted.", original_value=value)
        )
        return []

    controls: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            control = _control_from_string(item, config)
            controls.append(control)
            continue
        if not isinstance(item, dict):
            notes.append(
                NormalizationNote(
                    path=f"{path}[{index}]",
                    message="control entry invalid; skipped.",
                    original_value=item,
                )
            )
            continue
        control = dict(item)
        name = control.get("name")
        if not isinstance(name, str) or not name.strip():
            name = "unknown"
        control["name"] = name
        control["category"] = _normalize_enum_value(control.get("category"), "control.category", config) or "unknown"
        control["mode"] = _normalize_enum_value(control.get("mode"), "control.mode", config) or "unknown"
        control["status"] = _normalize_enum_value(control.get("status"), "control.status", config) or "unknown"
        _strip_extra_fields(control, control_keys, notes, f"{path}[{index}]")
        controls.append(control)

    return controls


def _control_from_string(raw: str, config: NormalizationConfig) -> Dict[str, str]:
    cleaned = _enum_clean(raw)
    mapping = config.control_mappings.get(cleaned)
    if mapping:
        return dict(mapping)
    normalized = _normalize_enum_value(raw, "control.category", config)
    if normalized and normalized in config.control_mappings:
        return dict(config.control_mappings[normalized])
    category = normalized or "unknown"
    return {"name": raw.strip(), "category": category, "mode": "unknown", "status": "unknown"}


def _normalize_tags(value: Any, notes: List[NormalizationNote], path: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()]
    if not isinstance(value, list):
        notes.append(
            NormalizationNote(path=path, message="tags must be an array; defaulted.", original_value=value)
        )
        return []
    tags = []
    for item in value:
        if isinstance(item, str) and item.strip():
            tags.append(item.strip())
    return tags


def _normalize_unknowns(
    value: Any,
    notes: List[NormalizationNote],
    path: str,
    unknowns_keys: set[str],
) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        notes.append(
            NormalizationNote(path=path, message="unknowns must be an array; defaulted.", original_value=value)
        )
        return []

    unknowns: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            unknowns.append({"field": "unknown", "reason": item, "question_hint": ""})
            continue
        if not isinstance(item, dict):
            notes.append(
                NormalizationNote(
                    path=f"{path}[{index}]",
                    message="unknown entry invalid; skipped.",
                    original_value=item,
                )
            )
            continue
        unknown = dict(item)
        unknown["field"] = unknown.get("field") if isinstance(unknown.get("field"), str) else "unknown"
        unknown["reason"] = unknown.get("reason") if isinstance(unknown.get("reason"), str) else "unknown"
        unknown["question_hint"] = (
            unknown.get("question_hint") if isinstance(unknown.get("question_hint"), str) else ""
        )
        _strip_extra_fields(unknown, unknowns_keys, notes, f"{path}[{index}]")
        unknowns.append(unknown)
    return unknowns


def _normalize_properties(value: Any, notes: List[NormalizationNote], path: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        notes.append(
            NormalizationNote(path=path, message="properties must be an object; defaulted.", original_value=value)
        )
        return {}
    return dict(value)


def _normalize_provenance(
    value: Any, config: NormalizationConfig, notes: List[NormalizationNote], path: str
) -> Dict[str, Any]:
    if not isinstance(value, dict):
        notes.append(
            NormalizationNote(
                path=path,
                message="provenance missing or invalid; defaulted.",
                original_value=value,
            )
        )
        return {
            "source": config.default_provenance_source,
            "method": config.default_provenance_method,
            "confidence": config.default_confidence,
            "evidence": list(config.default_evidence),
        }

    provenance = dict(value)
    _apply_key_aliases(provenance, config.key_aliases_provenance, notes, path)
    source = provenance.get("source")
    provenance["source"] = source.strip() if isinstance(source, str) and source.strip() else config.default_provenance_source
    method = provenance.get("method")
    provenance["method"] = method.strip() if isinstance(method, str) and method.strip() else config.default_provenance_method
    provenance["confidence"] = _normalize_confidence(
        provenance.get("confidence"), config.default_confidence, notes, f"{path}.confidence"
    )
    evidence = provenance.get("evidence")
    if isinstance(evidence, str):
        provenance["evidence"] = [evidence.strip()] if evidence.strip() else list(config.default_evidence)
    elif isinstance(evidence, list):
        provenance["evidence"] = [item for item in evidence if isinstance(item, str) and item.strip()] or list(
            config.default_evidence
        )
    else:
        provenance["evidence"] = list(config.default_evidence)
    return provenance


def _normalize_confidence(
    value: Any, default: float, notes: List[NormalizationNote], path: str
) -> float:
    raw = value
    confidence: Optional[float] = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        confidence = float(value)
    elif isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            confidence = float(cleaned)
        except ValueError:
            confidence = None
    if confidence is None:
        notes.append(
            NormalizationNote(
                path=path,
                message="confidence missing or invalid; defaulted.",
                original_value=raw,
                normalized_value=default,
            )
        )
        return default
    if confidence > 1.0 and confidence <= 100.0:
        confidence = confidence / 100.0
    if confidence < 0.0:
        confidence = 0.0
    if confidence > 1.0:
        confidence = 1.0
    return round(confidence, 4)


def _apply_key_aliases(
    data: Dict[str, Any],
    aliases: Dict[str, str],
    notes: List[NormalizationNote],
    path: str,
) -> None:
    for alias, canonical in aliases.items():
        if alias in data and canonical not in data:
            data[canonical] = data.pop(alias)
            notes.append(
                NormalizationNote(
                    path=f"{path}.{canonical}",
                    message=f"Mapped field '{alias}' to '{canonical}'.",
                )
            )


def _normalize_enum_value(value: Any, key: str, config: NormalizationConfig) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = _enum_clean(value)
    synonyms = config.synonyms.get(key, {})
    return synonyms.get(cleaned, cleaned)


def _enum_clean(value: str) -> str:
    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    cleaned = _ENUM_CLEAN_RE.sub("_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def _title_from_enum(value: str) -> str:
    if not value:
        return "Unknown"
    return value.replace("_", " ").title()


def _collect_ids(items: Iterable[Any]) -> List[str]:
    ids = []
    for item in items:
        if isinstance(item, dict):
            item_id = item.get("id")
            if isinstance(item_id, str):
                ids.append(item_id)
    return ids


def _node_name_index(nodes: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    name_to_id: Dict[str, str] = {}
    for node in nodes:
        node_id = node.get("id")
        name = node.get("name")
        if isinstance(node_id, str) and isinstance(name, str):
            name_to_id[name] = node_id
            name_to_id[name.lower()] = node_id
    return name_to_id


def _move_unsupported_fields(
    item: Dict[str, Any],
    allowed_keys: set[str],
    properties: Dict[str, Any],
    config: NormalizationConfig,
    notes: List[NormalizationNote],
    path: str,
    controls: List[Dict[str, Any]],
) -> None:
    for key in list(item.keys()):
        if key in allowed_keys:
            continue
        value = item.pop(key)
        control_alias = config.control_field_aliases.get(key)
        if control_alias:
            controls.append(_control_from_string(control_alias, config))
            notes.append(
                NormalizationNote(
                    path=f"{path}.controls",
                    message=f"Converted field '{key}' into control.",
                    original_value=value,
                )
            )
            continue
        if key not in properties:
            properties[key] = value
        else:
            properties.setdefault("unsupported", {})[key] = value
        notes.append(
            NormalizationNote(
                path=f"{path}.properties.{key}",
                message="Moved unsupported field into properties.",
                original_value=value,
            )
        )


def _strip_extra_fields(
    item: Dict[str, Any],
    allowed_keys: set[str],
    notes: List[NormalizationNote],
    path: str,
) -> None:
    for key in list(item.keys()):
        if key in allowed_keys:
            continue
        value = item.pop(key)
        notes.append(
            NormalizationNote(
                path=f"{path}.{key}",
                message="Dropped unsupported nested field.",
                original_value=value,
            )
        )
