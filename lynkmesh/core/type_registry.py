# lynkmesh/core/type_registry.py
"""
Type Registry - Centralized, language-agnostic method return type knowledge.

Stores:
- Explicit return types from parsed code
- Inferred return types (from `return new Class()`)
- Built-in mappings for standard library classes (loaded per-language)
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TypeRegistry:
    """
    Stores and resolves method return types.
    Language-specific knowledge is injected via `load_builtins`.
    """

    def __init__(self):
        # "ClassFQN::methodName" -> return type FQCN
        self._method_returns: Dict[str, str] = {}
        # Set of known class FQNs for quick existence check
        self._known_classes: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_return_type(self, class_fqn: str, method_name: str, return_type: str):
        """Register a return type for a method."""
        if not class_fqn or not method_name or not return_type:
            return
        key = f"{class_fqn}::{method_name}"
        if key not in self._method_returns:
            self._method_returns[key] = return_type
            self._known_classes.add(class_fqn)
            logger.debug(f"[TypeRegistry] Registered: {key} -> {return_type}")

    def get_return_type(self, class_fqn: str, method_name: str) -> Optional[str]:
        """Get registered return type for a method, or None."""
        key = f"{class_fqn}::{method_name}"
        return self._method_returns.get(key)

    def has_class(self, class_name: str) -> bool:
        """Check if a class is known to the registry (has at least one method)."""
        return class_name in self._known_classes

    def load_builtins(self, mapping: Dict[str, str]):
        """Load language-specific type mappings."""
        for key, rtype in mapping.items():
            if key not in self._method_returns:
                self._method_returns[key] = rtype
                # Extract class from key "Class::method"
                if "::" in key:
                    self._known_classes.add(key.split("::")[0])
        logger.info(f"[TypeRegistry] Loaded {len(mapping)} built-in types")

    def load_structured_builtins(self, structured: Dict[str, Dict[str, str]]):
        """Load built-in types in a structured format: {Class: {method: return_type}}."""
        loaded = 0
        for class_fqn, methods in structured.items():
            self._known_classes.add(class_fqn)
            for method_name, return_type in methods.items():
                key = f"{class_fqn}::{method_name}"
                if key not in self._method_returns:
                    self._method_returns[key] = return_type
                    loaded += 1
        logger.info(f"[TypeRegistry] Loaded {loaded} structured built-in types")

    def stats(self) -> int:
        return len(self._method_returns)