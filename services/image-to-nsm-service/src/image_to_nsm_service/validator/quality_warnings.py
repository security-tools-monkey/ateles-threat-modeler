from __future__ import annotations

from typing import Any, Dict, List


UNKNOWN_NODE_TYPE_RATIO = 0.5
UNKNOWN_EDGE_PROTOCOL_RATIO = 0.5
PROVENANCE_CONFIDENCE_THRESHOLD = 0.6


def _ratio(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


def warn_on_quality(payload: Dict[str, Any]) -> List[str]:
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    warnings: List[str] = []

    if isinstance(nodes, list) and nodes:
        unknown_nodes = sum(1 for node in nodes if node.get("type") == "unknown")
        if _ratio(unknown_nodes, len(nodes)) > UNKNOWN_NODE_TYPE_RATIO:
            warnings.append("Too many nodes have type=unknown")

        identity_nodes = [node for node in nodes if node.get("kind") == "identity"]
        if not identity_nodes:
            warnings.append("No identity nodes were found")

        path_lengths = [
            len(node.get("trust_boundary", {}).get("path", []))
            for node in nodes
            if isinstance(node, dict)
        ]
        if path_lengths and max(path_lengths) <= 1:
            warnings.append("No trust boundary path hierarchy detected")

    if isinstance(edges, list) and edges:
        unknown_protocols = sum(1 for edge in edges if edge.get("protocol") == "unknown")
        if _ratio(unknown_protocols, len(edges)) > UNKNOWN_EDGE_PROTOCOL_RATIO:
            warnings.append("Too many edges have protocol=unknown")

    confidences: List[float] = []
    for node in nodes if isinstance(nodes, list) else []:
        provenance = node.get("provenance") if isinstance(node, dict) else None
        confidence = provenance.get("confidence") if isinstance(provenance, dict) else None
        if isinstance(confidence, (int, float)):
            confidences.append(float(confidence))
    for edge in edges if isinstance(edges, list) else []:
        provenance = edge.get("provenance") if isinstance(edge, dict) else None
        confidence = provenance.get("confidence") if isinstance(provenance, dict) else None
        if isinstance(confidence, (int, float)):
            confidences.append(float(confidence))
    if confidences and all(value < PROVENANCE_CONFIDENCE_THRESHOLD for value in confidences):
        warnings.append("All provenance confidence values are below threshold")

    return warnings
