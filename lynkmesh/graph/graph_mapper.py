# lynkmesh/graph/graph_mapper.py
"""
Graph Mapper - Converts GraphCore into different representations.
Supports NetworkX, subgraph extraction, and filtered exports.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from lynkmesh.core.graph_core import GraphCore


class GraphMapper:
    """Maps GraphCore to various output formats."""

    # ------------------------------------------------------------------
    # Helper: Cypher string escaping
    # ------------------------------------------------------------------
    @staticmethod
    def _escape_cypher(value: Any) -> str:
        """Escape special characters for Cypher query literals."""
        if value is None:
            return ""
        s = str(value)
        # Backslash must be escaped first, then double quote
        s = s.replace("\\", "\\\\")
        s = s.replace('"', '\\"')
        # Optional: handle newlines if needed (Neo4j accepts \n as string)
        return s

    # ------------------------------------------------------------------
    # Conversion to NetworkX
    # ------------------------------------------------------------------
    def to_networkx(self, graph: GraphCore) -> Any:
        """
        Convert GraphCore to a NetworkX DiGraph.
        Requires networkx to be installed.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("NetworkX is required for to_networkx(). Install with `pip install networkx`.")

        G = nx.DiGraph()

        # Add nodes with attributes
        for node_id, node in graph.nodes.items():
            G.add_node(node_id, **node)

        # Add edges with attributes
        for edge in graph.edges:
            G.add_edge(
                edge["from"],
                edge["to"],
                type=edge["type"],
                confidence=edge.get("confidence", 1.0),
                **edge.get("metadata", {})
            )

        return G

    def to_adjacency_list(self, graph: GraphCore) -> Dict[str, List[str]]:
        """
        Convert to a simple adjacency list (source -> list of targets).
        Edge types are ignored.
        """
        adj = {}
        for node_id in graph.nodes:
            adj[node_id] = graph.get_neighbors(node_id)
        return adj

    # ------------------------------------------------------------------
    # Filtering and subgraph extraction (preserve original IDs)
    # ------------------------------------------------------------------
    def filter_by_layer(self, graph: GraphCore, layers: List[str]) -> GraphCore:
        """
        Create a new GraphCore containing only nodes of specified layers,
        plus edges between them. **Original node IDs are preserved.**
        """
        filtered = GraphCore()
        # Copy matching nodes with original IDs
        for node_id, node in graph.nodes.items():
            if node.get("layer") in layers:
                filtered.add_node(
                    node_id=node_id,                # preserve original ID
                    node_type=node["type"],
                    name=node["name"],
                    file_path=node.get("file_path"),
                    layer=node.get("layer"),
                    extra=node.get("extra", {}).copy()
                )
                # copy other attributes if any
                for k, v in node.items():
                    if k not in ("id", "type", "name", "file", "file_path", "layer", "extra"):
                        filtered.nodes[node_id][k] = v

        # Copy edges where both endpoints exist in filtered graph
        for edge in graph.edges:
            src = edge["from"]
            tgt = edge["to"]
            if src in filtered.nodes and tgt in filtered.nodes:
                filtered.add_edge(
                    src,
                    tgt,
                    edge_type=edge["type"],
                    confidence=edge.get("confidence", 1.0),
                    metadata=edge.get("metadata", {})
                )

        return filtered

    def extract_subgraph(
        self,
        graph: GraphCore,
        root_node_ids: List[str],
        direction: str = "downstream",
        max_depth: int = 10
    ) -> GraphCore:
        """
        Extract a subgraph starting from given root nodes.
        direction: 'downstream' (following outgoing edges),
                   'upstream' (incoming edges),
                   'both' (bidirectional BFS).
        **Original node IDs are preserved.**
        """
        sub = GraphCore()
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(nid, 0) for nid in root_node_ids if graph.has_node(nid)]

        # First pass: collect nodes to include
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)

            if direction in ("downstream", "both"):
                for neighbor in graph.get_neighbors(current):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
            if direction in ("upstream", "both"):
                for dependent in graph.get_dependents(current):
                    if dependent not in visited:
                        queue.append((dependent, depth + 1))

        # Copy selected nodes with original IDs
        for node_id in visited:
            node = graph.get_node(node_id)
            if node:
                sub.add_node(
                    node_id=node_id,                # preserve original ID
                    node_type=node["type"],
                    name=node["name"],
                    file_path=node.get("file_path"),
                    layer=node.get("layer"),
                    extra=node.get("extra", {}).copy()
                )
                # copy other attributes
                for k, v in node.items():
                    if k not in ("id", "type", "name", "file", "file_path", "layer", "extra"):
                        sub.nodes[node_id][k] = v

        # Copy edges between selected nodes
        for edge in graph.edges:
            src = edge["from"]
            tgt = edge["to"]
            if src in sub.nodes and tgt in sub.nodes:
                sub.add_edge(
                    src,
                    tgt,
                    edge_type=edge["type"],
                    confidence=edge.get("confidence", 1.0),
                    metadata=edge.get("metadata", {})
                )

        return sub

    # ------------------------------------------------------------------
    # Cypher export with proper escaping
    # ------------------------------------------------------------------
    def to_cypher_script(self, graph: GraphCore) -> str:
        """
        Generate a Cypher script to import the graph into Neo4j.
        Properly escapes special characters.
        """
        lines = []
        # Create nodes
        for node_id, node in graph.nodes.items():
            label = node["type"].capitalize()
            props = {
                "id": node_id,
                "name": node["name"],
                "file": node.get("file_path", ""),
                "layer": node.get("layer", "")
            }
            # Build properties string with escaping
            props_str = ", ".join(
                f'{k}: "{self._escape_cypher(v)}"'
                for k, v in props.items()
                if v is not None and v != ""
            )
            lines.append(f"CREATE (:{label} {{{props_str}}});")

        # Create edges
        for edge in graph.edges:
            rel_type = edge["type"].upper()
            lines.append(
                f"MATCH (a {{id: '{self._escape_cypher(edge['from'])}'}}), "
                f"(b {{id: '{self._escape_cypher(edge['to'])}'}})\n"
                f"CREATE (a)-[:{rel_type}]->(b);"
            )

        return "\n".join(lines)