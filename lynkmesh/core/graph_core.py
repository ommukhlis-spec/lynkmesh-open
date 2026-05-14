# lynkmesh/core/graph_core.py
"""
Graph Core v3 - Production-grade knowledge graph with fast indexing.
Optimized for O(1) edge/node lookup, type-based adjacency, and extensibility.
"""

import uuid
from collections import defaultdict
from typing import Dict, List, Set, Any, Optional, Tuple


class GraphCore:
    """Advanced graph container optimized for reasoning and traversal."""

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------
    DEFAULT_SEMANTIC = "generic"
    CALL_EDGE_TYPES = {
        "calls_confirmed",
        "calls_heuristic",
        "calls_external",
        "calls_di",
        "depends_on"
    }

    def __init__(self):
        # Primary storage
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

        # Indexes for fast lookup
        self.edges_by_id: Dict[str, Dict[str, Any]] = {}
        self.edges_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.edges_by_flow: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._edge_index: Set[Tuple[str, str, str]] = set()  # (source, target, edge_type)

        # Adjacency: source -> set of (target, edge_id)
        self.adj_out: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        self.adj_in: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)

        # Optimized adjacency: edge_type -> source -> set of target
        self.adj_out_by_type: Dict[str, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self.adj_in_by_type: Dict[str, Dict[str, Set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

        # Fast node lookup by qualified name
        self.nodes_by_qname: Dict[str, str] = {}

        # Metadata
        self.meta: Dict[str, Any] = {
            "version": "3.0",
            "engine": "LynkMesh Production Core"
        }

        # Stage 3.0.0 — Version lifecycle state (architecture spec §20).
        # Populated by Orchestrator via _assign_initial_metadata (post-build)
        # then _finalize_content_hash (post-all-mutations). Until both run,
        # the `version` property raises RuntimeError. Forward references for
        # typing only; concrete imports are lazy inside methods to preserve
        # tier-0 dependency hygiene.
        self._version_metadata: Optional["VersionMetadata"] = None  # type: ignore[name-defined]
        self._content_hash: Optional[str] = None
        self._version: Optional["GraphVersion"] = None  # type: ignore[name-defined]

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------
    def _generate_id(self) -> str:
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Node Management
    # ------------------------------------------------------------------
    def add_node(
        self,
        node_id: Optional[str] = None,
        node_type: str = "unknown",
        name: str = "",
        qualified_name: Optional[str] = None,
        file_path: Optional[str] = None,
        layer: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        if node_id is None:
            node_id = self._generate_id()
        elif node_id in self.nodes:
            existing = self.nodes[node_id]
            if extra:
                existing.setdefault("extra", {}).update(extra)
            for k, v in kwargs.items():
                if k != "id":
                    existing[k] = v
            if qualified_name:
                old_qname = existing.get("qualified_name")
                if old_qname and old_qname in self.nodes_by_qname:
                    del self.nodes_by_qname[old_qname]
                existing["qualified_name"] = qualified_name
                self.nodes_by_qname[qualified_name] = node_id
            return node_id

        if not qualified_name:
            if node_type == "method" and "class" in kwargs:
                qualified_name = f"{kwargs['class']}::{name}"
            elif node_type == "class":
                qualified_name = name
            else:
                qualified_name = name

        node = {
            "id": node_id,
            "type": node_type,
            "name": name,
            "qualified_name": qualified_name,
            "file": file_path,
            "file_path": file_path,
            "layer": layer or "unknown",
            "extra": extra or {},
            **kwargs
        }

        node["extra"].setdefault("layer", node["layer"])
        node["extra"].setdefault("importance", self._default_importance(node_type, layer))
        node["extra"].setdefault("entry", False)

        self.nodes[node_id] = node
        self.nodes_by_qname[qualified_name] = node_id
        return node_id

    def _default_importance(self, node_type: str, layer: Optional[str]) -> int:
        if layer == "controller":
            return 5
        elif layer == "service":
            return 4
        elif layer == "repository":
            return 3
        elif layer == "model":
            return 2
        elif node_type == "class":
            return 3
        elif node_type == "method":
            return 2
        return 1

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    # ------------------------------------------------------------------
    # Edge Management
    # ------------------------------------------------------------------
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        confidence: float = 1.0,
        semantic: Optional[str] = None,
        flow_id: Optional[str] = None,
        weight: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        if source_id not in self.nodes or target_id not in self.nodes:
            return None

        key = (source_id, target_id, edge_type)
        if key in self._edge_index:
            return None

        if semantic is None:
            semantic = edge_type

        edge_id = self._generate_id()
        edge = {
            "id": edge_id,
            "from": source_id,
            "to": target_id,
            "type": edge_type,
            "semantic": semantic,
            "confidence": float(confidence)
        }

        if flow_id:
            edge["flow_id"] = flow_id
            self.edges_by_flow[flow_id].append(edge)
        if weight is not None:
            edge["weight"] = weight
        if metadata:
            edge["metadata"] = metadata

        self.edges.append(edge)
        self.edges_by_id[edge_id] = edge
        self._edge_index.add(key)
        self.edges_by_type[edge_type].append(edge)

        self.adj_out[source_id].add((target_id, edge_id))
        self.adj_in[target_id].add((source_id, edge_id))

        self.adj_out_by_type[edge_type][source_id].add(target_id)
        self.adj_in_by_type[edge_type][target_id].add(source_id)

        return edge_id

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------
    def get_neighbors(self, node_id: str, edge_type: Optional[str] = None) -> List[str]:
        if edge_type:
            return list(self.adj_out_by_type.get(edge_type, {}).get(node_id, set()))
        return [tgt for tgt, _ in self.adj_out.get(node_id, set())]

    def get_neighbors_by_type(self, node_id: str, edge_types: Set[str]) -> List[str]:
        result: Set[str] = set()
        for etype in edge_types:
            result.update(self.adj_out_by_type.get(etype, {}).get(node_id, set()))
        return list(result)

    def get_dependents(self, node_id: str, edge_type: Optional[str] = None) -> List[str]:
        if edge_type:
            return list(self.adj_in_by_type.get(edge_type, {}).get(node_id, set()))
        return [src for src, _ in self.adj_in.get(node_id, set())]

    def get_dependents_by_type(self, node_id: str, edge_types: Set[str]) -> List[str]:
        result: Set[str] = set()
        for etype in edge_types:
            result.update(self.adj_in_by_type.get(etype, {}).get(node_id, set()))
        return list(result)

    def _get_edge_by_id(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """O(1) edge lookup (internal)."""
        return self.edges_by_id.get(edge_id)

    # --- NEW Public API -------------------------------------------------
    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """Public API to retrieve an edge by its ID. Replaces direct _get_edge_by_id."""
        return self._get_edge_by_id(edge_id)

    def get_edges_between(self, source: str, target: str) -> List[Dict[str, Any]]:
        result = []
        for tgt, eid in self.adj_out.get(source, set()):
            if tgt == target:
                edge = self._get_edge_by_id(eid)
                if edge:
                    result.append(edge)
        return result

    def get_edges_by_semantic(self, semantic: str) -> List[Dict[str, Any]]:
        return [e for e in self.edges if e.get("semantic") == semantic]

    def get_edges_by_type(self, edge_type: str) -> List[Dict[str, Any]]:
        return self.edges_by_type.get(edge_type, [])

    # ------------------------------------------------------------------
    # Fast Call Graph Helpers
    # ------------------------------------------------------------------
    def get_call_neighbors(self, node_id: str) -> List[str]:
        return self.get_neighbors_by_type(node_id, self.CALL_EDGE_TYPES)

    def get_call_dependents(self, node_id: str) -> List[str]:
        return self.get_dependents_by_type(node_id, self.CALL_EDGE_TYPES)

    def has_call_edge(self, source: str, target: str) -> bool:
        for etype in self.CALL_EDGE_TYPES:
            if target in self.adj_out_by_type.get(etype, {}).get(source, set()):
                return True
        return False

    def has_edge(self, source: str, target: str, edge_type: Optional[str] = None) -> bool:
        if edge_type:
            return target in self.adj_out_by_type.get(edge_type, {}).get(source, set())
        for tgt, _ in self.adj_out.get(source, set()):
            if tgt == target:
                return True
        return False

    # ------------------------------------------------------------------
    # Node Filtering
    # ------------------------------------------------------------------
    def find_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        return [node for node in self.nodes.values() if node.get("type") == node_type]

    def find_nodes_by_layer(self, layer: str) -> List[Dict[str, Any]]:
        return [node for node in self.nodes.values() if node.get("layer") == layer]

    def find_nodes_by_qualified_name(self, qname: str) -> Optional[Dict[str, Any]]:
        nid = self.nodes_by_qname.get(qname)
        return self.nodes.get(nid) if nid else None

    # ------------------------------------------------------------------
    # Statistics & Export
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "files": sum(1 for n in self.nodes.values() if n["type"] == "file"),
            "classes": sum(1 for n in self.nodes.values() if n["type"] == "class"),
            "methods": sum(1 for n in self.nodes.values() if n["type"] == "method"),
            "functions": sum(1 for n in self.nodes.values() if n["type"] == "function"),
            "external": sum(1 for n in self.nodes.values() if n["type"] == "external")
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
            "meta": self.meta,
            "stats": self.stats()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphCore":
        instance = cls()
        for node in data.get("nodes", []):
            node_id = node["id"]
            instance.nodes[node_id] = node
            qname = node.get("qualified_name")
            if qname:
                instance.nodes_by_qname[qname] = node_id
        for edge in data.get("edges", []):
            instance._add_edge_internal(
                edge["from"],
                edge["to"],
                edge["type"],
                confidence=edge.get("confidence", 1.0),
                semantic=edge.get("semantic"),
                flow_id=edge.get("flow_id"),
                weight=edge.get("weight"),
                metadata=edge.get("metadata")
            )
        if "meta" in data:
            instance.meta.update(data["meta"])
        return instance

    def _add_edge_internal(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        confidence: float = 1.0,
        semantic: Optional[str] = None,
        flow_id: Optional[str] = None,
        weight: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        key = (source_id, target_id, edge_type)
        if key in self._edge_index:
            return None
        if semantic is None:
            semantic = edge_type
        edge_id = self._generate_id()
        edge = {
            "id": edge_id,
            "from": source_id,
            "to": target_id,
            "type": edge_type,
            "semantic": semantic,
            "confidence": float(confidence)
        }
        if flow_id:
            edge["flow_id"] = flow_id
            self.edges_by_flow[flow_id].append(edge)
        if weight is not None:
            edge["weight"] = weight
        if metadata:
            edge["metadata"] = metadata
        self.edges.append(edge)
        self.edges_by_id[edge_id] = edge
        self._edge_index.add(key)
        self.edges_by_type[edge_type].append(edge)
        self.adj_out[source_id].add((target_id, edge_id))
        self.adj_in[target_id].add((source_id, edge_id))
        self.adj_out_by_type[edge_type][source_id].add(target_id)
        self.adj_in_by_type[edge_type][target_id].add(source_id)
        return edge_id

    def update_importance(self, node_id: str, new_importance: int) -> None:
        node = self.nodes.get(node_id)
        if node:
            node.setdefault("extra", {})
            node["extra"]["importance"] = new_importance

    # ------------------------------------------------------------------
    # Stage 3.0.0 — Version lifecycle (architecture spec §20)
    # ------------------------------------------------------------------

    def _assign_initial_metadata(
        self,
        project_path: str,
        git_commit: Optional[str] = None,
        graph_id_override: Optional[str] = None,
    ) -> None:
        """
        Internal lifecycle hook. Called by Orchestrator after structural
        build completes, before resolution/enrichment mutations begin.

        After this call:
            self._version_metadata is non-None (I9)
            self._content_hash is still None
            self._version is still None
            self.version raises RuntimeError (not yet finalized)
        """
        from lynkmesh.core.graph_version import VersionMetadata
        self._version_metadata = VersionMetadata.create(
            project_path=project_path,
            git_commit=git_commit,
            graph_id_override=graph_id_override,
        )

    def _finalize_content_hash(self) -> None:
        """
        Internal lifecycle hook. Called by Orchestrator after ALL mutation
        phases (resolution, enrichment, validation) complete.

        Computes deterministic content_hash and assembles GraphVersion (I10).
        After this call, self.version returns a valid GraphVersion.

        Raises:
            RuntimeError: if _assign_initial_metadata has not been called.
        """
        from lynkmesh.core.graph_version import GraphVersion, compute_content_hash
        if self._version_metadata is None:
            raise RuntimeError(
                "GraphCore._finalize_content_hash: metadata not yet assigned. "
                "_assign_initial_metadata must be called first."
            )
        self._content_hash = compute_content_hash(
            nodes=self.nodes.values(),
            edges=self.edges,
        )
        self._version = GraphVersion(
            metadata=self._version_metadata,
            content_hash=self._content_hash,
        )

    def _invalidate_version(self) -> None:
        """
        Internal lifecycle hook. Returns version state to 'metadata-only'
        (I21): _version_metadata preserved, _content_hash and _version
        cleared. Re-finalization requires another _finalize_content_hash call.

        Defined for Stage 3.5+ incremental update boundary. NOT auto-wired
        into any current mutation path in Stage 3.0.0 — current pipeline
        finalizes at the end of Orchestrator.run() with no further mutation.
        """
        self._content_hash = None
        self._version = None

    @property
    def version(self):
        """
        Public API: return the finalized GraphVersion for this graph.

        Returns:
            GraphVersion: the immutable version captured at pipeline finalization.

        Raises:
            RuntimeError: if the pipeline has not yet called
            _finalize_content_hash on this GraphCore instance.
        """
        if self._version is None:
            raise RuntimeError(
                "GraphCore.version: not yet finalized. "
                "Pipeline must call _finalize_content_hash() before accessing version."
            )
        return self._version