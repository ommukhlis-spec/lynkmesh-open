# lynkmesh/config.py
"""
LynkMesh Configuration — single source of truth for system paths and settings.

This module provides a compatibility layer for Stage 3’s legacy parser bridge.
All lookups are ordered, deterministic where possible, and side‑effect‑free
after initial resolution.  Paths are norm resolved (symlinks expanded) to
guarantee stable identity across runs.

Migrating to Stage 3 native IR will make this module unnecessary.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_cached_legacy_root: Path | None = None


def _find_repo_root() -> Path:
    """
    Walk up from this file to locate the repository root.

    Look for a marker file/folder common in the project layout
    (``.git`` or ``pyproject.toml``).  Falls back to the parent of the
    top‑level ``lynkmesh`` directory if no marker is found.

    This is deterministic because it is based solely on ``__file__``.
    """
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        # check for known repository markers
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent

    # fallback: assume structure  repo / lynkmesh / config.py
    #             -> repo is two levels up
    return current.parents[2]


# ---------------------------------------------------------------------------
# Parser bridge resolution sources (Stage 4.2.5.5C)
# ---------------------------------------------------------------------------

PARSER_SOURCE_EXPLICIT = "explicit_parser_path"
PARSER_SOURCE_INTERNAL = "internal_bundle"
PARSER_SOURCE_LEGACY = "legacy_root_fallback"
PARSER_SOURCE_UNRESOLVED = "unresolved"


def get_internal_php_bridge_dir() -> Path:
    """Return the internal PHP bridge directory bundled with LynkMesh."""
    return Path(__file__).resolve().parent / "ingestion" / "php_bridge"


def get_internal_parser_path() -> Path:
    """Return the bundled internal parser.php path."""
    return get_internal_php_bridge_dir() / "parser.php"


def resolve_parser_path() -> tuple[Path | None, dict]:
    """
    Resolve parser.php without raising.

    Resolution order:
    1. LYNKMESH_PARSER_PATH
    2. internal ingestion/php_bridge/parser.php
    3. LYNKMESH_LEGACY_ROOT fallback
    4. unresolved
    """
    explicit_raw = os.getenv("LYNKMESH_PARSER_PATH")
    legacy_raw = os.getenv("LYNKMESH_LEGACY_ROOT")

    internal_parser = get_internal_parser_path()

    info = {
        "source": PARSER_SOURCE_UNRESOLVED,
        "resolved_path": None,
        "explicit_parser_path_was_set": bool(explicit_raw),
        "explicit_parser_path": explicit_raw,
        "explicit_parser_path_exists": None,
        "internal_bundle_path": str(internal_parser),
        "internal_bundle_exists": internal_parser.exists(),
        "legacy_root_was_set": bool(legacy_raw),
        "legacy_root": legacy_raw,
        "legacy_parser_path": None,
        "legacy_parser_exists": False,
    }

    if explicit_raw:
        explicit_path = Path(explicit_raw).resolve()
        info["explicit_parser_path_exists"] = explicit_path.exists()
        if explicit_path.exists():
            info["source"] = PARSER_SOURCE_EXPLICIT
            info["resolved_path"] = str(explicit_path)
            return explicit_path, info

    if internal_parser.exists():
        info["source"] = PARSER_SOURCE_INTERNAL
        info["resolved_path"] = str(internal_parser)
        return internal_parser, info

    if legacy_raw:
        try:
            legacy_root = Path(legacy_raw).resolve()
            legacy_candidates = [
                legacy_root / "ast_bridge" / "parser.php",
                legacy_root / "lynkmesh" / "ast_bridge" / "parser.php",
            ]
            for candidate in legacy_candidates:
                info["legacy_parser_path"] = str(candidate)
                info["legacy_parser_exists"] = candidate.exists()
                if candidate.exists():
                    info["source"] = PARSER_SOURCE_LEGACY
                    info["resolved_path"] = str(candidate)
                    return candidate, info
        except Exception:
            pass

    return None, info


# ---------------------------------------------------------------------------
# Public API — Legacy runtime compatibility
# ---------------------------------------------------------------------------

def get_legacy_root() -> Path:
    """
    Return the absolute path to the optional legacy compatibility workspace.

    Resolution order (first existing wins):

    1. Environment variable ``LYNKMESH_LEGACY_ROOT`` (absolute)
    2. ``./legacy_runtime`` (relative to current working directory)
    3. ``../legacy_runtime`` (relative to current working directory)
    4. ``<repository-root>/legacy_runtime`` (deterministic, repo‑root based)
    5. ``<repository-root>/../legacy_runtime`` (sibling project layout)

    The result is **cached** after the first successful lookup – the same
    ``Path`` object is returned for the remainder of the process.

    Stage 3 migration context:
       This function exists solely for the legacy PHP parser bridge.
       Once the native parser is the default, the legacy runtime can be
       removed entirely.

    Raises:
        FileNotFoundError: if none of the candidate locations exist.
    """
    global _cached_legacy_root
    if _cached_legacy_root is not None:
        return _cached_legacy_root

    repo_root = _find_repo_root()

    # ordered list of (description, path) candidates
    candidates: list[tuple[str, Path]] = []

    # 1 – explicit environment variable
    env_path = os.getenv("LYNKMESH_LEGACY_ROOT")
    if env_path:
        candidates.append(("env var LYNKMESH_LEGACY_ROOT", Path(env_path).resolve()))

    # 2 – ./legacy_runtime  (cwd‑dependent, kept for backwards compatibility)
    cwd_candidate = Path.cwd() / "legacy_runtime"
    candidates.append(("$CWD/legacy_runtime", cwd_candidate))

    # 3 – ../legacy_runtime  (cwd‑dependent)
    cwd_parent_candidate = Path.cwd().parent / "legacy_runtime"
    candidates.append(("$CWD/../legacy_runtime", cwd_parent_candidate))

    # 4 – repo‑root/legacy_runtime
    repo_legacy = repo_root / "legacy_runtime"
    candidates.append(("repository root", repo_legacy))

    # 5 – sibling project layout  (repo_root/../legacy_runtime)
    sibling_legacy = repo_root.parent / "legacy_runtime"
    candidates.append(("sibling of repository", sibling_legacy))

    attempted: list[str] = []
    for desc, cand in candidates:
        resolved = cand.resolve()
        attempted.append(f"  • {desc}  ->  {resolved}")
        if resolved.exists():
            _cached_legacy_root = resolved
            which = "env var" if desc.startswith("env") else "fallback"
            logger.info(
                "Legacy runtime root resolved via %s: %s",
                which,
                resolved,
            )
            return resolved

    # none found – raise with helpful context
    raise FileNotFoundError(
        "Legacy project root not found.\n"
        "Tried the following locations:\n"
        + "\n".join(attempted)
        + f"\n\nCurrent working directory: {Path.cwd()}\n"
        "Set LYNKMESH_LEGACY_ROOT environment variable to an existing directory, "
        "or place a 'legacy_runtime' folder in one of the listed locations."
    )


def has_legacy_runtime() -> bool:
    """
    Return ``True`` if the legacy compatibility workspace can be located.

    Does **not** raise an exception.
    """
    try:
        get_legacy_root()
    except FileNotFoundError:
        return False
    return True


def get_legacy_lynkmesh_path() -> Path:
    """
    Return the Python import root for the legacy LynkMesh runtime.

    The legacy PHP bridge has two separate concerns:

    1. Python import root:
       must contain:
         - core/parallel_parser.py
         - ir_engine.py

    2. PHP parser path:
       usually lives at:
         - ast_bridge/parser.php

    Supports current migration layout:

        legacy_runtime_backup/
        ├── ast_bridge/parser.php
        └── lynkmesh/
            ├── core/parallel_parser.py
            └── ir_engine.py

    Also supports older direct layout where the root itself contains
    core/parallel_parser.py and ir_engine.py.
    """
    legacy_root = get_legacy_root()

    candidates = [
        legacy_root / "lynkmesh",  # current backup layout
        legacy_root,               # direct legacy layout
    ]

    attempted: list[str] = []
    for candidate in candidates:
        parallel_parser = candidate / "core" / "parallel_parser.py"
        ir_engine = candidate / "ir_engine.py"
        attempted.append(
            f"  • {candidate} "
            f"(parallel_parser={parallel_parser.exists()}, ir_engine={ir_engine.exists()})"
        )

        if parallel_parser.exists() and ir_engine.exists():
            return candidate

    raise FileNotFoundError(
        "Legacy LynkMesh Python import root not found.\n"
        "Expected a folder containing both:\n"
        "  - core/parallel_parser.py\n"
        "  - ir_engine.py\n"
        "Tried:\n"
        + "\n".join(attempted)
        + "\n\nSet LYNKMESH_LEGACY_ROOT to the legacy backup root, "
        "for example: legacy_runtime_backup"
    )


# ---------------------------------------------------------------------------
# Public API — Parser path resolution (updated Stage 4.2.5.5C)
# ---------------------------------------------------------------------------

def get_parser_path() -> Path:
    """
    Return the absolute path to ``parser.php``.

    Resolution order:

    1. Environment variable ``LYNKMESH_PARSER_PATH``
    2. Internal bundled bridge: ingestion/php_bridge/parser.php
    3. Legacy runtime fallback
    """
    path, info = resolve_parser_path()
    if path is not None:
        return path

    raise FileNotFoundError(
        "parser.php not found.\n"
        "Tried:\n"
        f"  • LYNKMESH_PARSER_PATH: {info.get('explicit_parser_path')} "
        f"(exists={info.get('explicit_parser_path_exists')})\n"
        f"  • Internal bundle: {info.get('internal_bundle_path')} "
        f"(exists={info.get('internal_bundle_exists')})\n"
        f"  • Legacy fallback from LYNKMESH_LEGACY_ROOT: {info.get('legacy_root')} "
        f"(parser={info.get('legacy_parser_path')}, exists={info.get('legacy_parser_exists')})\n"
        "\nSet LYNKMESH_PARSER_PATH directly, restore the internal php_bridge, "
        "or configure LYNKMESH_LEGACY_ROOT as fallback."
    )