# lynkmesh/core/graph_cache.py
"""
Stage 3.2.0 — Canonical Graph Cache

Persistent filesystem cache for finalized GraphCore snapshots, keyed by
GraphVersion.content_hash. Built on top of GraphSerializer.

Tier: 0 (core). Allowed imports: stdlib only +
    lynkmesh.core.graph_serializer
    lynkmesh.core.graph_version

NOT allowed: imports from graph/, query/, exporters/, ai/, pipeline/.

Architecture spec references:
    §10 — Cache philosophy
    §11 — Persistence philosophy
    §15 — Determinism: cache reads return byte-identical data
    §20 — Graph versioning: cache keyed by content_hash

Cache invariants:
    C1 — All persistent identity uses GraphVersion.content_hash, never hash()
    C2 — Cache writes are atomic (temp file + os.replace)
    C3 — Cache directory layout is content-addressable
    C4 — Reads validate cache_schema_version and serializer_schema_version
    C5 — Cache does not mutate graph state (read-only with respect to GraphCore)
    C6 — Two saves of same content → idempotent (no rewrite)
    C7 — Save requires finalized graph (delegates to serializer)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lynkmesh.core.graph_serializer import (
    SERIALIZER_SCHEMA_VERSION,
    GraphNotFinalizedError,
    SerializerConsistencyError,
    compute_content_hash,
    serialize_graph,
)
from lynkmesh.core.graph_version import (
    JSON_SERIALIZATION_OPTIONS,
    compute_edge_identity,
    compute_node_identity,
)


# =============================================================================
# Constants
# =============================================================================

# Cache file schema version. Independent of serializer schema version.
# Bump on any breaking change to cache file structure.
CACHE_SCHEMA_VERSION: str = "3.2.0"

# Required top-level keys in content cache files.
_CONTENT_FILE_KEYS = frozenset({"cache_schema_version", "cached_at", "payload"})

# Required top-level keys in ref pointer files.
_REF_FILE_KEYS = frozenset({
    "cache_schema_version", "graph_id", "build_id", "content_hash", "cached_at"
})

# Subdirectory names within cache_dir.
_CONTENT_SUBDIR = "content"
_REFS_SUBDIR = "refs"
_BUILDS_SUBDIR = "builds"

# Reserved filename for "latest build of a graph_id" pointer.
_LATEST_REF_NAME = "latest.json"


# =============================================================================
# Error types
# =============================================================================

class CacheError(Exception):
    """Base for all cache errors."""


class CacheInitError(CacheError):
    """Raised when cache directory cannot be initialized."""


class CacheMissError(CacheError):
    """Raised when a requested cache entry is not found."""


class CacheSchemaMismatchError(CacheError):
    """Raised when cached file schema_version does not match current code."""


class CacheCorruptionError(CacheError):
    """Raised when cache file is malformed or content_hash mismatch detected."""


# =============================================================================
# Public types
# =============================================================================

@dataclass(frozen=True)
class CacheRecord:
    """Returned by save(): describes the resulting cache entry."""
    content_hash: str
    graph_id: str
    build_id: str
    content_path: Path
    cached_at: str
    deduplicated: bool  # True if save was a no-op (content already cached)


@dataclass(frozen=True)
class CacheEntry:
    """Returned by load_*(): the cached payload plus metadata."""
    payload: Dict[str, Any]
    content_hash: str
    cached_at: str


@dataclass(frozen=True)
class VerifyResult:
    """Returned by verify(): result of deep validation."""
    ok: bool
    content_hash: str
    recomputed_hash: Optional[str]
    error: Optional[str]


# =============================================================================
# Internal helpers
# =============================================================================

def _now_utc_iso() -> str:
    """Current UTC time as ISO 8601 string. Only place we read system time."""
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """
    Atomically write JSON to path. Uses pinned serialization options.

    Process:
        1. Ensure parent exists.
        2. Write to temp file in same parent directory.
        3. fsync temp file.
        4. os.replace temp → target (atomic on POSIX and Windows).
        5. On exception, attempt to remove temp file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_str = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_str)
    try:
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, **JSON_SERIALIZATION_OPTIONS)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            # fd is closed by os.fdopen context; if open failed, fd may
            # still need closing — handle defensively.
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        os.replace(str(temp_path), str(path))
    except Exception:
        # Cleanup temp file on any failure.
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Dict[str, Any]:
    """Read and parse JSON file. Raise CacheCorruptionError on parse failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise CacheCorruptionError(
            f"Cache file is not valid JSON: {path}"
        ) from exc
    except OSError as exc:
        raise CacheCorruptionError(
            f"Cannot read cache file: {path}"
        ) from exc
    if not isinstance(data, dict):
        raise CacheCorruptionError(
            f"Cache file root must be JSON object, got {type(data).__name__}: {path}"
        )
    return data


def _validate_content_file(data: Dict[str, Any], path: Path) -> None:
    """Validate a content cache file structure. Raise on any deviation."""
    keys = set(data.keys())
    if keys != _CONTENT_FILE_KEYS:
        raise CacheCorruptionError(
            f"Cache content file has wrong keys. "
            f"Expected {sorted(_CONTENT_FILE_KEYS)}, got {sorted(keys)}: {path}"
        )
    cache_schema = data.get("cache_schema_version")
    if cache_schema != CACHE_SCHEMA_VERSION:
        raise CacheSchemaMismatchError(
            f"Cache file uses cache_schema_version={cache_schema!r}, "
            f"current code expects {CACHE_SCHEMA_VERSION!r}: {path}"
        )
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise CacheCorruptionError(
            f"Cache file payload must be a JSON object: {path}"
        )
    serializer_schema = payload.get("schema_version")
    if serializer_schema != SERIALIZER_SCHEMA_VERSION:
        raise CacheSchemaMismatchError(
            f"Cache file payload uses serializer schema_version={serializer_schema!r}, "
            f"current code expects {SERIALIZER_SCHEMA_VERSION!r}: {path}"
        )
    version_block = payload.get("version")
    if not isinstance(version_block, dict):
        raise CacheCorruptionError(
            f"Cache file payload missing 'version' block: {path}"
        )
    if "content_hash" not in version_block:
        raise CacheCorruptionError(
            f"Cache file payload.version missing content_hash: {path}"
        )


def _validate_ref_file(data: Dict[str, Any], path: Path) -> None:
    """Validate a ref pointer file structure."""
    keys = set(data.keys())
    if keys != _REF_FILE_KEYS:
        raise CacheCorruptionError(
            f"Cache ref file has wrong keys. "
            f"Expected {sorted(_REF_FILE_KEYS)}, got {sorted(keys)}: {path}"
        )
    cache_schema = data.get("cache_schema_version")
    if cache_schema != CACHE_SCHEMA_VERSION:
        raise CacheSchemaMismatchError(
            f"Cache ref file uses cache_schema_version={cache_schema!r}, "
            f"current code expects {CACHE_SCHEMA_VERSION!r}: {path}"
        )


# =============================================================================
# GraphCache
# =============================================================================

class GraphCache:
    """
    Filesystem cache for serialized graph snapshots.

    Construction validates that cache_dir exists and is writable.
    No automatic invalidation. No global state. No background threads.

    Thread safety: NOT thread-safe. Concurrent saves from multiple threads
    or processes against the same cache_dir is undefined. POSIX rename
    semantics mean writes won't corrupt existing files, but ref-pointer
    updates can race. Use external locking if needed.
    """

    def __init__(self, cache_dir: os.PathLike) -> None:
        """
        Args:
            cache_dir: Path to cache directory. Must exist and be writable.

        Raises:
            CacheInitError: if cache_dir does not exist or is not writable.
        """
        self._cache_dir = Path(cache_dir)
        if not self._cache_dir.exists():
            raise CacheInitError(
                f"Cache directory does not exist: {self._cache_dir}. "
                f"Create it before constructing GraphCache."
            )
        if not self._cache_dir.is_dir():
            raise CacheInitError(
                f"Cache path is not a directory: {self._cache_dir}"
            )
        if not os.access(str(self._cache_dir), os.W_OK):
            raise CacheInitError(
                f"Cache directory is not writable: {self._cache_dir}"
            )
        # Create subdirectories lazily if missing.
        (self._cache_dir / _CONTENT_SUBDIR).mkdir(exist_ok=True)
        (self._cache_dir / _REFS_SUBDIR).mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @property
    def cache_dir(self) -> Path:
        """Public read-only access to cache directory path."""
        return self._cache_dir

    def _content_path(self, content_hash: str) -> Path:
        return self._cache_dir / _CONTENT_SUBDIR / f"{content_hash}.json"

    def _graph_refs_dir(self, graph_id: str) -> Path:
        return self._cache_dir / _REFS_SUBDIR / graph_id

    def _latest_ref_path(self, graph_id: str) -> Path:
        return self._graph_refs_dir(graph_id) / _LATEST_REF_NAME

    def _build_ref_path(self, graph_id: str, build_id: str) -> Path:
        return self._graph_refs_dir(graph_id) / _BUILDS_SUBDIR / f"{build_id}.json"

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, graph: Any) -> CacheRecord:
        """
        Serialize and cache a finalized graph.

        Idempotent: if content_hash already exists, content file is not
        rewritten. Ref files are always refreshed (graph_id/latest, builds/<id>).

        Args:
            graph: Finalized GraphCore instance.

        Returns:
            CacheRecord describing the cached entry.

        Raises:
            GraphNotFinalizedError: if graph.version is not finalized.
            SerializerConsistencyError: if serializer detects identity drift.
        """
        # Serialize first — this validates finalization and consistency.
        payload = serialize_graph(graph)
        version_block = payload["version"]
        content_hash = version_block["content_hash"]
        metadata = version_block["metadata"]
        graph_id = metadata["graph_id"]
        build_id = metadata["build_id"]
        cached_at = _now_utc_iso()

        content_path = self._content_path(content_hash)
        deduplicated = content_path.exists()

        if not deduplicated:
            content_file = {
                "cache_schema_version": CACHE_SCHEMA_VERSION,
                "cached_at": cached_at,
                "payload": payload,
            }
            _atomic_write_json(content_path, content_file)

        # Ref files always refresh (cached_at and build mapping).
        ref_data_build = {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "graph_id": graph_id,
            "build_id": build_id,
            "content_hash": content_hash,
            "cached_at": cached_at,
        }
        _atomic_write_json(self._build_ref_path(graph_id, build_id), ref_data_build)

        ref_data_latest = {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "graph_id": graph_id,
            "build_id": build_id,
            "content_hash": content_hash,
            "cached_at": cached_at,
        }
        _atomic_write_json(self._latest_ref_path(graph_id), ref_data_latest)

        return CacheRecord(
            content_hash=content_hash,
            graph_id=graph_id,
            build_id=build_id,
            content_path=content_path,
            cached_at=cached_at,
            deduplicated=deduplicated,
        )

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_by_content_hash(self, content_hash: str) -> CacheEntry:
        """
        Load a cached entry by its content_hash.

        Validates: file exists, JSON parseable, schema versions match,
        payload structure correct, claimed content_hash matches filename.

        Raises:
            CacheMissError: if no entry exists for this content_hash.
            CacheCorruptionError: if file is malformed.
            CacheSchemaMismatchError: if schema versions disagree.
        """
        path = self._content_path(content_hash)
        if not path.exists():
            raise CacheMissError(
                f"No cache entry for content_hash={content_hash!r}"
            )
        data = _read_json(path)
        _validate_content_file(data, path)
        # Cross-check: claimed content_hash must match filename.
        claimed = data["payload"]["version"]["content_hash"]
        if claimed != content_hash:
            raise CacheCorruptionError(
                f"Cache file content_hash mismatch. "
                f"Filename claims {content_hash!r}, payload claims {claimed!r}: {path}"
            )
        return CacheEntry(
            payload=data["payload"],
            content_hash=content_hash,
            cached_at=data["cached_at"],
        )

    def load_latest(self, graph_id: str) -> CacheEntry:
        """
        Load the most recently saved entry for a graph_id.

        Raises:
            CacheMissError: if no entry exists for this graph_id.
        """
        ref_path = self._latest_ref_path(graph_id)
        if not ref_path.exists():
            raise CacheMissError(
                f"No latest cache entry for graph_id={graph_id!r}"
            )
        ref_data = _read_json(ref_path)
        _validate_ref_file(ref_data, ref_path)
        content_hash = ref_data["content_hash"]
        return self.load_by_content_hash(content_hash)

    def load_build(self, graph_id: str, build_id: str) -> CacheEntry:
        """
        Load a specific build entry.

        Raises:
            CacheMissError: if no entry exists for this (graph_id, build_id).
        """
        ref_path = self._build_ref_path(graph_id, build_id)
        if not ref_path.exists():
            raise CacheMissError(
                f"No cache entry for graph_id={graph_id!r}, build_id={build_id!r}"
            )
        ref_data = _read_json(ref_path)
        _validate_ref_file(ref_data, ref_path)
        content_hash = ref_data["content_hash"]
        return self.load_by_content_hash(content_hash)

    # ------------------------------------------------------------------
    # Existence checks
    # ------------------------------------------------------------------

    def exists_by_content_hash(self, content_hash: str) -> bool:
        """Cheap path-exists check. No deserialization."""
        return self._content_path(content_hash).exists()

    def exists_latest(self, graph_id: str) -> bool:
        """Cheap path-exists check for graph_id's latest ref."""
        return self._latest_ref_path(graph_id).exists()

    def exists_build(self, graph_id: str, build_id: str) -> bool:
        """Cheap path-exists check for a specific build ref."""
        return self._build_ref_path(graph_id, build_id).exists()

    # ------------------------------------------------------------------
    # Deletion (explicit, never automatic)
    # ------------------------------------------------------------------

    def delete_by_content_hash(self, content_hash: str) -> bool:
        """
        Delete a content cache file. Does NOT delete ref files pointing
        to it (those become dangling and will raise on load).

        Returns:
            True if a file was deleted, False if no file existed.
        """
        path = self._content_path(content_hash)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_refs_for_graph(self, graph_id: str) -> int:
        """
        Delete all ref files for a graph_id. Does NOT touch content files.

        Returns:
            Count of ref files deleted.
        """
        refs_dir = self._graph_refs_dir(graph_id)
        if not refs_dir.exists():
            return 0
        count = 0
        for ref_file in refs_dir.rglob("*.json"):
            if ref_file.is_file():
                ref_file.unlink()
                count += 1
        # Try to remove now-empty directories. shutil.rmtree handles non-empty
        # gracefully, but we want to be lenient here — directory may have
        # subdirs.
        try:
            shutil.rmtree(refs_dir)
        except OSError:
            pass
        return count

    # ------------------------------------------------------------------
    # Verify (opt-in deep validation)
    # ------------------------------------------------------------------

    def verify(self, content_hash: str) -> VerifyResult:
        """
        Deep validation: recomputes content_hash from cached payload's
        identity stream and compares to claimed content_hash.

        Expensive (O(nodes + edges) hash recomputation). Not invoked on
        every load. Use for diagnostics, debugging, or post-restore checks.

        Returns:
            VerifyResult with ok=True if hashes match, ok=False otherwise.
            Does NOT raise on mismatch — returns structured result.
        """
        try:
            entry = self.load_by_content_hash(content_hash)
        except CacheError as exc:
            return VerifyResult(
                ok=False,
                content_hash=content_hash,
                recomputed_hash=None,
                error=str(exc),
            )
        # Reconstruct identity stream from payload.
        # Note: payload's nodes/edges contain {"identity": ..., "uuid": ...}
        # entries. The identity dicts have already been canonicalized by
        # the serializer. To recompute content_hash, we need the original
        # node/edge dicts. We do NOT have those — only the canonicalized
        # identity blocks. So verify() compares the IDENTITY stream itself.
        # This is sufficient because compute_content_hash is a pure function
        # of the canonical identity output: same identity → same hash.
        try:
            nodes_identities = [n["identity"] for n in entry.payload["nodes"]]
            edges_identities = [e["identity"] for e in entry.payload["edges"]]
        except (KeyError, TypeError) as exc:
            return VerifyResult(
                ok=False,
                content_hash=content_hash,
                recomputed_hash=None,
                error=f"Malformed payload: {exc}",
            )
        # Reconstruct pseudo-nodes/edges that compute_content_hash can consume.
        # We synthesize node dicts whose compute_node_identity output matches
        # the stored identity. This requires bypassing the function and
        # hashing the identities directly via the same canonical path.
        try:
            recomputed = _hash_from_identity_stream(
                nodes_identities, edges_identities,
            )
        except Exception as exc:
            return VerifyResult(
                ok=False,
                content_hash=content_hash,
                recomputed_hash=None,
                error=f"Recomputation failed: {exc}",
            )
        return VerifyResult(
            ok=(recomputed == content_hash),
            content_hash=content_hash,
            recomputed_hash=recomputed,
            error=None if recomputed == content_hash else "Hash mismatch",
        )

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_graph_ids(self) -> List[str]:
        """Return sorted list of graph_ids present in refs/."""
        refs_root = self._cache_dir / _REFS_SUBDIR
        if not refs_root.exists():
            return []
        return sorted(p.name for p in refs_root.iterdir() if p.is_dir())

    def list_builds(self, graph_id: str) -> List[str]:
        """Return sorted list of build_ids for a graph_id."""
        builds_dir = self._graph_refs_dir(graph_id) / _BUILDS_SUBDIR
        if not builds_dir.exists():
            return []
        return sorted(
            p.stem for p in builds_dir.iterdir()
            if p.is_file() and p.suffix == ".json"
        )

    def list_content_hashes(self) -> List[str]:
        """Return sorted list of content_hashes in content/."""
        content_root = self._cache_dir / _CONTENT_SUBDIR
        if not content_root.exists():
            return []
        return sorted(
            p.stem for p in content_root.iterdir()
            if p.is_file() and p.suffix == ".json"
        )


# =============================================================================
# Internal: hash recomputation from identity stream
# =============================================================================

def _hash_from_identity_stream(
    node_identities: List[Dict[str, Any]],
    edge_identities: List[Dict[str, Any]],
) -> str:
    """
    Recompute content_hash directly from canonical identity dicts.

    This bypasses compute_node_identity / compute_edge_identity (which
    expect raw node/edge dicts) and operates on pre-canonicalized
    identities. The hash algorithm itself is reused from graph_version.py
    via direct invocation of the same SHA-256 / JSON / blob structure.

    Used by verify() to deep-check cached payloads against their claimed
    content_hash.
    """
    import hashlib
    from lynkmesh.core.graph_version import (
        HASH_ALGORITHM,
        HASH_BLOB_SEPARATOR,
        HASH_EDGES_PREFIX,
        HASH_NODES_PREFIX,
    )

    node_strings = sorted(
        json.dumps(ident, **JSON_SERIALIZATION_OPTIONS)
        for ident in node_identities
    )
    nodes_blob = HASH_BLOB_SEPARATOR.join(
        s.encode("utf-8") for s in node_strings
    )
    edge_strings = sorted(
        json.dumps(ident, **JSON_SERIALIZATION_OPTIONS)
        for ident in edge_identities
    )
    edges_blob = HASH_BLOB_SEPARATOR.join(
        s.encode("utf-8") for s in edge_strings
    )
    payload = HASH_NODES_PREFIX + nodes_blob + HASH_EDGES_PREFIX + edges_blob
    return hashlib.new(HASH_ALGORITHM, payload).hexdigest()


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    "GraphCache",
    "CacheRecord",
    "CacheEntry",
    "VerifyResult",
    "CacheError",
    "CacheInitError",
    "CacheMissError",
    "CacheSchemaMismatchError",
    "CacheCorruptionError",
    "CACHE_SCHEMA_VERSION",
]