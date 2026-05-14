"""
Symbol Registry v4 – Multi-format AST, defensive parsing

- Builds index from parser output (list of per-file IR)
- Supports both legacy flat node lists and new nested structure
- Auto-generates stable node IDs when missing
"""

from collections import defaultdict
from typing import Dict, Set, Optional, List, Any


class SymbolRegistry:

    def __init__(self):
        # General symbol index
        self.symbol_to_nodes: Dict[str, Set[str]] = defaultdict(set)
        self.file_to_symbols: Dict[str, Set[str]] = defaultdict(set)

        # Class indexes
        self.class_fqn_to_node: Dict[str, str] = {}
        self.class_short_index: Dict[str, Set[str]] = defaultdict(set)

        # Method indexes
        self.class_method_index: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self.method_name_index: Dict[str, Set[str]] = defaultdict(set)
        self.global_method_index: Dict[str, Set[str]] = defaultdict(set)

        # Function index
        self.function_index: Dict[str, Set[str]] = defaultdict(set)

        # Relationships
        self.interface_implementations: Dict[str, Set[str]] = defaultdict(set)
        self.class_parent_map: Dict[str, Optional[str]] = {}
        self.class_traits_map: Dict[str, Set[str]] = defaultdict(set)

    # ==============================================================
    # BUILD – universal entry point
    # ==============================================================
    def build(self, ast_data):
        """
        Accepts:
          - list of per‑file IR dicts   (new parser)
          - list of flat node dicts     (legacy format)
          - GraphCore object (has .nodes)
        """
        # 1. Normalise to a list of node-like dicts
        if hasattr(ast_data, "nodes"):               # GraphCore
            nodes = list(ast_data.nodes.values())
        elif isinstance(ast_data, list):
            nodes = ast_data
        else:
            print("[SymbolRegistry] Unsupported AST format")
            return

        # 2. Detect format and dispatch
        if nodes and isinstance(nodes[0], dict) and "classes" in nodes[0]:
            # ** NEW FORMAT: list of file IR **
            self._build_from_file_ir_list(nodes)
        else:
            # ** LEGACY FORMAT: flat node list **
            self._build_from_flat_nodes(nodes)

        print(f"[SymbolRegistry] Classes: {len(self.class_fqn_to_node)}")
        print(f"[SymbolRegistry] Methods: {len(self.global_method_index)}")
        print(f"[SymbolRegistry] Functions: {len(self.function_index)}")

    # ----------------------------------------------------------
    # NEW FORMAT PROCESSOR
    # ----------------------------------------------------------
    def _build_from_file_ir_list(self, file_irs: List[Dict]):
        for file_ir in file_irs:
            file_path = file_ir.get("file", "")
            # Process classes inside this file
            for cls in file_ir.get("classes", []):
                if not isinstance(cls, dict):
                    continue
                class_fqn = cls.get("fqn") or cls.get("name")
                if not class_fqn:
                    continue

                # Use class_fqn as stable node_id (or generate)
                class_node_id = f"class::{class_fqn}"
                # Register the class itself
                self.register_class(
                    class_fqn=class_fqn,
                    node_id=class_node_id,
                    file_path=file_path,
                    parent_fqn=cls.get("extends"),
                    traits=cls.get("traits"),
                    interfaces=cls.get("implements"),
                )

                # Process methods inside the class
                for method in cls.get("methods", []):
                    if not isinstance(method, dict):
                        continue
                    method_name = method.get("name")
                    if not method_name:
                        continue

                    method_node_id = f"{class_fqn}::{method_name}"
                    self.register_method(
                        method_name=method_name,
                        node_id=method_node_id,
                        class_fqn=class_fqn,
                        file_path=file_path,
                    )

            # Also process top-level functions (if any)
            for func in file_ir.get("functions", []):
                if not isinstance(func, dict):
                    continue
                func_name = func.get("name")
                if not func_name:
                    continue
                func_node_id = f"func::{func_name}"
                self.register_function(
                    func_name=func_name,
                    node_id=func_node_id,
                    file_path=file_path,
                )

    # ----------------------------------------------------------
    # LEGACY FORMAT PROCESSOR (flat node list)
    # ----------------------------------------------------------
    def _build_from_flat_nodes(self, nodes: List[Dict]):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type") or node.get("kind")
            name = node.get("name")
            if not node_type or not name:
                continue

            node_id = node.get("id") or id(node)

            if node_type == "class":
                self.register_class(
                    class_fqn=name,
                    node_id=node_id,
                    file_path=node.get("file"),
                    parent_fqn=node.get("extends"),
                    traits=node.get("traits"),
                    interfaces=node.get("implements"),
                )
            elif node_type == "method":
                self.register_method(
                    method_name=name,
                    node_id=node_id,
                    class_fqn=node.get("class") or node.get("extra", {}).get("class"),
                    file_path=node.get("file"),
                )
            elif node_type == "function":
                self.register_function(
                    func_name=name,
                    node_id=node_id,
                    file_path=node.get("file"),
                )

    # ==============================================================
    # REGISTER HELPERS (unchanged logic, just refactored)
    # ==============================================================
    def register_class(self, class_fqn: str, node_id: str, file_path: Optional[str] = None,
                       parent_fqn: Optional[str] = None, traits: Optional[List[str]] = None,
                       interfaces: Optional[List[str]] = None):
        if not class_fqn:
            return

        self.class_fqn_to_node[class_fqn] = node_id

        short = class_fqn.split("\\")[-1].lower()
        self.class_short_index[short].add(node_id)

        if file_path:
            self.file_to_symbols[file_path].add(class_fqn)

        if parent_fqn:
            self.class_parent_map[class_fqn] = parent_fqn

        if traits:
            for t in traits:
                self.class_traits_map[class_fqn].add(t)

        if interfaces:
            for iface in interfaces:
                self.interface_implementations[iface].add(class_fqn)

        self._add_symbol(class_fqn, node_id)

    def register_method(self, method_name: str, node_id: str, class_fqn: Optional[str] = None,
                        file_path: Optional[str] = None):
        if not method_name:
            return

        method_lower = method_name.lower()

        self.method_name_index[method_lower].add(node_id)
        self.global_method_index[method_lower].add(node_id)

        if class_fqn:
            self.class_method_index[class_fqn][method_lower].add(node_id)
            self._add_symbol(f"{class_fqn}::{method_name}", node_id)

        if file_path:
            self.file_to_symbols[file_path].add(method_name)

        self._add_symbol(method_name, node_id)

    def register_function(self, func_name: str, node_id: str, file_path: Optional[str] = None):
        if not func_name:
            return

        self.function_index[func_name.lower()].add(node_id)

        if file_path:
            self.file_to_symbols[file_path].add(func_name)

        self._add_symbol(func_name, node_id)

    def _add_symbol(self, symbol: str, node_id: str):
        normalized = symbol.lower().strip("\\")
        self.symbol_to_nodes[normalized].add(node_id)

    # ==============================================================
    # RESOLVE METHODS
    # ==============================================================
    def resolve_class(self, class_name: str) -> Optional[str]:
        normalized = class_name.lower().strip("\\")
        for fqn, nid in self.class_fqn_to_node.items():
            if fqn.lower() == normalized:
                return nid
        short = class_name.split("\\")[-1].lower()
        candidates = self.class_short_index.get(short, set())
        if len(candidates) == 1:
            return next(iter(candidates))
        return None

    def resolve_method(self, target_class: Optional[str], method_name: str,
                       caller_class: Optional[str] = None, imports: Optional[List[str]] = None) -> Optional[str]:
        method_lower = method_name.lower()

        if target_class:
            if target_class in ("self", "static", "$this") and caller_class:
                return self._resolve_in_class(caller_class, method_lower)
            res = self._resolve_in_class(target_class, method_lower)
            if res:
                return res

        if caller_class:
            res = self._resolve_in_class(caller_class, method_lower)
            if res:
                return res

        return None

    def _resolve_in_class(self, class_fqn: str, method_lower: str):
        methods = self.class_method_index.get(class_fqn, {}).get(method_lower)
        if methods:
            return next(iter(methods))
        return None

    def get_symbols_in_file(self, file_path: str) -> Set[str]:
        return self.file_to_symbols.get(file_path, set())

    def get_class_node(self, class_fqn: str) -> Optional[str]:
        return self.class_fqn_to_node.get(class_fqn)