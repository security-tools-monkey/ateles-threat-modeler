from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


IDENTITY_TYPES: Set[str] = {
    "external_user",
    "internal_user",
    "admin",
    "service_account",
    "workload_identity",
    "third_party",
}


def _duplicate_ids(items: Iterable[Dict[str, Any]], kind: str) -> List[str]:
    seen: Set[str] = set()
    duplicates: Set[str] = set()
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        if item_id in seen:
            duplicates.add(item_id)
        seen.add(item_id)
    return [f"Duplicate {kind} id '{dup_id}'" for dup_id in sorted(duplicates)]


def _validate_edges_reference_nodes(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    node_ids = {node.get("id") for node in nodes if isinstance(node.get("id"), str)}
    errors: List[str] = []
    for index, edge in enumerate(edges):
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and source not in node_ids:
            errors.append(f"edges[{index}].source references unknown node id {source}")
        if isinstance(target, str) and target not in node_ids:
            errors.append(f"edges[{index}].target references unknown node id {target}")
    return errors


def _validate_trust_boundaries(nodes: List[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    for index, node in enumerate(nodes):
        trust_boundary = node.get("trust_boundary")
        if not isinstance(trust_boundary, dict):
            errors.append(f"nodes[{index}].trust_boundary is required")
            continue
        path = trust_boundary.get("path")
        if not isinstance(path, list) or not path:
            errors.append(f"nodes[{index}].trust_boundary.path must be a non-empty array")
    return errors


def _validate_node_kind_type(nodes: List[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    for index, node in enumerate(nodes):
        kind = node.get("kind")
        node_type = node.get("type")
        if not isinstance(kind, str) or not isinstance(node_type, str):
            continue
        if node_type == "unknown":
            continue
        if kind == "identity" and node_type not in IDENTITY_TYPES:
            errors.append(f"nodes[{index}].type does not match kind identity")
        if kind == "object" and node_type in IDENTITY_TYPES:
            errors.append(f"nodes[{index}].type does not match kind object")
    return errors


def validate_semantics(payload: Dict[str, Any]) -> List[str]:
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["nodes and edges must be arrays"]

    errors: List[str] = []
    errors.extend(_duplicate_ids(nodes, "node"))
    errors.extend(_duplicate_ids(edges, "edge"))
    errors.extend(_validate_edges_reference_nodes(nodes, edges))
    errors.extend(_validate_trust_boundaries(nodes))
    errors.extend(_validate_node_kind_type(nodes))
    return errors
