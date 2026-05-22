"""Test import compatibility for internal and exported package layouts.

The internal repository exposes semantic contracts from the top-level
``semantic`` package. The generated public package exposes the same code under
``lynkmesh.semantic``.

The semantic contract tests intentionally keep the shorter internal imports.
When those tests run against the generated package layout, this pytest shim maps
``semantic`` to ``lynkmesh.semantic`` before test modules are collected.
"""

from __future__ import annotations

import importlib
import sys


def _install_exported_package_alias() -> None:
    """Alias ``semantic`` imports to ``lynkmesh.semantic`` when needed."""

    try:
        importlib.import_module("semantic.contracts")
        return
    except ModuleNotFoundError as exc:
        if exc.name not in {"semantic", "semantic.contracts"}:
            raise

    exported_semantic = importlib.import_module("lynkmesh.semantic")
    exported_contracts = importlib.import_module("lynkmesh.semantic.contracts")

    sys.modules.setdefault("semantic", exported_semantic)
    sys.modules.setdefault("semantic.contracts", exported_contracts)


_install_exported_package_alias()
