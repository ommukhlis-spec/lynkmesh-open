# lynkmesh/graph/graph_validator.py
"""
Graph Validator - Checks structural integrity of the built graph.
Produces errors, warnings, and a validation report.
"""

from typing import Dict, Any, List, Set
from lynkmesh.core.graph_core import GraphCore


class GraphValidator:
    """Validates a GraphCore instance for consistency and completeness."""

    def validate(self, graph: GraphCore) -> Dict[str, Any]:
        """
        Perform a full validation of the graph.

        Returns:
            Dictionary with keys:
                valid: bool
                errors: List[str]
                warnings: List[str]
                stats: Dict[str, int]
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Check for orphan edges (source or target missing)
        node_ids: Set[str] = set(graph.nodes.keys())
        for edge in graph.edges:
            src = edge.get("from")
            tgt = edge.get("to")
            if src not in node_ids:
                errors.append(f"Edge {edge.get('id')} has missing source node: {src}")
            if tgt not in node_ids:
                errors.append(f"Edge {edge.get('id')} has missing target node: {tgt}")

        # 2. Check that method/function nodes have a parent (class or file)
        for node_id, node in graph.nodes.items():
            if node.get("type") in ("method", "function"):
                has_parent = False
                for src, edge_type in graph.adj_in.get(node_id, set()):
                    if node["type"] == "method" and edge_type == "contains":
                        has_parent = True
                        break
                    if node["type"] == "function" and edge_type == "defined_in":
                        has_parent = True
                        break
                if not has_parent:
                    warnings.append(f"{node['type'].capitalize()} '{node['name']}' has no parent container")

        # 3. Check for duplicate node definitions (same type, name, file)
        seen: Dict[tuple, str] = {}
        for node_id, node in graph.nodes.items():
            key = (node.get("type"), node.get("name"), node.get("file_path"))
            if key in seen:
                warnings.append(
                    f"Duplicate node: {node['type']} '{node['name']}' in {node.get('file_path')} "
                    f"(IDs: {seen[key]} and {node_id})"
                )
            else:
                seen[key] = node_id

        # 4. Check for unreachable nodes (no incoming edges)
        #    Exclude files, externals, and entry points (which are expected to have no callers)
        for node_id, node in graph.nodes.items():
            if node.get("type") in ("file", "external"):
                continue
            if node.get("entry"):        # explicitly marked entry points
                continue
            if not graph.adj_in.get(node_id):
                # Also check if it's a method/function with zero incoming edges but is an entry point by name?
                # Already handled by entry flag.
                warnings.append(f"Unreachable node (no incoming edges): {node['type']} '{node['name']}' ({node_id})")

        valid = len(errors) == 0

        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "stats": graph.stats()
        }