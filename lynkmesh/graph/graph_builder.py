# lynkmesh/graph/graph_builder.py
"""
Graph Builder - Constructs the STRUCTURAL layer of GraphCore from IR data.
PURE builder: file, class, method nodes and contains/defined_in edges.
No call resolution or behavior edges. That's delegated to CallResolver.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from lynkmesh.core.graph_core import GraphCore
from lynkmesh.core.symbol_registry import SymbolRegistry


class GraphBuilder:
    """Builds the structural skeleton of the knowledge graph."""

    EDGE_CONTAINS = "contains"
    EDGE_DEFINED_IN = "defined_in"

    SEMANTIC_CONTAINS = "structural_contains"
    SEMANTIC_DEFINED_IN = "structural_defined_in"

    ENTRY_METHODS = {"handle", "__invoke", "execute", "run", "index", "store", "update", "destroy"}
    CONTROLLER_ACTIONS = {"index", "store", "update", "destroy", "show", "create", "edit"}
    CLI_COMMANDS = {"handle", "fire", "execute"}
    JOB_METHODS = {"handle", "process"}

    def __init__(self):
        self.graph = GraphCore()
        self.symbols = SymbolRegistry()
        self._layer_cache: Dict[Tuple[Optional[str], Optional[str]], Tuple[str, float]] = {}

    def build_from_ir(self, ir_list: List[Dict[str, Any]]) -> GraphCore:
        self.graph = GraphCore()
        self.symbols = SymbolRegistry()
        self._layer_cache.clear()
        self._build_structure(ir_list)
        return self.graph

    def get_symbol_registry(self) -> SymbolRegistry:
        """Expose the registry for external resolvers (e.g., CallResolver)."""
        return self.symbols

    def _normalize_fqn(self, fqn: str) -> str:
        """Remove leading backslash from a fully qualified name."""
        if fqn:
            return fqn.lstrip("\\")
        return fqn

    def _select_return_type(self, explicit_rt: Optional[str], inferred_rt: Optional[str]) -> Optional[str]:
        """
        Merge explicit return type hint with inferred return type.
        Prioritaskan inferred jika explicit adalah 'mixed' atau None.
        """
        if not explicit_rt:
            return inferred_rt
        if explicit_rt.lower() in ("mixed", "void", "null", "never"):
            return inferred_rt or explicit_rt
        return explicit_rt

    def _normalize_method_return_types(self, raw: Any) -> Dict[str, str]:
        """
        Convert parser's method_return_types (dict or list) into a normalized dict.
        Handles both legacy and new parser formats gracefully.
        """
        if isinstance(raw, dict):
            return {self._normalize_fqn(k): v for k, v in raw.items()}
        if isinstance(raw, list):
            result = {}
            for entry in raw:
                if isinstance(entry, dict):
                    cls = entry.get("class") or entry.get("fqn") or ""
                    meth = entry.get("method") or entry.get("name") or ""
                    rtype = entry.get("return_type") or entry.get("type") or entry.get("returns")
                    if cls and meth and rtype:
                        key = self._normalize_fqn(f"{cls}::{meth}")
                        result[key] = rtype
                elif isinstance(entry, str) and "::" in entry:
                    # Could be "Class::method" but return type missing – skip
                    pass
            return result
        return {}

    def _build_structure(self, ir_list: List[Dict[str, Any]]) -> None:
        for ir in ir_list:
            if not isinstance(ir, dict):
                continue

            file_path = ir.get("file")
            namespace = ir.get("namespace")
            imports = ir.get("uses", [])

            # 🔥 Normalisasi method_return_types dari parser dengan aman
            raw_method_return_types = ir.get("method_return_types", {})
            normalized_mrt = self._normalize_method_return_types(raw_method_return_types)

            file_id = None
            if file_path:
                layer, conf = self._infer_layer(file_path, None)
                file_id = self.graph.add_node(
                    node_type="file",
                    name=file_path,
                    qualified_name=file_path,
                    file_path=file_path,
                    layer=layer,
                    extra={"imports": imports, "layer_confidence": conf}
                )

            for cls in ir.get("classes", []):
                if not isinstance(cls, dict):
                    continue
                class_name = cls.get("name")
                if not class_name:
                    continue

                fqn = cls.get("fqn")
                if not fqn:
                    fqn = f"{namespace}\\{class_name}" if namespace else class_name
                fqn = self._normalize_fqn(fqn)

                layer, conf = self._infer_layer(file_path, class_name)
                class_id = self.graph.add_node(
                    node_type="class",
                    name=fqn,
                    qualified_name=fqn,
                    file_path=file_path,
                    layer=layer,
                    extra={
                        "extends": cls.get("extends"),
                        "interfaces": cls.get("implements", []),
                        "traits": cls.get("traits", []),
                        "properties": cls.get("properties", []),   # FIX: penting untuk propagation
                        "layer_confidence": conf
                    }
                )
                if file_id:
                    self.graph.add_edge(class_id, file_id, self.EDGE_DEFINED_IN,
                                        semantic=self.SEMANTIC_DEFINED_IN)

                # Normalize extends, traits, implements sebelum registrasi
                parent = cls.get("extends")
                if isinstance(parent, list):
                    parent = parent[0] if parent else None
                elif not isinstance(parent, str):
                    parent = None

                traits = cls.get("traits", [])
                if not isinstance(traits, list):
                    traits = [traits] if traits else []

                interfaces = cls.get("implements", [])
                if not isinstance(interfaces, list):
                    interfaces = [interfaces] if interfaces else []

                self.symbols.register_class(
                    class_fqn=fqn, node_id=class_id, file_path=file_path,
                    parent_fqn=parent, traits=traits, interfaces=interfaces
                )

                for method in cls.get("methods", []):
                    if not isinstance(method, dict):
                        continue
                    method_name = method.get("name")
                    if not method_name:
                        continue

                    qualified_name = self._normalize_fqn(f"{fqn}::{method_name}")

                    # Gabungkan return type: eksplisit dari AST, lalu inferred dari parser
                    explicit_rt = method.get("return_type")
                    inferred_rt = normalized_mrt.get(qualified_name)
                    return_type = self._select_return_type(explicit_rt, inferred_rt)

                    # Normalisasi property_fetches: jika item adalah string, ubah menjadi dict
                    raw_property_fetches = method.get("property_fetches", [])
                    normalized_property_fetches = [
                        {"property": pf, "type": ""} if isinstance(pf, str) else pf
                        for pf in raw_property_fetches
                    ]

                    method_id = self.graph.add_node(
                        node_type="method", name=method_name, qualified_name=qualified_name,
                        file_path=file_path, layer=layer,
                        extra={
                            "class": fqn,
                            "calls": method.get("calls", []),
                            "imports": imports,
                            "visibility": method.get("visibility", "public"),
                            "params": method.get("params", []),
                            "layer_confidence": conf,
                            "return_type": return_type,   # untuk TypeRegistry

                            # 🔥 KRUSIAL untuk propagasi tipe di CallResolver
                            "instantiations": method.get("instantiations", []),
                            "assignments": method.get("assignments", []),
                            "property_fetches": normalized_property_fetches,
                            "static_property_fetches": method.get("static_property_fetches", []),
                            "constant_fetches": method.get("constant_fetches", []),
                            "returns": method.get("returns", []),
                            "sql_strings": method.get("sql_strings", []),
                        }
                    )
                    self.graph.add_edge(class_id, method_id, self.EDGE_CONTAINS,
                                        semantic=self.SEMANTIC_CONTAINS)
                    if file_id:
                        self.graph.add_edge(method_id, file_id, self.EDGE_DEFINED_IN,
                                            semantic=self.SEMANTIC_DEFINED_IN)
                    self.symbols.register_method(method_name, method_id, fqn, file_path)

                    entry_type = self._get_entry_type(method_name, layer, file_path)
                    if entry_type:
                        node = self.graph.get_node(method_id)
                        if node:
                            node["entry"] = True
                            node["extra"]["entry"] = True
                            node["extra"]["entry_type"] = entry_type

            for func in ir.get("functions", []):
                if not isinstance(func, dict):
                    continue
                func_name = func.get("name")
                if not func_name:
                    continue
                qualified_name = self._normalize_fqn(f"{namespace}\\{func_name}" if namespace else func_name)
                layer, conf = self._infer_layer(file_path, None)
                func_id = self.graph.add_node(
                    node_type="function", name=func_name, qualified_name=qualified_name,
                    file_path=file_path, layer=layer,
                    extra={
                        "calls": func.get("calls", []),
                        "imports": imports,
                        "params": func.get("params", []),
                        "return_type": func.get("return_type"),

                        # Behavioral metadata for functions too
                        "instantiations": func.get("instantiations", []),
                        "assignments": func.get("assignments", []),
                        "property_fetches": func.get("property_fetches", []),
                        "static_property_fetches": func.get("static_property_fetches", []),
                        "returns": func.get("returns", []),

                        "layer_confidence": conf
                    }
                )
                if file_id:
                    self.graph.add_edge(func_id, file_id, self.EDGE_DEFINED_IN,
                                        semantic=self.SEMANTIC_DEFINED_IN)
                self.symbols.register_function(func_name, func_id, file_path)

    def _infer_layer(self, file_path: Optional[str], class_name: Optional[str]) -> Tuple[str, float]:
        """
        Infer architectural layer from file path and class name.
        Enhanced to use FQN and namespace parts for better accuracy.
        """
        if not file_path and not class_name:
            return "unknown", 0.0
        key = (file_path, class_name)
        if key in self._layer_cache:
            return self._layer_cache[key]

        path_lower = (file_path or "").lower()
        name_lower = (class_name or "").lower()

        layer = "unknown"
        conf = 0.5

        # 1. Check class name first (strongest signal)
        if name_lower.endswith("controller"):
            layer, conf = "controller", 0.95
        elif name_lower.endswith("service"):
            layer, conf = "service", 0.9
        elif name_lower.endswith("repository"):
            layer, conf = "repository", 0.9
        elif name_lower.endswith("model"):
            layer, conf = "model", 0.9
        elif name_lower.endswith("middleware"):
            layer, conf = "middleware", 0.9
        elif name_lower.endswith("provider"):
            layer, conf = "infrastructure", 0.8
        elif name_lower.endswith("factory"):
            layer, conf = "domain", 0.8
        elif name_lower.endswith("observer"):
            layer, conf = "domain", 0.8
        elif "controller" in name_lower:
            layer, conf = "controller", 0.85
        elif "service" in name_lower:
            layer, conf = "service", 0.85
        elif "repo" in name_lower:
            layer, conf = "repository", 0.85
        elif "model" in name_lower:
            layer, conf = "model", 0.85

        # 2. Check FQN namespace parts
        elif "\\controllers\\" in name_lower or "\\controller\\" in name_lower:
            layer, conf = "controller", 0.85
        elif "\\services\\" in name_lower or "\\service\\" in name_lower:
            layer, conf = "service", 0.85
        elif "\\repositories\\" in name_lower or "\\repository\\" in name_lower:
            layer, conf = "repository", 0.85
        elif "\\models\\" in name_lower or "\\model\\" in name_lower:
            layer, conf = "model", 0.85
        elif "\\middleware\\" in name_lower:
            layer, conf = "middleware", 0.85
        elif "\\providers\\" in name_lower:
            layer, conf = "infrastructure", 0.85

        # 3. Fall back to path-based heuristics
        elif "/controllers/" in path_lower or "\\controllers\\" in path_lower:
            layer, conf = "controller", 0.85
        elif "/services/" in path_lower or "\\services\\" in path_lower:
            layer, conf = "service", 0.85
        elif "/repositories/" in path_lower or "\\repositories\\" in path_lower:
            layer, conf = "repository", 0.85
        elif "/models/" in path_lower or "\\models\\" in path_lower:
            layer, conf = "model", 0.85
        elif "/middleware/" in path_lower or "\\middleware\\" in path_lower:
            layer, conf = "middleware", 0.85
        elif "controller" in path_lower:
            layer, conf = "controller", 0.7
        elif "service" in path_lower:
            layer, conf = "service", 0.7
        elif "repo" in path_lower:
            layer, conf = "repository", 0.7
        elif "model" in path_lower:
            layer, conf = "model", 0.7
        elif "domain" in path_lower:
            layer, conf = "domain", 0.6
        elif "infra" in path_lower:
            layer, conf = "infrastructure", 0.6
        else:
            layer, conf = "unknown", 0.5

        self._layer_cache[key] = (layer, conf)
        return layer, conf

    def _get_entry_type(self, method_name: str, layer: str, file_path: Optional[str]) -> Optional[str]:
        name_lower = method_name.lower()
        path_lower = (file_path or "").lower()
        if layer == "controller" and name_lower in self.CONTROLLER_ACTIONS:
            return "http"
        if "command" in path_lower or "console" in path_lower:
            if name_lower in self.CLI_COMMANDS:
                return "cli"
        if "job" in path_lower or name_lower in self.JOB_METHODS:
            return "job"
        if name_lower in self.ENTRY_METHODS:
            return "http" if layer == "controller" else "generic"
        return None