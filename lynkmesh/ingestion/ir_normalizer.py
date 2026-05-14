"""
IR Normalizer - Convert raw AST into GraphBuilder-compatible IR.

Now aggregates per-method return types into file-level `method_return_types`
so that the orchestrator can hydrate the TypeRegistry.
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class IRNormalizer:
    """
    Normalize AST output into a stable IR format expected by GraphBuilder.
    """

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------
    def normalize(self, ast_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not ast_list:
            return []

        normalized = []
        for file_ast in ast_list:
            if not isinstance(file_ast, dict):
                continue
            try:
                normalized.append(self._normalize_file(file_ast))
            except Exception as e:
                # ✅ FIX 1: log file path together with the error
                file_path = self._get_file_path(file_ast)
                logger.exception(
                    f"[IRNormalizer] Failed to normalize file {file_path}: {e}"
                )

        logger.info(f"[IRNormalizer] Normalized {len(normalized)} files")
        return normalized

    # ----------------------------------------------------------------
    # File level
    # ----------------------------------------------------------------
    def _normalize_file(self, file_ast: Dict[str, Any]) -> Dict[str, Any]:
        file_path = self._get_file_path(file_ast)

        # Aggregate method return types from all classes in this file
        file_method_return_types: Dict[str, str] = {}
        normalized_classes = self._normalize_classes(
            file_ast.get("classes", []),
            file_path,
            file_method_return_types,
        )

        # Merge parser's original method_return_types (if any) with what we just collected
        raw_mrt = file_ast.get("method_return_types", {})
        if isinstance(raw_mrt, dict):
            for k, v in raw_mrt.items():
                if k not in file_method_return_types:
                    file_method_return_types[k] = v

        return {
            "file": file_path,
            "namespace": file_ast.get("namespace"),
            "uses": file_ast.get("uses", []),
            "method_return_types": file_method_return_types,
            "classes": normalized_classes,
            "functions": self._normalize_functions(
                file_ast.get("functions", []), file_path
            ),
        }

    def _get_file_path(self, file_ast: Dict[str, Any]) -> str:
        return (
            file_ast.get("file")
            or file_ast.get("file_path")
            or file_ast.get("path")
            or "unknown_file"
        )

    # ----------------------------------------------------------------
    # Class level
    # ----------------------------------------------------------------
    def _normalize_classes(
        self,
        classes: List[Dict],
        file_path: str,
        file_method_return_types: Dict[str, str],
    ) -> List[Dict]:
        if not isinstance(classes, list):
            return []

        result = []
        for cls in classes:
            if not isinstance(cls, dict):
                continue
            name = cls.get("name")
            if not name:
                continue

            normalized_cls = {
                "name": name,
                "fqn": cls.get("fqn"),
                "extends": cls.get("extends"),
                "implements": cls.get("implements", []),
                "traits": cls.get("traits", []),
                "properties": cls.get("properties", []),
                "methods": self._normalize_methods(
                    cls.get("methods", []),
                    class_name=name,
                    file_path=file_path,
                    file_method_return_types=file_method_return_types,
                ),
            }
            result.append(normalized_cls)
        return result

    # ----------------------------------------------------------------
    # Method level
    # ----------------------------------------------------------------
    def _normalize_methods(
        self,
        methods: List[Dict],
        class_name: str,
        file_path: str,
        file_method_return_types: Dict[str, str],
    ) -> List[Dict]:
        if not isinstance(methods, list):
            return []

        result = []
        for method in methods:
            if not isinstance(method, dict):
                continue
            method_name = method.get("name")
            if not method_name:
                continue

            # Record return type for file-level aggregation
            return_type = method.get("return_type")
            if return_type and return_type.lower() not in (
                "void", "mixed", "null", "never"
            ):
                key = f"{class_name}::{method_name}"
                file_method_return_types[key] = return_type

            # Merge legacy assignment metadata into calls
            merged_calls = self._normalize_calls(
                self._merge_call_assignments(
                    method.get("calls", []),
                    method.get("assignments", []),
                )
            )

            normalized_method = {
                "name": method_name,
                "visibility": method.get("visibility", "public"),
                "params": method.get("params", []),
                "return_type": return_type,
                "file": file_path,
                "calls": merged_calls,
                "function_calls": self._normalize_calls(
                    method.get("function_calls", [])
                ),
                "instantiations": method.get("instantiations", []),
                "assignments": method.get("assignments", []),
                "sql_strings": method.get("sql_strings", []),
                "property_fetches": method.get("property_fetches", []),
                "static_property_fetches": method.get("static_property_fetches", []),
                "constant_fetches": method.get("constant_fetches", []),
                "returns": method.get("returns", []),
                "has_try_catch": method.get("has_try_catch", False),
            }
            result.append(normalized_method)
        return result

    # ----------------------------------------------------------------
    # Normalize calls
    # ----------------------------------------------------------------
    def _normalize_calls(self, calls: List[Dict]) -> List[Dict]:
        if not isinstance(calls, list):
            return []

        result = []
        for c in calls:
            if not isinstance(c, dict):
                continue
            new_call = dict(c)

            class_hint = c.get("target") or c.get("class")
            if isinstance(class_hint, str):
                # ✅ FIX 2: PHP-specific namespace trimming – to be moved
                # into language adapter once multi-language support is active.
                class_hint = class_hint.lstrip("\\")

            new_call["class"] = class_hint
            new_call.pop("target", None)

            result.append(new_call)

        return result

    # ----------------------------------------------------------------
    # Merge assignments → calls (NO HEURISTIC)
    # ----------------------------------------------------------------
    def _merge_call_assignments(
        self,
        calls: List[Dict],
        assignments: List[Dict],
    ) -> List[Dict]:
        if not isinstance(calls, list):
            return []
        if not isinstance(assignments, list):
            assignments = []

        assignment_by_line: Dict[tuple, str] = {}
        fallback_queue: Dict[str, List[str]] = {}

        for a in assignments:
            if not isinstance(a, dict):
                continue

            var_name = (
                a.get("var")
                or a.get("variable")
                or a.get("target")
                or a.get("assign_to")
            )
            source_method = (
                a.get("source_call")
                or a.get("method")
                or a.get("source_method")
            )
            line = a.get("line")

            if not var_name or not source_method:
                continue

            if isinstance(var_name, str) and var_name.startswith("$"):
                var_name = var_name[1:]

            if line:
                assignment_by_line[(line, source_method)] = var_name
            else:
                fallback_queue.setdefault(source_method, []).append(var_name)

        enriched = []
        for call in calls:
            if not isinstance(call, dict):
                continue

            method_name = call.get("method")
            line = call.get("line")
            new_call = dict(call)

            if line and (line, method_name) in assignment_by_line:
                new_call["assign_to"] = assignment_by_line[(line, method_name)]
            elif method_name in fallback_queue and fallback_queue[method_name]:
                new_call["assign_to"] = fallback_queue[method_name].pop(0)

            enriched.append(new_call)

        return enriched

    # ----------------------------------------------------------------
    # Function level
    # ----------------------------------------------------------------
    def _normalize_functions(
        self, functions: List[Dict], file_path: str
    ) -> List[Dict]:
        if not isinstance(functions, list):
            return []

        result = []
        for func in functions:
            if not isinstance(func, dict):
                continue
            name = func.get("name")
            if not name:
                continue

            merged_calls = self._normalize_calls(
                self._merge_call_assignments(
                    func.get("calls", []),
                    func.get("assignments", []),
                )
            )

            normalized_func = {
                "type": func.get("type", "function"),
                "name": name,
                "fqn": func.get("fqn"),
                "file": file_path,
                "params": func.get("params", []),
                "return_type": func.get("return_type"),
                "calls": merged_calls,
                "http_method": func.get("http_method"),
                "uri": func.get("uri"),
                "controller": func.get("controller"),
                "controller_method": func.get("controller_method"),
            }
            result.append(normalized_func)
        return result