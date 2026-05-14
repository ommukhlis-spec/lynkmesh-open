# lynkmesh/graph/call_resolver.py
"""
Call Resolver v6 – Multi-pass fixpoint resolution with enhanced propagation.

Improvements:
  1. Global assignment pass: scan all assignments before resolution loop,
     seeding var_types with instantiation targets and method call results.
  2. Call order replay: sort calls by source line number to respect execution order.
  3. Reverse edge index: maintain `in_edges` lookup on GraphCore for dependency tracing.
  4. Multi-hop propagation: iterate resolution until no new types can be inferred,
     handling chained calls like $a->method()->next().

Stage 3.0.0.1b – deterministic resolver candidate selection added.
"""

import json
import logging
from collections import Counter
from typing import Dict, Any, Optional, List, Set, Tuple

from lynkmesh.core.graph_core import GraphCore
from lynkmesh.core.symbol_registry import SymbolRegistry
from lynkmesh.core.type_registry import TypeRegistry

# Sprint 2.7.A.1 — telemetry instrumentation
# PR 2.a: EXACT telemetry
# PR 2.b: rejection telemetry
# PR 2.c: unified resolution result & invariants

from lynkmesh.semantic.contracts import (
    ConfidenceClass,
    FailureReason,
    RejectReason,
    ResolutionOutcome,
    ResolutionResult,
    ResolutionTelemetry,
    SourceLocation,
)

logger = logging.getLogger(__name__)


class CallResolver:
    """Resolves call relationships inside GraphCore with type propagation."""

    EDGE_CALLS_CONFIRMED = "calls_confirmed"
    EDGE_CALLS_EXTERNAL = "calls_external"
    EDGE_CALLS_HEURISTIC = "calls_heuristic"

    SEMANTIC_INTERNAL_CALL = "internal_call"
    SEMANTIC_EXTERNAL_CALL = "external_integration"

    LAYER_PRIORITY = {
        "service": 3,
        "repository": 2,
        "model": 1,
        "controller": 0,
        "unknown": 0,
    }

    PHP_BUILTINS = {
        "count", "isset", "array_map", "in_array", "array_filter",
        "array_merge", "array_keys", "array_values", "strlen", "strpos",
        "substr", "trim", "explode", "implode", "json_encode", "json_decode",
        "is_null", "is_array", "is_string", "is_int", "print_r", "var_dump",
    }

    KNOWN_GLOBAL_FUNCTIONS = {
        "view", "redirect", "response", "config", "env", "now",
        "abort", "session", "route", "asset",
    }

    KNOWN_EXTERNAL_CLASSES = {
        "DB", "Auth", "Validator", "Carbon", "Response", "Session",
        "Cache", "Storage", "Mail", "Log", "Eloquent",
        "Spreadsheet", "Worksheet", "Dompdf", "Superadmin_AuditLog",
        "ExportService", "Invoice", "User",
    }

    MAX_FIXPOINT_ITERATIONS = 10

    def __init__(self):
        self._cache: Dict[tuple, Optional[str]] = {}
        self._external_cache: Dict[str, str] = {}
        self._stats = {
            "resolved": 0, "self_parent": 0, "propagated": 0,
            "instantiation": 0, "heuristic": 0, "unresolved": 0,
        }
        self.type_registry = TypeRegistry()
        self._load_php_builtins()
        self._debug_propagation: List[Dict[str, Any]] = []
        self._telemetry: ResolutionTelemetry = ResolutionTelemetry()

        # Class-level property cache: class_fqn -> {prop_name: type}
        self._class_property_cache: Dict[str, Dict[str, str]] = {}

    @property
    def last_telemetry(self) -> ResolutionTelemetry:
        return self._telemetry

    def _load_php_builtins(self):
        structured = {
            "PDO": {
                "prepare": "PDOStatement", "query": "PDOStatement",
                "exec": "int", "lastInsertId": "string",
                "beginTransaction": "bool", "commit": "bool",
                "rollBack": "bool", "inTransaction": "bool",
                "errorCode": "string", "errorInfo": "array",
            },
            "PDOStatement": {
                "execute": "bool", "fetch": "array", "fetchAll": "array",
                "fetchColumn": "mixed", "rowCount": "int",
                "bindParam": "bool", "bindValue": "bool",
                "closeCursor": "bool", "columnCount": "int",
            },
            "Exception": {
                "getMessage": "string", "getTraceAsString": "string",
                "getCode": "int", "getFile": "string", "getLine": "int",
            },
            "Throwable": {"getMessage": "string", "getTraceAsString": "string"},
            "finfo": {"file": "string"},
            "DateTime": {
                "format": "string", "getTimestamp": "int",
                "diff": "DateInterval", "add": "DateTime", "sub": "DateTime",
                "modify": "DateTime",
            },
            "DateTimeImmutable": {
                "format": "string", "getTimestamp": "int",
                "diff": "DateInterval", "add": "DateTimeImmutable", "sub": "DateTimeImmutable",
            },
            "DateInterval": {"format": "string"},
            "mysqli": {
                "prepare": "mysqli_stmt", "real_escape_string": "string",
                "query": "mysqli_result", "error": "string", "errno": "int",
            },
            "mysqli_stmt": {
                "execute": "bool", "bind_param": "bool", "bind_result": "bool",
                "get_result": "mysqli_result", "fetch": "bool", "affected_rows": "int",
            },
            "mysqli_result": {
                "fetch_assoc": "array", "fetch_all": "array",
                "fetch_object": "object", "num_rows": "int",
            },
            "Spreadsheet": {
                "getActiveSheet": "Worksheet",
            },
            "Worksheet": {
                "setCellValueExplicit": "void", "freezePane": "void",
                "fromArray": "void", "setAutoFilter": "void", "setTitle": "void",
            },
            "Dompdf": {
                "loadHtml": "void", "setPaper": "void", "stream": "void",
                "render": "void", "output": "string",
            },
        }
        self.type_registry.load_structured_builtins(structured)

    # ------------------------------------------------------------------
    # Stage 3.0.0.1b — deterministic resolver candidate selection
    # ------------------------------------------------------------------
    def _stable_json_fragment(self, value: Any) -> str:
        """
        Stable serialization fragment for tie-breaking only.

        This is not used for GraphVersion hashing. It is only used to make
        resolver candidate ordering deterministic when multiple candidates
        have the same semantic class/method identity.
        """
        try:
            return json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
        except TypeError:
            return str(value)

    def _stable_path(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\\", "/")

    def _node_semantic_sort_key(self, node: Optional[Dict[str, Any]]) -> tuple:
        """
        Stable semantic node key for resolver tie-breaking.

        Uses runtime id only as final fallback. The important disambiguators are
        qualified_name, file path, type/name, class, params, return type, and
        visibility. This handles duplicate class/method names across files.
        """
        if not isinstance(node, dict):
            return ("", "", "", "", "", "", "", "", "", "")

        extra = node.get("extra")
        if not isinstance(extra, dict):
            extra = {}

        params = extra.get("params")
        interfaces = extra.get("interfaces")
        extends = extra.get("extends")

        return (
            str(node.get("qualified_name") or ""),
            self._stable_path(node.get("file_path") or node.get("file")),
            str(node.get("type") or ""),
            str(node.get("name") or ""),
            str(node.get("layer") or ""),
            str(extra.get("class") or ""),
            self._stable_json_fragment(params if params is not None else []),
            str(extra.get("return_type") or ""),
            str(extra.get("visibility") or ""),
            self._stable_json_fragment(
                {
                    "extends": extends,
                    "interfaces": interfaces,
                    "entry": extra.get("entry"),
                    "entry_type": extra.get("entry_type"),
                }
            ),
            str(node.get("id") or ""),
        )

    def _call_sort_key(self, call: Dict[str, Any]) -> tuple:
        """Stable ordering for calls on the same line."""
        if not isinstance(call, dict):
            return (0, "", "", "", "", "")

        return (
            call.get("line", 0) if isinstance(call.get("line", 0), int) else 0,
            str(call.get("method") or ""),
            self._stable_json_fragment(call.get("object") or ""),
            str(call.get("class") or ""),
            str(call.get("assign_to") or ""),
            self._stable_json_fragment(call),
        )

    def _normalize_class_token(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lstrip("\\").lstrip("?")

    def _short_class_name(self, value: Any) -> str:
        token = self._normalize_class_token(value)
        if not token:
            return ""
        return token.split("\\")[-1]

    def _node_class_candidates(self, node: Dict[str, Any]) -> Set[str]:
        """
        Return possible class tokens for a node.

        Handles:
        - extra.class
        - qualified_name before ::
        - short class names
        """
        if not isinstance(node, dict):
            return set()

        extra = node.get("extra")
        if not isinstance(extra, dict):
            extra = {}

        values = set()

        cls = self._normalize_class_token(extra.get("class"))
        qn = self._normalize_class_token(node.get("qualified_name"))

        if cls:
            values.add(cls)
            values.add(self._short_class_name(cls))

        if "::" in qn:
            qn_cls = qn.split("::", 1)[0]
            values.add(qn_cls)
            values.add(self._short_class_name(qn_cls))
        elif qn and node.get("type") == "class":
            values.add(qn)
            values.add(self._short_class_name(qn))

        name = self._normalize_class_token(node.get("name"))
        if node.get("type") == "class" and name:
            values.add(name)
            values.add(self._short_class_name(name))

        return {v for v in values if v}

    def _node_matches_class(self, node: Dict[str, Any], target_class: Any) -> bool:
        target = self._normalize_class_token(target_class)
        if not target:
            return True

        target_short = self._short_class_name(target)
        candidates = self._node_class_candidates(node)

        return (
            target in candidates
            or target_short in candidates
            or any(c.endswith("\\" + target_short) for c in candidates)
        )

    def _stable_method_candidates(
        self,
        graph: GraphCore,
        symbols: SymbolRegistry,
        method_name: str,
        target_class: Optional[str] = None,
        *,
        exclude_id: Optional[str] = None,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Return deterministic candidate list for a method.

        Uses global_method_index as the candidate source, then filters by
        target_class when provided. This does not create new resolution paths;
        callers still use symbols.resolve_method() as the gatekeeper.
        """
        method_key = (method_name or "").lower()
        raw_candidates = list(getattr(symbols, "global_method_index", {}).get(method_key, []))

        candidates: List[Tuple[str, Dict[str, Any]]] = []
        for raw in raw_candidates:
            cand_id = raw.get("id") if isinstance(raw, dict) else raw
            if not cand_id or cand_id == exclude_id:
                continue

            cand_node = graph.get_node(cand_id)
            if not cand_node:
                continue

            if str(cand_node.get("name") or "").lower() != method_key:
                continue

            if target_class and not self._node_matches_class(cand_node, target_class):
                continue

            candidates.append((cand_id, cand_node))

        candidates.sort(key=lambda item: self._node_semantic_sort_key(item[1]))
        return candidates

    def _resolve_method_stable(
        self,
        graph: GraphCore,
        symbols: SymbolRegistry,
        *,
        target_class: Optional[str],
        method_name: str,
        caller_class: Optional[str] = None,
        imports: Optional[List[str]] = None,
        exclude_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Deterministic wrapper around SymbolRegistry.resolve_method().

        Important:
        - We still call symbols.resolve_method() first to preserve existing
          resolution semantics and telemetry counts.
        - If SymbolRegistry says the method is resolvable and target_class is
          known, we choose from equivalent candidates using a stable semantic
          tie-break.
        """
        resolved = symbols.resolve_method(
            target_class=target_class,
            method_name=method_name,
            caller_class=caller_class,
            imports=imports,
        )

        if not resolved:
            return None

        # If we know the target class, stabilize duplicate class/method choices.
        if target_class:
            candidates = self._stable_method_candidates(
                graph,
                symbols,
                method_name,
                target_class,
                exclude_id=exclude_id,
            )
            if candidates:
                return candidates[0][0]

        return resolved

    def _stable_class_node_id(
        self,
        graph: GraphCore,
        symbols: SymbolRegistry,
        class_name: str,
    ) -> Optional[str]:
        """
        Deterministic class node lookup.

        Keeps SymbolRegistry's mapping as a candidate, then sorts all matching
        class nodes semantically.
        """
        candidates: List[Tuple[str, Dict[str, Any]]] = []

        mapped_id = getattr(symbols, "class_fqn_to_node", {}).get(class_name)
        if mapped_id:
            mapped_node = graph.get_node(mapped_id)
            if mapped_node:
                candidates.append((mapped_id, mapped_node))

        for node_id, node in graph.nodes.items():
            if node.get("type") != "class":
                continue
            if self._node_matches_class(node, class_name):
                candidates.append((node_id, node))

        # Deduplicate by id, preserving node object.
        deduped = {}
        for node_id, node in candidates:
            deduped[node_id] = node

        ordered = sorted(
            deduped.items(),
            key=lambda item: self._node_semantic_sort_key(item[1]),
        )
        return ordered[0][0] if ordered else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def resolve(self, graph: GraphCore, symbols: SymbolRegistry) -> GraphCore:
        self._collect_return_types(graph)
        self._debug_propagation.clear()
        self._class_property_cache.clear()
        self._telemetry = ResolutionTelemetry()

        for node_id, node in sorted(
            list(graph.nodes.items()),
            key=lambda item: self._node_semantic_sort_key(item[1]),
        ):
            if node.get("type") not in ("method", "function"):
                continue

            caller_class_fqn = node.get("extra", {}).get("class")
            if caller_class_fqn:
                self._ensure_class_cache(graph, symbols, caller_class_fqn)

            calls = node.get("extra", {}).get("calls", [])
            instantiations = node.get("extra", {}).get("instantiations", [])

            if not calls and not instantiations:
                continue

            var_types: Dict[str, str] = {}
            self._seed_params(node, var_types)
            self._seed_instantiations(node, var_types)
            self._seed_constructor_promoted_properties(graph, symbols, node, var_types)
            self._seed_property_fetches(node, var_types)

            if caller_class_fqn:
                class_props = self._class_property_cache.get(caller_class_fqn, {})
                for prop_name, prop_type in class_props.items():
                    if prop_name not in var_types:
                        var_types[prop_name] = prop_type

            self._collect_assignments(graph, symbols, node, var_types, caller_class_fqn)

            caller_class = node.get("extra", {}).get("class")
            imports = node.get("extra", {}).get("imports", [])
            source_layer = node.get("layer", "unknown")

            ordered_calls = sorted(
                [
                    c for c in calls
                    if isinstance(c, dict)
                    and c.get("method", "").lower() not in self.PHP_BUILTINS
                ],
                key=self._call_sort_key,
            )

            progress = True
            iteration = 0
            while progress and iteration < self.MAX_FIXPOINT_ITERATIONS:
                iteration += 1
                progress = False
                unresolved_calls: List[Dict[str, Any]] = []

                for call in ordered_calls:
                    method_name = call.get("method")
                    if not method_name:
                        continue
                    obj_expr = call.get("object") or ""

                    debug_entry = {
                        "method": method_name,
                        "object": obj_expr,
                        "class_hint": call.get("class"),
                        "assign_to": call.get("assign_to"),
                        "var_name": None, "var_type": None,
                        "resolved_by": None, "failure_reason": None,
                    }

                    target_class = call.get("class")
                    if isinstance(target_class, str):
                        target_class = target_class.lstrip("\\").lstrip("?")

                    resolved_id = None
                    edge_type = self.EDGE_CALLS_CONFIRMED
                    confidence = 0.9

                    # --- PASS 1a ---
                    if target_class:
                        resolved_id = self._resolve_method_stable(
                            graph,
                            symbols,
                            target_class=target_class,
                            method_name=method_name,
                            caller_class=caller_class,
                            imports=imports,
                            exclude_id=node_id,
                        )
                        if resolved_id:
                            self._telemetry.record_attempt(ConfidenceClass.EXACT)
                            self._stats["resolved"] += 1

                            if self._propagate_assignment(graph, call, resolved_id, var_types):
                                progress = True

                            result = ResolutionResult(
                                caller_id=node_id,
                                site=self._build_site(node, call),
                                confidence=ConfidenceClass.EXACT,
                                outcome=ResolutionOutcome.RESOLVED,
                                callee_id=resolved_id,
                            )
                            self._finalize_resolution(
                                graph,
                                result,
                                debug_entry,
                                source_id=node_id,
                                source_layer=source_layer,
                                call=call,
                                edge_confidence=confidence,
                                edge_type=edge_type,
                                debug_resolved_by="exact",
                            )
                            continue

                    # --- PASS 1b ---
                    resolved_id, prop_debug = self._resolve_via_propagation(
                        graph, symbols, call, var_types
                    )
                    debug_entry["var_name"] = prop_debug.get("var_name")
                    debug_entry["var_type"] = prop_debug.get("var_type")

                    if isinstance(resolved_id, str) and resolved_id.startswith("__type_"):
                        pseudo_id = resolved_id
                        assert pseudo_id
                        assert pseudo_id.startswith("__type_")

                        if self._propagate_from_registry(pseudo_id, call, var_types):
                            progress = True

                        self._telemetry.record_attempt(ConfidenceClass.PROPAGATED)
                        self._stats["propagated"] += 1

                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.PROPAGATED,
                            outcome=ResolutionOutcome.REJECTED,
                            callee_id=pseudo_id,
                            reject_reason=RejectReason.INVALID_TARGET,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            source_id=node_id,
                            source_layer=source_layer,
                            call=call,
                            edge_confidence=0.0,
                            edge_type=None,
                            debug_resolved_by="type_registry",
                        )
                        continue

                    if resolved_id:
                        if self._propagate_assignment(graph, call, resolved_id, var_types):
                            progress = True

                        self._telemetry.record_attempt(ConfidenceClass.PROPAGATED)
                        self._stats["propagated"] += 1

                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.PROPAGATED,
                            outcome=ResolutionOutcome.RESOLVED,
                            callee_id=resolved_id,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            source_id=node_id,
                            source_layer=source_layer,
                            call=call,
                            edge_confidence=0.8,
                            edge_type=edge_type,
                            debug_resolved_by="propagation",
                        )
                        continue

                    # --- PASS 1c ---
                    if caller_class and not target_class:
                        resolved_id = self._resolve_method_stable(
                            graph,
                            symbols,
                            target_class=caller_class,
                            method_name=method_name,
                            caller_class=caller_class,
                            imports=imports,
                            exclude_id=node_id,
                        )
                        if resolved_id:
                            self._telemetry.record_attempt(ConfidenceClass.EXACT)
                            self._stats["self_parent"] += 1

                            if self._propagate_assignment(graph, call, resolved_id, var_types):
                                progress = True

                            result = ResolutionResult(
                                caller_id=node_id,
                                site=self._build_site(node, call),
                                confidence=ConfidenceClass.EXACT,
                                outcome=ResolutionOutcome.RESOLVED,
                                callee_id=resolved_id,
                            )
                            self._finalize_resolution(
                                graph,
                                result,
                                debug_entry,
                                source_id=node_id,
                                source_layer=source_layer,
                                call=call,
                                edge_confidence=0.95,
                                edge_type=edge_type,
                                debug_resolved_by="self/parent",
                            )
                            continue

                    # --- PASS 1d ---
                    if not resolved_id and imports and caller_class:
                        resolved_id = self._resolve_method_stable(
                            graph,
                            symbols,
                            target_class=None,
                            method_name=method_name,
                            caller_class=caller_class,
                            imports=imports,
                            exclude_id=node_id,
                        )
                        if resolved_id:
                            self._telemetry.record_attempt(ConfidenceClass.EXACT)
                            self._stats["resolved"] += 1

                            if self._propagate_assignment(graph, call, resolved_id, var_types):
                                progress = True

                            result = ResolutionResult(
                                caller_id=node_id,
                                site=self._build_site(node, call),
                                confidence=ConfidenceClass.EXACT,
                                outcome=ResolutionOutcome.RESOLVED,
                                callee_id=resolved_id,
                            )
                            self._finalize_resolution(
                                graph,
                                result,
                                debug_entry,
                                source_id=node_id,
                                source_layer=source_layer,
                                call=call,
                                edge_confidence=confidence,
                                edge_type=edge_type,
                                debug_resolved_by="import",
                            )
                            continue

                    # --- PASS 1e ---
                    valid_candidates = self._stable_method_candidates(
                        graph,
                        symbols,
                        method_name,
                        target_class=None,
                        exclude_id=node_id,
                    )

                    if valid_candidates:
                        best_candidate = None
                        best_priority = -1
                        caller_ns = self._extract_namespace(node)

                        for cand_id, cand_node in valid_candidates:
                            layer = cand_node.get("layer", "unknown")
                            priority = self.LAYER_PRIORITY.get(layer, 0)

                            cand_qn = str(cand_node.get("qualified_name") or "")
                            cand_file = self._stable_path(
                                cand_node.get("file_path") or cand_node.get("file")
                            )

                            if caller_ns and (
                                caller_ns in cand_qn or self._stable_path(caller_ns) in cand_file
                            ):
                                priority += 2

                            if priority > best_priority:
                                best_priority = priority
                                best_candidate = cand_id

                        if best_candidate:
                            self._telemetry.record_attempt(ConfidenceClass.HEURISTIC)
                            self._stats["heuristic"] += 1

                            if self._propagate_assignment(graph, call, best_candidate, var_types):
                                progress = True

                            debug_entry["source_id"] = node_id
                            debug_entry["target_id"] = best_candidate
                            debug_entry["outcome"] = "RESOLVED"
                            debug_entry["confidence"] = "HEURISTIC"
                            debug_entry["resolved_by"] = "heuristic"

                            self._telemetry.record_hit(ConfidenceClass.HEURISTIC)
                            self._add_call_edge(
                                graph,
                                node_id,
                                best_candidate,
                                source_layer,
                                call,
                                confidence=0.5,
                                edge_type=self.EDGE_CALLS_HEURISTIC,
                            )
                            self._telemetry.record_emission(ConfidenceClass.HEURISTIC)

                            self._debug_propagation.append(debug_entry)
                            continue

                    unresolved_calls.append((call, debug_entry))

                # --- Replay loop ---
                for call, debug_entry in unresolved_calls:
                    method_name = call.get("method")
                    target_class = call.get("class")
                    obj_expr_replay = call.get("object") or ""

                    if isinstance(target_class, str):
                        target_class = target_class.lstrip("\\").lstrip("?")

                    resolved_id, prop_debug = self._resolve_via_propagation(
                        graph, symbols, call, var_types
                    )
                    debug_entry["var_name"] = prop_debug.get("var_name")
                    debug_entry["var_type"] = prop_debug.get("var_type")

                    if isinstance(resolved_id, str) and resolved_id.startswith("__type_"):
                        pseudo_id = resolved_id
                        assert pseudo_id.startswith("__type_")

                        if self._propagate_from_registry(pseudo_id, call, var_types):
                            progress = True

                        self._telemetry.record_attempt(ConfidenceClass.PROPAGATED)
                        self._stats["propagated"] += 1

                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.PROPAGATED,
                            outcome=ResolutionOutcome.REJECTED,
                            callee_id=pseudo_id,
                            reject_reason=RejectReason.INVALID_TARGET,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            debug_resolved_by="type_registry_replay",
                        )
                        continue

                    if resolved_id:
                        if self._propagate_assignment(graph, call, resolved_id, var_types):
                            progress = True

                        self._telemetry.record_attempt(ConfidenceClass.PROPAGATED)
                        self._stats["propagated"] += 1

                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.PROPAGATED,
                            outcome=ResolutionOutcome.RESOLVED,
                            callee_id=resolved_id,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            source_id=node_id,
                            source_layer=source_layer,
                            call=call,
                            edge_confidence=0.8,
                            edge_type=self.EDGE_CALLS_CONFIRMED,
                            debug_resolved_by="propagation_replay",
                        )
                        continue

                    # External fallback check
                    if (target_class in self.KNOWN_EXTERNAL_CLASSES or
                            obj_expr_replay in self.KNOWN_EXTERNAL_CLASSES):
                        self._telemetry.record_attempt(ConfidenceClass.EXTERNAL)
                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.EXTERNAL,
                            outcome=ResolutionOutcome.NO_TARGET,
                            failure_reason=FailureReason.KNOWN_FRAMEWORK_EXTERNAL,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            failure_sample={
                                "target_class": target_class,
                                "obj_expr": obj_expr_replay,
                                "method": method_name,
                            },
                        )
                        continue

                    if target_class and self.type_registry.has_class(target_class):
                        self._telemetry.record_attempt(ConfidenceClass.PROPAGATED)
                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.PROPAGATED,
                            outcome=ResolutionOutcome.NO_TARGET,
                            failure_reason=FailureReason.BUILTIN_TYPE_SKIPPED,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            failure_sample={
                                "target_class": target_class,
                                "reason": "builtin_type_from_target",
                            },
                        )
                        continue
                    if obj_expr_replay and self.type_registry.has_class(obj_expr_replay):
                        self._telemetry.record_attempt(ConfidenceClass.PROPAGATED)
                        result = ResolutionResult(
                            caller_id=node_id,
                            site=self._build_site(node, call),
                            confidence=ConfidenceClass.PROPAGATED,
                            outcome=ResolutionOutcome.NO_TARGET,
                            failure_reason=FailureReason.BUILTIN_TYPE_SKIPPED,
                        )
                        self._finalize_resolution(
                            graph,
                            result,
                            debug_entry,
                            failure_sample={
                                "obj_expr": obj_expr_replay,
                                "reason": "builtin_type_from_obj_expr",
                            },
                        )
                        continue

                    # Truly unresolvable
                    self._stats["unresolved"] += 1

                    step = prop_debug.get("step")
                    if step == "NO_OBJECT":
                        debug_entry["failure_reason"] = "NO_OBJECT"
                    elif step == "STATIC_METHOD_NOT_FOUND":
                        debug_entry["failure_reason"] = "STATIC_METHOD_NOT_FOUND"

                    self._telemetry.record_attempt(ConfidenceClass.EXTERNAL)

                    ext_name = f"{target_class or obj_expr_replay or 'unknown'}::{method_name}"
                    if ext_name not in self._external_cache:
                        ext_id = graph.add_node(
                            node_type="external", name=ext_name, qualified_name=ext_name,
                            extra={"target_class": target_class, "method": method_name},
                        )
                        self._external_cache[ext_name] = ext_id
                    else:
                        ext_id = self._external_cache[ext_name]

                    result = ResolutionResult(
                        caller_id=node_id,
                        site=self._build_site(node, call),
                        confidence=ConfidenceClass.EXTERNAL,
                        outcome=ResolutionOutcome.RESOLVED,
                        callee_id=ext_id,
                    )
                    self._finalize_resolution(
                        graph,
                        result,
                        debug_entry,
                        source_id=node_id,
                        source_layer=source_layer,
                        call=call,
                        edge_confidence=0.3,
                        edge_type=self.EDGE_CALLS_EXTERNAL,
                        edge_semantic=self.SEMANTIC_EXTERNAL_CALL,
                        debug_resolved_by="external",
                    )

            # End fixpoint loop for this node

        logger.info(
            f"[CallResolver] Resolved: {self._stats['resolved']}, "
            f"Self/Parent: {self._stats['self_parent']}, "
            f"Propagated: {self._stats['propagated']}, "
            f"Heuristic: {self._stats['heuristic']}, "
            f"Unresolved: {self._stats['unresolved']}"
        )

        self._log_telemetry()

        # Stage 2.4 breakdown (unchanged)
        _PROPAGATED_PATHS = (
            "propagation",
            "propagation_replay",
            "type_registry",
            "type_registry_replay",
        )

        propagated_breakdown = Counter()
        for record in self._debug_propagation:
            label = (
                record.get("resolved_by")
                if isinstance(record, dict)
                else None
            )
            if label in _PROPAGATED_PATHS:
                propagated_breakdown[label] += 1

        if propagated_breakdown:
            logger.info("[CallResolver] PROPAGATED by-path breakdown:")
            for label in _PROPAGATED_PATHS:
                count = propagated_breakdown.get(label, 0)
                if count:
                    logger.info(f"  {label:<24} {count:>5}")
            breakdown_sum = sum(propagated_breakdown.values())
            propagated_hits = self._telemetry.hits[ConfidenceClass.PROPAGATED]
            if breakdown_sum != propagated_hits:
                logger.warning(
                    "[CallResolver] PROPAGATED breakdown sanity: "
                    "breakdown_sum=%d != telemetry.hits[PROPAGATED]=%d (diff=%d)",
                    breakdown_sum, propagated_hits, breakdown_sum - propagated_hits,
                )

        emitted_intent = sum(self._telemetry.emitted.values())
        self._check_invariants_soft(emitted_intent)

        return graph

    def _log_telemetry(self):
        """Print telemetry summary per ConfidenceClass."""
        t = self._telemetry
        logger.info("[CallResolver] Telemetry per ConfidenceClass:")
        for cc in ConfidenceClass:
            attempts = t.attempts[cc]
            hits = t.hits[cc]
            emitted = t.emitted[cc]
            rejected_for_cc = sum(
                v for (c, _), v in t.rejected.items() if c == cc
            )
            if attempts == hits == emitted == rejected_for_cc == 0:
                continue
            logger.info(
                f"  {cc.value:<12} "
                f"attempts={attempts:>5}  "
                f"hits={hits:>5}  "
                f"emitted={emitted:>5}  "
                f"rejected={rejected_for_cc:>5}"
            )
        total_emitted = sum(t.emitted.values())
        logger.info(f"[CallResolver] Total emission intent: {total_emitted}")

    # ------------------------------------------------------------------
    # IMPROVEMENT 1: Global assignment pass
    # ------------------------------------------------------------------
    def _collect_assignments(
        self,
        graph: GraphCore,
        symbols: SymbolRegistry,
        node: Dict[str, Any],
        var_types: Dict[str, str],
        caller_class_fqn: Optional[str],
    ):
        """Scan all assignments in the method and pre-seed types where possible."""
        assignments = node.get("extra", {}).get("assignments", [])
        for assign in assignments:
            if not isinstance(assign, dict):
                continue
            var_name = assign.get("var")
            if not var_name:
                continue

            # Case: $var = new Class
            if assign.get("type") == "instantiation":
                class_name = assign.get("class")
                if class_name:
                    if var_name.startswith("$this->"):
                        prop = self._normalize_this_prop(var_name)
                        self._class_property_cache.setdefault(caller_class_fqn or "", {})[prop] = class_name
                    else:
                        key = self._normalize_var_name(var_name)
                        var_types[key] = class_name

            # Case: $var = func()  -- we can't resolve yet, skip
            # Case: $var = $obj->method()  -- skip, will be resolved later
            # Case: $this->prop = new Class  -> update property cache
            elif assign.get("type") == "property_instantiation":
                class_name = assign.get("class")
                if class_name:
                    prop = self._normalize_this_prop(var_name)
                    if caller_class_fqn:
                        self._class_property_cache.setdefault(caller_class_fqn, {})[prop] = class_name

            # $this->prop = $var (constructor injection) handled elsewhere

    # ------------------------------------------------------------------
    # Class property cache management
    # ------------------------------------------------------------------
    def _ensure_class_cache(
        self, graph: GraphCore, symbols: SymbolRegistry, class_fqn: str
    ):
        """Build cache for a class if not already present."""
        if class_fqn in self._class_property_cache:
            return

        class_node_id = symbols.class_fqn_to_node.get(class_fqn)
        if not class_node_id:
            self._class_property_cache[class_fqn] = {}
            return
        class_node = graph.get_node(class_node_id)
        if not class_node:
            self._class_property_cache[class_fqn] = {}
            return

        props: Dict[str, str] = {}

        # PASS 1: Declared properties from class node
        class_props = class_node.get("extra", {}).get("properties", [])
        if isinstance(class_props, list):
            for prop in class_props:
                if not isinstance(prop, dict):
                    continue
                pname = prop.get("name")
                ptype = prop.get("type")
                if pname and ptype:
                    if isinstance(pname, str) and pname.startswith("$"):
                        pname = pname[1:]
                    props[pname] = ptype

        # PASS 2: Constructor injection
        constructor_id = self._resolve_method_stable(
            graph,
            symbols,
            target_class=class_fqn,
            method_name="__construct",
        )
        if constructor_id:
            ctor_node = graph.get_node(constructor_id)
            if ctor_node:
                ctor_params = ctor_node.get("extra", {}).get("params", [])
                param_types: Dict[str, str] = {}
                for param in ctor_params:
                    pname = param.get("name")
                    ptype = param.get("type")
                    if pname and ptype:
                        if isinstance(pname, str) and pname.startswith("$"):
                            pname = pname[1:]
                        param_types[pname] = ptype

                assignments = ctor_node.get("extra", {}).get("assignments", [])
                for assign in assignments:
                    if not isinstance(assign, dict):
                        continue
                    if assign.get("type") == "property_instantiation":
                        prop_name = assign.get("var")
                        class_name = assign.get("class")
                        if prop_name and class_name and prop_name not in props:
                            props[prop_name] = class_name
                    elif assign.get("type") == "property_param" or (
                        assign.get("var") and assign.get("source_var")
                    ):
                        prop_name = assign.get("var")
                        source_var = assign.get("source_var")
                        if prop_name and source_var:
                            if isinstance(source_var, str) and source_var.startswith("$"):
                                source_var = source_var[1:]
                            rtype = param_types.get(source_var)
                            if rtype and prop_name not in props:
                                props[prop_name] = rtype

        self._class_property_cache[class_fqn] = props

    # ------------------------------------------------------------------
    # Type collection & seeding (unchanged, but keep for context)
    # ------------------------------------------------------------------
    def _collect_return_types(self, graph: GraphCore):
        for node_id, node in graph.nodes.items():
            if node.get("type") != "method":
                continue
            class_fqn = node.get("extra", {}).get("class")
            method_name = node.get("name")
            return_type = node.get("extra", {}).get("return_type")
            if not return_type:
                return_type = node.get("extra", {}).get("inferred_return_type")
            if return_type:
                self.type_registry.add_return_type(class_fqn, method_name, return_type)

    def _extract_namespace(self, node: Dict[str, Any]) -> Optional[str]:
        class_fqn = node.get("extra", {}).get("class")
        if class_fqn:
            return class_fqn
        file_path = node.get("file_path") or node.get("file")
        if file_path:
            return file_path.replace("/", "\\")
        return None

    def _seed_params(self, node: Dict[str, Any], var_types: Dict[str, str]):
        params = node.get("extra", {}).get("params", [])
        for param in params:
            if not isinstance(param, dict):
                continue
            pname = param.get("name")
            ptype = param.get("type")
            if not pname or not ptype:
                continue
            if isinstance(pname, str) and pname.startswith("$"):
                pname = pname[1:]
            var_types[pname] = ptype

    def _seed_instantiations(self, node: Dict[str, Any], var_types: Dict[str, str]):
        insts = node.get("extra", {}).get("instantiations", [])
        if not isinstance(insts, list):
            return
        for inst in insts:
            if not isinstance(inst, dict):
                continue
            vname = inst.get("var") or inst.get("variable") or inst.get("assign_to")
            cname = inst.get("class") or inst.get("fqn")
            if vname and cname:
                if isinstance(vname, str) and vname.startswith("$"):
                    vname = vname[1:]
                var_types[vname] = cname

    def _seed_constructor_promoted_properties(
        self, graph: GraphCore, symbols: SymbolRegistry,
        node: Dict[str, Any], var_types: Dict[str, str],
    ):
        caller_class = node.get("extra", {}).get("class")
        if not caller_class:
            return
        constructor_id = self._resolve_method_stable(
            graph,
            symbols,
            target_class=caller_class,
            method_name="__construct",
        )
        if not constructor_id:
            return
        constructor_node = graph.get_node(constructor_id)
        if not constructor_node:
            return
        params = constructor_node.get("extra", {}).get("params", [])
        for param in params:
            pname = param.get("name")
            ptype = param.get("type")
            if not pname or not ptype:
                continue
            if isinstance(pname, str) and pname.startswith("$"):
                pname = pname[1:]
            var_types[pname] = ptype

    def _seed_property_fetches(self, node: Dict[str, Any], var_types: Dict[str, str]):
        fetches = node.get("extra", {}).get("property_fetches", [])
        if not isinstance(fetches, list):
            return
        for pf in fetches:
            if not isinstance(pf, dict):
                continue
            pname = pf.get("property")
            ptype = pf.get("type")
            if pname and ptype:
                if isinstance(pname, str) and pname.startswith("$"):
                    pname = pname[1:]
                var_types[pname] = ptype.lstrip("\\")

    # ------------------------------------------------------------------
    # State mutation helpers (now return bool indicating progress)
    # ------------------------------------------------------------------
    def _get_return_type_for_node(self, graph: GraphCore, node_id: str) -> Optional[str]:
        node = graph.get_node(node_id)
        if not node:
            return None
        rtype = node.get("extra", {}).get("return_type")
        if rtype:
            return rtype.lstrip("\\").lstrip("?")
        class_fqn = node.get("extra", {}).get("class")
        method_name = node.get("name")
        if class_fqn and method_name:
            rtype = self.type_registry.get_return_type(class_fqn, method_name)
            if rtype:
                return rtype.lstrip("\\").lstrip("?")
        if node.get("type") == "class":
            return (node.get("qualified_name") or node.get("name") or "").lstrip("\\").lstrip("?")
        method_lower = (method_name or "").lower()
        if method_lower in {"getconnection", "connection", "connect", "getdb", "db"}:
            return "PDO"
        if method_lower in {"prepare", "query", "execute", "fetch", "fetchall", "fetchcolumn"}:
            return "PDOStatement"
        return None

    def _propagate_assignment(
        self, graph: GraphCore, call: Dict[str, Any],
        resolved_id: str, var_types: Dict[str, str],
    ) -> bool:
        """Returns True if a new type was added to var_types."""
        assign_to = call.get("assign_to")
        if not assign_to:
            return False
        rtype = self._get_return_type_for_node(graph, resolved_id)
        if not rtype:
            return False

        if assign_to.startswith("$this->"):
            var_name = assign_to.split("->", 1)[1]
        elif assign_to.startswith("$"):
            var_name = assign_to[1:]
        else:
            var_name = assign_to

        if var_name not in var_types:
            var_types[var_name] = rtype
            return True
        return False

    def _propagate_from_registry(
        self, fake_id: str, call: Dict[str, Any], var_types: Dict[str, str],
    ) -> bool:
        assign_to = call.get("assign_to")
        if not assign_to:
            return False
        parts = fake_id[len("__type_"):].split("__", 1)
        if len(parts) != 2:
            return False
        class_fqn, method_name = parts
        rtype = self.type_registry.get_return_type(class_fqn, method_name)
        if not rtype:
            return False
        if assign_to.startswith("$this->"):
            var_name = assign_to.split("->", 1)[1]
        elif assign_to.startswith("$"):
            var_name = assign_to[1:]
        else:
            var_name = assign_to
        if var_name not in var_types:
            var_types[var_name] = rtype
            return True
        return False

    # ------------------------------------------------------------------
    # Propagation logic (with debug)
    # ------------------------------------------------------------------
    def _resolve_via_propagation(
        self,
        graph: GraphCore,
        symbols: SymbolRegistry,
        call: Dict[str, Any],
        var_types: Dict[str, str],
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        debug = {"var_name": None, "var_type": None, "step": None}

        obj_expr = call.get("object") or ""
        method_name = call.get("method")
        if not method_name:
            debug["step"] = "NO_METHOD"
            return None, debug

        obj_name = self._resolve_object_name(obj_expr)

        class_hint = call.get("class")
        if isinstance(class_hint, str):
            class_hint = class_hint.lstrip("\\").lstrip("?")

        if class_hint:
            resolved = self._resolve_method_stable(
                graph,
                symbols,
                target_class=class_hint,
                method_name=method_name,
            )
            if resolved:
                debug["var_type"] = class_hint
                debug["step"] = "CLASS_HINT"
                return resolved, debug

            if self.type_registry.has_class(class_hint):
                class_node_id = self._stable_class_node_id(graph, symbols, class_hint)
                if class_node_id:
                    debug["var_type"] = class_hint
                    debug["step"] = "CLASS_HINT_NODE"
                    return class_node_id, debug
                debug["var_type"] = class_hint
                return f"__type_{class_hint}__{method_name}", debug

        if not obj_name:
            debug["step"] = "NO_OBJECT"
            return None, debug

        if obj_name.lower() in self.KNOWN_GLOBAL_FUNCTIONS:
            debug["step"] = "GLOBAL_FUNCTION"
            return None, debug

        if obj_name and not obj_name.startswith("$"):
            if obj_name in self.KNOWN_EXTERNAL_CLASSES:
                debug["step"] = "KNOWN_FRAMEWORK_STATIC"
                return None, debug

            if obj_name.lower() in self.KNOWN_GLOBAL_FUNCTIONS:
                debug["step"] = "GLOBAL_FUNCTION"
                return None, debug

            if obj_name in var_types:
                obj_type = var_types[obj_name]
                debug["var_name"] = obj_name
                debug["var_type"] = obj_type
                obj_type = obj_type.lstrip("\\").lstrip("?")

                resolved = self._resolve_method_stable(
                    graph,
                    symbols,
                    target_class=obj_type,
                    method_name=method_name,
                )
                if resolved:
                    debug["step"] = "BARE_VAR_SUCCESS"
                    return resolved, debug

                if self.type_registry.get_return_type(obj_type, method_name) is not None:
                    debug["step"] = "BARE_VAR_TYPE_KNOWN"
                    return f"__type_{obj_type}__{method_name}", debug

                debug["step"] = "BARE_VAR_METHOD_NOT_FOUND"
                return None, debug

            resolved = self._resolve_method_stable(
                graph,
                symbols,
                target_class=obj_name,
                method_name=method_name,
            )
            if resolved:
                debug["step"] = "STATIC_CALL"
                return resolved, debug

            debug["step"] = "STATIC_METHOD_NOT_FOUND"
            return None, debug

        if "::" in obj_name:
            class_name = obj_name.split("::")[0]
            if class_name in self.KNOWN_EXTERNAL_CLASSES:
                debug["step"] = "KNOWN_FRAMEWORK_STATIC"
                return None, debug

            resolved = self._resolve_method_stable(
                graph,
                symbols,
                target_class=class_name,
                method_name=method_name,
            )
            if resolved:
                debug["step"] = "STATIC_CALL"
                return resolved, debug

            debug["step"] = "STATIC_METHOD_NOT_FOUND"
            return None, debug

        var_name = self._normalize_var_name(obj_name)
        debug["var_name"] = var_name
        obj_type = var_types.get(var_name)

        if not obj_type:
            debug["step"] = "VAR_TYPE_UNKNOWN"
            return None, debug

        debug["var_type"] = obj_type
        obj_type = obj_type.lstrip("\\").lstrip("?")

        resolved = self._resolve_method_stable(
            graph,
            symbols,
            target_class=obj_type,
            method_name=method_name,
        )
        if resolved:
            debug["step"] = "SUCCESS"
            return resolved, debug

        if self.type_registry.get_return_type(obj_type, method_name) is not None:
            debug["step"] = "VAR_TYPE_KNOWN"
            return f"__type_{obj_type}__{method_name}", debug

        debug["step"] = "METHOD_NOT_FOUND"
        return None, debug

    def _resolve_object_name(self, obj_expr):
        if isinstance(obj_expr, str):
            return obj_expr
        if isinstance(obj_expr, dict):
            if obj_expr.get("type") == "property_fetch":
                target = obj_expr.get("object")
                prop = obj_expr.get("property")
                if target == "$this":
                    return f"$this->{prop}"
                if target:
                    return f"{target}->{prop}"
        return None

    def _normalize_var_name(self, obj_name: str) -> str:
        if not obj_name:
            return ""
        if obj_name.startswith("$this->"):
            chain = obj_name[len("$this->"):]
            return chain.split("->")[0]
        if obj_name.startswith("$"):
            return obj_name[1:]
        return obj_name

    def _normalize_this_prop(self, assign_var: str) -> str:
        """Convert '$this->prop' to 'prop'."""
        if assign_var.startswith("$this->"):
            return assign_var[len("$this->"):]
        return assign_var

    # ------------------------------------------------------------------
    # Edge injection (IMPROVEMENT 3: maintain reverse edge index)
    # ------------------------------------------------------------------
    def _add_call_edge(
        self, graph: GraphCore, source_id: str, target_id: str,
        source_layer: str, call: Dict[str, Any],
        confidence: float, edge_type: str, semantic: Optional[str] = None,
    ):
        target_node = graph.get_node(target_id)
        target_layer = target_node.get("layer", "unknown") if target_node else "unknown"
        if semantic is None:
            semantic = self._infer_semantic(source_layer, target_layer)
        metadata = {
            "call_type": call.get("type", "unknown"),
            "line": call.get("line"),
            "raw_call": call.copy(),
        }
        graph.add_edge(
            source_id, target_id, edge_type,
            confidence=confidence, semantic=semantic, metadata=metadata,
        )

        # 🔥 IMPROVEMENT 3: populate reverse index for dependency tracing
        if not hasattr(graph, 'in_edges'):
            graph.in_edges = {}
        graph.in_edges.setdefault(target_id, []).append(source_id)

    # ------------------------------------------------------------------
    # PR 2.c Stage 2.1 — SourceLocation builder
    # ------------------------------------------------------------------
    def _build_site(
        self, node: Dict[str, Any], call: Dict[str, Any]
    ) -> SourceLocation:
        """
        Construct SourceLocation from caller node + call context.

        Defensive: file/line/col may be missing in some node/call shapes.
        Falls back to '<unknown>' for file and 0 for line/col.
        """
        file_path = (
            (node.get("file") if isinstance(node, dict) else None)
            or (node.get("extra", {}).get("file") if isinstance(node, dict) else None)
            or "<unknown>"
        )

        raw_line = call.get("line") if isinstance(call, dict) else 0
        raw_col = call.get("col") if isinstance(call, dict) else 0

        line = int(raw_line) if isinstance(raw_line, int) and raw_line >= 0 else 0
        col = int(raw_col) if isinstance(raw_col, int) and raw_col >= 0 else 0

        return SourceLocation(
            file=str(file_path),
            line=line,
            col=col,
        )

    # ------------------------------------------------------------------
    # PR 2.c — Unified resolution finalizer
    # ------------------------------------------------------------------
    def _finalize_resolution(
        self,
        graph,
        result: ResolutionResult,
        debug_entry: Dict[str, Any],
        *,
        source_id=None,
        source_layer=None,
        call=None,
        edge_confidence=0.0,
        edge_type=None,
        edge_semantic=None,
        debug_resolved_by=None,
        failure_sample=None,
    ):
        """
        Single terminal for all resolution outcomes.

        All paths (RESOLVED, REJECTED, NO_TARGET) must pass through here eventually.
        Handles telemetry recording, edge creation, and debug entry appending.
        """
        confidence = result.confidence
        if result.outcome == ResolutionOutcome.RESOLVED:
            if result.callee_id is None:
                raise ValueError("RESOLVED outcome requires callee_id")
            self._telemetry.record_hit(confidence)
            self._add_call_edge(
                graph,
                source_id,
                result.callee_id,
                source_layer,
                call,
                edge_confidence,
                edge_type,
                edge_semantic,
            )
            self._telemetry.record_emission(confidence)
            if debug_resolved_by:
                debug_entry["resolved_by"] = debug_resolved_by

        elif result.outcome == ResolutionOutcome.REJECTED:
            if result.reject_reason is None:
                raise ValueError("REJECTED outcome requires reject_reason")
            self._telemetry.record_hit(confidence)
            self._telemetry.record_rejection(confidence, result.reject_reason)
            if debug_resolved_by:
                debug_entry["resolved_by"] = debug_resolved_by

        elif result.outcome == ResolutionOutcome.NO_TARGET:
            if result.failure_reason is None:
                raise ValueError("NO_TARGET outcome requires failure_reason")
            self._telemetry.record_no_resolution(
                confidence, result.failure_reason, sample=failure_sample
            )
            # PR 2.c Stage 2.3 R7 — use .name to match integration baseline (uppercase)
            debug_entry["failure_reason"] = result.failure_reason.name
            if debug_resolved_by:
                debug_entry["resolved_by"] = debug_resolved_by

        else:
            raise ValueError(f"Unknown outcome: {result.outcome}")

        # Always append debug entry for export
        self._debug_propagation.append(debug_entry)

    # ------------------------------------------------------------------
    # PR 2.c — Soft invariant checker
    # ------------------------------------------------------------------
    def _check_invariants_soft(self, intent_count: int):
        """
        Verify telemetry consistency.  Issues are logged as warnings;
        no hard failures yet.
        """
        t = self._telemetry
        total_attempts = sum(t.attempts.values())
        total_hits = sum(t.hits.values())
        total_emitted = sum(t.emitted.values())
        total_no_resolution = sum(t.no_resolution.values())

        # INV 1: attempts == hits + no_resolution
        if total_attempts != total_hits + total_no_resolution:
            logger.warning(
                "[Invariant] attempts (%d) != hits (%d) + no_resolution (%d)",
                total_attempts, total_hits, total_no_resolution,
            )

        # INV 2: hits == emitted + rejected
        total_rejected = sum(t.rejected.values())
        if total_hits != total_emitted + total_rejected:
            logger.warning(
                "[Invariant] hits (%d) != emitted (%d) + rejected (%d)",
                total_hits, total_emitted, total_rejected,
            )

        # INV 3: sum(emitted) should match intent (edge emission count may differ due to dedup)
        if total_emitted != intent_count:
            logger.warning(
                "[Invariant] telemetry emitted (%d) != resolver intent (%d)",
                total_emitted, intent_count,
            )

    def _infer_semantic(self, src_layer: str, tgt_layer: str) -> str:
        if src_layer == "controller" and tgt_layer == "service":
            return "request_flow"
        if src_layer == "service" and tgt_layer in ("repository", "model"):
            return "data_access"
        return self.SEMANTIC_INTERNAL_CALL

    # ------------------------------------------------------------------
    # D4: Export resolution debug in v2 format
    # ------------------------------------------------------------------
    def export_resolution_debug_v2(self, path: str = "resolution_debug.json"):
        """Export resolution records in deterministic v2 provenance schema."""
        records = self._debug_propagation

        # Build call sites for each record
        for rec in records:
            obj = rec.get("object") or ""
            method = rec.get("method") or "unknown"
            cls_hint = rec.get("class_hint") or ""
            call_site = f"{cls_hint}::{method}" if cls_hint else f"{obj}->{method}"
            rec["_call_site"] = call_site
            rec.setdefault("target_id", None)
            rec.setdefault("source_id", "unknown")

        # Categorize
        attempts = list(records)
        emissions = [r for r in records if r.get("outcome") == "RESOLVED"]
        rejections = [r for r in records if r.get("outcome") == "REJECTED"]
        unresolved = [r for r in records if r.get("outcome") == "NO_TARGET"]

        # Deterministic sorting key
        def sort_key(rec):
            return (
                rec.get("source_id", ""),
                rec.get("target_id") or "",
                rec.get("_call_site", ""),
                rec.get("confidence", ""),
            )

        attempts.sort(key=sort_key)
        emissions.sort(key=sort_key)
        rejections.sort(key=sort_key)
        unresolved.sort(key=sort_key)

        # Build summary
        t = self._telemetry
        summary = {
            "total_attempts": sum(t.attempts.values()),
            "total_hits": sum(t.hits.values()),
            "total_emitted": sum(t.emitted.values()),
            "total_rejected": sum(t.rejected.values()),
            "total_unresolved": sum(t.no_resolution.values()),
            "stats": {**self._stats},
        }

        output = {
            "schema_version": "2.0",
            "generated_at": None,
            "resolver_version": "stage3-prep",
            "summary": summary,
            "resolution_attempts": [self._normalize_record(r) for r in attempts],
            "emissions": [self._normalize_record(r) for r in emissions],
            "rejections": [self._normalize_record(r) for r in rejections],
            "unresolved": [self._normalize_record(r) for r in unresolved],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, sort_keys=False)
        logger.info(f"[CallResolver] Resolution debug v2 written to {path}")

    @staticmethod
    def _normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
        """Convert internal debug record to stable v2 entry."""
        return {
            "source_id": rec.get("source_id", "unknown"),
            "call_site": rec.get("_call_site", ""),
            "candidate_target": rec.get("class_hint") or None,
            "final_target": rec.get("target_id") or None,
            "confidence": rec.get("confidence", "UNKNOWN"),
            "outcome": rec.get("outcome") or (
                "RESOLVED" if rec.get("resolved_by") else "NO_TARGET"
            ),
            "reason": rec.get("failure_reason") or rec.get("reject_reason") or None,
        }

    # --- keep original export_debug for backward compatibility ---
    def export_debug(self, path: str = "propagation_debug.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._debug_propagation, f, indent=2, default=str)
        logger.info(f"[CallResolver] Debug export written to {path}")

    def debug_summary(self):
        reasons = Counter(
            d.get("failure_reason") or d.get("resolved_by")
            for d in self._debug_propagation
        )
        logger.info("[CallResolver] Debug Summary:")
        for reason, count in reasons.most_common():
            logger.info(f"  {reason}: {count}")