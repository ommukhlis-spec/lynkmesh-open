# lynkmesh/pipeline/incremental_pipeline.py
"""
Stage 3.4.0 — IncrementalPipeline

A thin orchestration layer over:
    - Orchestrator (full build)
    - GraphSerializer (canonical payload)
    - GraphCache (persistence)
    - IncrementalDiffEngine (compare against prior)

Stage 3.4.0 always runs a FULL build via Orchestrator. The "incremental"
designation refers to the comparison output (what changed since last
cached build), not to skipping work. Partial parsing/rebuild is deferred
to Stage 3.5+.

Tier: 5 (pipeline composition). Allowed imports:
    stdlib
    lynkmesh.core.graph_cache
    lynkmesh.core.graph_serializer
    lynkmesh.core.graph_version (transitively)
    lynkmesh.core.incremental_diff
    lynkmesh.pipeline.orchestrator

NOT allowed: imports from devtools/, mcp/, cli/.

Architecture spec references:
    §3  — read-only with respect to graph state
    §15 — determinism: same input + same cache state → same report
    §20 — graph versioning: content_hash is persistent identity

Pipeline invariants:
    P1 — Pipeline is additive: no behavioral changes to Orchestrator
    P2 — Cache-disabled mode is fully supported (cache_dir=None)
    P3 — Cache miss is normal; corruption is recoverable; build failure is fatal
    P4 — Prior cached entry is captured BEFORE save to avoid self-comparison
    P5 — Report is JSON-safe (to_dict produces dict serializable via json.dumps)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lynkmesh.core.graph_cache import (
    CacheCorruptionError,
    CacheEntry,
    CacheError,
    CacheMissError,
    CacheRecord,
    CacheSchemaMismatchError,
    GraphCache,
)
from lynkmesh.core.graph_serializer import serialize_graph
from lynkmesh.core.incremental_diff import (
    DiffReport,
    MalformedPayloadError,
    diff_payloads,
)
from lynkmesh.pipeline.orchestrator import Orchestrator


# =============================================================================
# Constants
# =============================================================================

PIPELINE_SCHEMA_VERSION: str = "3.4.0"

# Stage 3.5.0 — result_status enum.
# Top-level outcome flag for consumers. "success" means build + serialize
# completed; cache and comparison sub-statuses give the detail.
# Future Stage 3.6+ may introduce "partial_success" (e.g., build succeeded
# but cache save failed via soft-handle). Adding new values is non-breaking.
RESULT_STATUS_SUCCESS: str = "success"

# Cache status values exposed in report.
CACHE_STATUS_SAVED: str = "saved"

CACHE_STATUS_DEDUPLICATED: str = "deduplicated"
CACHE_STATUS_DISABLED: str = "disabled"
CACHE_STATUS_SAVE_SKIPPED: str = "save_skipped"

# Comparison status values exposed in report.
COMPARISON_STATUS_NO_PRIOR: str = "no_prior"
COMPARISON_STATUS_PRIOR_CORRUPT: str = "prior_corrupt"
COMPARISON_STATUS_COMPARED: str = "compared"
COMPARISON_STATUS_DISABLED: str = "comparison_disabled"


# =============================================================================
# Error types
# =============================================================================

class PipelineError(Exception):
    """Base class for IncrementalPipeline errors."""


class PipelineConfigurationError(PipelineError):
    """Raised when pipeline is constructed with invalid configuration."""


# =============================================================================
# Public types
# =============================================================================

@dataclass(frozen=True)
class IncrementalRunReport:
    """
    Result of a single IncrementalPipeline.run() call.

    Stage 3.5.0 freeze: this report's to_dict() output is the public ABI
    for downstream CLI/MCP consumers. See INCREMENTAL_PIPELINE_API.md
    and test_incremental_pipeline_schema.py for the frozen schema contract.

    The full DiffReport is accessible via `diff_report` attribute but is
    NOT embedded in to_dict() by default (use include_full_diff=True).
    """
    pipeline_schema_version: str
    completed_at: str
    project_path: str
    current_graph_id: str
    current_build_id: str
    current_content_hash: str
    current_stats: Dict[str, Any]
    cache_enabled: bool
    cache_status: str
    cache_dir: Optional[str]
    content_path: Optional[str]
    comparison_status: str
    prior_content_hash: Optional[str]
    prior_build_id: Optional[str]
    diff_report: Optional[DiffReport] = None
    warnings: List[str] = field(default_factory=list)
    # Stage 3.5.0 addition: marker for explicit-hash compare mode.
    # None = implicit latest lookup; str = explicit hash provided.
    _explicit_compare_hash: Optional[str] = None

    # ------------------------------------------------------------------
    # Derived properties (Stage 3.5.0 additions)
    # ------------------------------------------------------------------

    @property
    def result_status(self) -> str:
        """
        Top-level outcome flag. Currently always 'success' because any
        non-success outcome raises before the report is constructed.
        Future stages may add 'partial_success' etc.
        """
        return RESULT_STATUS_SUCCESS

    @property
    def has_changes(self) -> bool:
        """
        True iff comparison detected any added/removed/changed nodes or edges.

        Returns False when:
            - No prior to compare against (comparison_status='no_prior')
            - Prior was corrupt (comparison_status='prior_corrupt')
            - Cache disabled (comparison_status='comparison_disabled')
            - Diff reported identical=True
        """
        if self.diff_report is None:
            return False
        s = self.diff_report.summary
        return any(s.get(k, 0) for k in (
            "nodes_added", "nodes_removed", "nodes_changed",
            "edges_added", "edges_removed", "edges_changed",
        ))

    @property
    def compared_against_explicit_hash(self) -> bool:
        """
        True iff this run used compare_against_content_hash override
        rather than implicit latest lookup.

        Derived from a stored attribute set during run() (see _run_metadata).
        """
        return bool(self._explicit_compare_hash)

    def change_counts(self) -> Dict[str, int]:
        """
        Flat dict of change counters. Stable shape:
            {nodes_added, nodes_removed, nodes_changed,
             edges_added, edges_removed, edges_changed}

        All zero when diff_report is None.
        """
        if self.diff_report is None:
            return {
                "nodes_added": 0, "nodes_removed": 0, "nodes_changed": 0,
                "edges_added": 0, "edges_removed": 0, "edges_changed": 0,
            }
        s = self.diff_report.summary
        return {
            "nodes_added": int(s.get("nodes_added", 0)),
            "nodes_removed": int(s.get("nodes_removed", 0)),
            "nodes_changed": int(s.get("nodes_changed", 0)),
            "edges_added": int(s.get("edges_added", 0)),
            "edges_removed": int(s.get("edges_removed", 0)),
            "edges_changed": int(s.get("edges_changed", 0)),
        }

    # ------------------------------------------------------------------
    # Consumer-facing helpers (Stage 3.5.0 additions)
    # ------------------------------------------------------------------

    def summary_line(self) -> str:
        """
        One-line human-readable summary for CLI/log output. Stable format:

            <icon> <state>: <details> build=<hash8> [prior=<hash8>]

        States:
            'identical'      — content_hash matches prior
            'changed'        — diff has non-zero changes
            'first build'    — no prior exists
            'prior corrupt'  — cache returned a bad payload
            'cache disabled' — no cache_dir configured
        """
        nodes = self.current_stats.get("nodes", "?")
        edges = self.current_stats.get("edges", "?")
        build_hash8 = (self.current_content_hash or "")[:8]
        prior_hash8 = (self.prior_content_hash or "")[:8] if self.prior_content_hash else None

        if self.comparison_status == COMPARISON_STATUS_DISABLED:
            return f"🚫 cache disabled ({nodes}n/{edges}e) build={build_hash8}"
        if self.comparison_status == COMPARISON_STATUS_NO_PRIOR:
            return f"🆕 first build ({nodes}n/{edges}e) build={build_hash8}"
        if self.comparison_status == COMPARISON_STATUS_PRIOR_CORRUPT:
            return f"⚠️  prior corrupt ({nodes}n/{edges}e) build={build_hash8}"
        # comparison_status == COMPARISON_STATUS_COMPARED
        if self.diff_report is not None and self.diff_report.identical:
            return (
                f"✅ identical ({nodes}n/{edges}e) "
                f"build={build_hash8} prior={prior_hash8}"
            )
        # Changes detected
        c = self.change_counts()
        return (
            f"✏️  changed: "
            f"+{c['nodes_added']}/-{c['nodes_removed']}/~{c['nodes_changed']}n "
            f"+{c['edges_added']}/-{c['edges_removed']}/~{c['edges_changed']}e "
            f"build={build_hash8} prior={prior_hash8}"
        )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Minimal JSON-safe summary dict for consumers that only need outcomes.

        Stable shape (Stage 3.5.0 contract):
            {
              "pipeline_schema_version": "3.4.0",
              "result_status": "success",
              "content_hash": "<hex>",
              "graph_id": "<uuid>",
              "build_id": "<uuid>",
              "stats": {"nodes": N, "edges": N, ...},
              "cache_status": "<enum>",
              "comparison_status": "<enum>",
              "has_changes": bool,
              "change_counts": {...},
              "compared_against_explicit_hash": bool,
              "prior_content_hash": "<hex or null>"
            }

        This is the recommended payload shape for CLI/MCP responses.
        Does NOT include warnings, full diff, full timestamps, or paths.
        """
        return {
            "pipeline_schema_version": self.pipeline_schema_version,
            "result_status": self.result_status,
            "content_hash": self.current_content_hash,
            "graph_id": self.current_graph_id,
            "build_id": self.current_build_id,
            "stats": dict(self.current_stats),
            "cache_status": self.cache_status,
            "comparison_status": self.comparison_status,
            "has_changes": self.has_changes,
            "change_counts": self.change_counts(),
            "compared_against_explicit_hash": self.compared_against_explicit_hash,
            "prior_content_hash": self.prior_content_hash,
        }

    # ------------------------------------------------------------------
    # Full to_dict (Stage 3.4.0 baseline + Stage 3.5.0 additive fields)
    # ------------------------------------------------------------------

    def to_dict(self, *, include_full_diff: bool = False) -> Dict[str, Any]:
        """
        JSON-safe full report.

        Top-level keys (FROZEN by Stage 3.5.0 schema contract):
            pipeline_schema_version, result_status, completed_at,
            project_path, current, cache, comparison, derived, warnings

        Nested 'derived' block (Stage 3.5.0 addition):
            has_changes, change_counts, compared_against_explicit_hash
        """
        diff_summary: Optional[Dict[str, Any]] = None
        diff_warnings: Optional[List[str]] = None
        if self.diff_report is not None:
            diff_summary = dict(self.diff_report.summary)
            diff_warnings = list(self.diff_report.warnings)

        result: Dict[str, Any] = {
            "pipeline_schema_version": self.pipeline_schema_version,
            "result_status": self.result_status,
            "completed_at": self.completed_at,
            "project_path": self.project_path,
            "current": {
                "graph_id": self.current_graph_id,
                "build_id": self.current_build_id,
                "content_hash": self.current_content_hash,
                "stats": dict(self.current_stats),
            },
            "cache": {
                "enabled": self.cache_enabled,
                "status": self.cache_status,
                "cache_dir": self.cache_dir,
                "content_path": self.content_path,
            },
            "comparison": {
                "status": self.comparison_status,
                "prior_content_hash": self.prior_content_hash,
                "prior_build_id": self.prior_build_id,
                "diff_summary": diff_summary,
                "diff_warnings": diff_warnings,
            },
            "derived": {
                "has_changes": self.has_changes,
                "change_counts": self.change_counts(),
                "compared_against_explicit_hash":
                    self.compared_against_explicit_hash,
            },
            "warnings": list(self.warnings),
        }
        if include_full_diff and self.diff_report is not None:
            result["comparison"]["full_diff"] = self.diff_report.to_dict()
        return result


# =============================================================================
# Internal helpers
# =============================================================================

def _now_utc_iso() -> str:
    """Current UTC time as ISO 8601. Only place we read system time."""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# IncrementalPipeline
# =============================================================================

class IncrementalPipeline:
    """
    Thin orchestration layer for full-build + serialize + cache + diff.

    Always runs a full build via Orchestrator. Compares against prior
    cached build if available. Persists current build to cache (optional).

    Not thread-safe. Not asynchronous. One run() call per instance is the
    expected usage; instances may be reused across runs but state from a
    prior run does not affect a subsequent run.
    """

    def __init__(
        self,
        *,
        cache_dir: Optional[os.PathLike] = None,
        orchestrator: Optional[Orchestrator] = None,
        orchestrator_factory: Optional[Callable[[], Orchestrator]] = None,
    ) -> None:
        """
        Args:
            cache_dir: filesystem path for GraphCache. If None, pipeline
                runs in no-cache mode (no save, no comparison).
            orchestrator: pre-constructed Orchestrator. Mutually exclusive
                with orchestrator_factory.
            orchestrator_factory: callable returning a fresh Orchestrator.
                Used per run. If neither orchestrator nor factory given,
                default factory creates a vanilla Orchestrator().

        Raises:
            PipelineConfigurationError: if both orchestrator and
                orchestrator_factory are provided.
            CacheInitError: if cache_dir is provided but invalid.
        """
        if orchestrator is not None and orchestrator_factory is not None:
            raise PipelineConfigurationError(
                "IncrementalPipeline: provide either 'orchestrator' OR "
                "'orchestrator_factory', not both."
            )

        self._cache_dir: Optional[Path] = (
            Path(cache_dir) if cache_dir is not None else None
        )
        self._cache: Optional[GraphCache] = None
        if self._cache_dir is not None:
            # GraphCache constructor validates dir exists and is writable.
            self._cache = GraphCache(self._cache_dir)

        self._orchestrator: Optional[Orchestrator] = orchestrator
        self._orchestrator_factory: Optional[Callable[[], Orchestrator]] = (
            orchestrator_factory
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cache_enabled(self) -> bool:
        """True if cache_dir was provided at construction time."""
        return self._cache is not None

    @property
    def cache(self) -> Optional[GraphCache]:
        """Read-only access to underlying GraphCache (None if disabled)."""
        return self._cache

    def run(
        self,
        project_path: str,
        *,
        compare_against_content_hash: Optional[str] = None,
        skip_cache_save: bool = False,
    ) -> IncrementalRunReport:
        """
        Execute a full build, serialize, cache, and diff cycle.

        Args:
            project_path: forwarded to Orchestrator.run.
            compare_against_content_hash: if provided, diff against this
                specific cached content_hash instead of latest. If the
                entry doesn't exist, raises (caller named it explicitly).
            skip_cache_save: if True, don't persist current build.
                Comparison against prior is still performed if cache enabled.

        Returns:
            IncrementalRunReport describing the run.

        Raises:
            CacheMissError: only if compare_against_content_hash was
                provided and that entry doesn't exist.
            CacheError: subclasses propagate for explicit hash lookup or
                save failures.
            Any exception from Orchestrator.run or serialize_graph.
        """
        warnings_log: List[str] = []

        # --- Step 1: Build full graph via Orchestrator -------------------
        orch = self._resolve_orchestrator()
        graph = orch.run(project_path)

        # --- Step 2: Serialize current graph -----------------------------
        # serialize_graph requires finalized graph.version; Orchestrator
        # finalizes at end of run(). If serialization fails, the build
        # state is corrupt and exception propagates.
        current_payload = serialize_graph(graph)
        current_version = current_payload["version"]
        current_metadata = current_version["metadata"]
        current_content_hash = current_version["content_hash"]
        current_graph_id = current_metadata["graph_id"]
        current_build_id = current_metadata["build_id"]
        current_stats = dict(current_payload["stats"])

        # --- Step 3: Capture prior BEFORE save (P4) ----------------------
        prior_payload: Optional[Dict[str, Any]] = None
        prior_content_hash: Optional[str] = None
        prior_build_id: Optional[str] = None
        comparison_status: str
        diff_report: Optional[DiffReport] = None

        if not self.cache_enabled:
            comparison_status = COMPARISON_STATUS_DISABLED
        else:
            assert self._cache is not None  # for type-checker
            try:
                if compare_against_content_hash is not None:
                    # Explicit lookup — caller named this hash. Propagate
                    # errors; don't soft-handle.
                    prior_entry = self._cache.load_by_content_hash(
                        compare_against_content_hash
                    )
                else:
                    # Implicit latest lookup — soft-handle miss/corruption.
                    prior_entry = self._cache.load_latest(current_graph_id)
                prior_payload = prior_entry.payload
                prior_content_hash = prior_entry.content_hash
                prior_meta = prior_payload.get("version", {}).get("metadata", {})
                prior_build_id = prior_meta.get("build_id")
                comparison_status = COMPARISON_STATUS_COMPARED
            except CacheMissError as exc:
                if compare_against_content_hash is not None:
                    # Explicit hash request → propagate
                    raise
                comparison_status = COMPARISON_STATUS_NO_PRIOR
            except (CacheCorruptionError, CacheSchemaMismatchError) as exc:
                if compare_against_content_hash is not None:
                    raise
                comparison_status = COMPARISON_STATUS_PRIOR_CORRUPT
                warnings_log.append(
                    f"Prior cache entry was corrupt or schema-mismatched: {exc}"
                )

        # --- Step 4: Save current to cache -------------------------------
        cache_status: str
        content_path_str: Optional[str] = None
        if not self.cache_enabled:
            cache_status = CACHE_STATUS_DISABLED
        elif skip_cache_save:
            cache_status = CACHE_STATUS_SAVE_SKIPPED
        else:
            assert self._cache is not None
            # save may raise; we propagate because user provided cache_dir
            # which is an explicit opt-in.
            record: CacheRecord = self._cache.save(graph)
            content_path_str = str(record.content_path)
            cache_status = (
                CACHE_STATUS_DEDUPLICATED if record.deduplicated
                else CACHE_STATUS_SAVED
            )

        # --- Step 5: Compute diff if we have a prior payload -------------
        if prior_payload is not None:
            try:
                diff_report = diff_payloads(prior_payload, current_payload)
            except MalformedPayloadError as exc:
                # Cache returned an entry but its shape is malformed.
                # Soft-handle: downgrade to prior_corrupt.
                comparison_status = COMPARISON_STATUS_PRIOR_CORRUPT
                diff_report = None
                prior_content_hash = None
                prior_build_id = None
                warnings_log.append(
                    f"Prior cache entry payload was malformed; "
                    f"diff aborted: {exc}"
                )

        # --- Step 6: Assemble report -------------------------------------
        return IncrementalRunReport(
            pipeline_schema_version=PIPELINE_SCHEMA_VERSION,
            completed_at=_now_utc_iso(),
            project_path=str(project_path),
            current_graph_id=current_graph_id,
            current_build_id=current_build_id,
            current_content_hash=current_content_hash,
            current_stats=current_stats,
            cache_enabled=self.cache_enabled,
            cache_status=cache_status,
            cache_dir=(str(self._cache_dir) if self._cache_dir else None),
            content_path=content_path_str,
            comparison_status=comparison_status,
            prior_content_hash=prior_content_hash,
            prior_build_id=prior_build_id,
            diff_report=diff_report,
            warnings=warnings_log,
            _explicit_compare_hash=compare_against_content_hash,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_orchestrator(self) -> Orchestrator:
        """Resolve the orchestrator instance for this run."""
        if self._orchestrator is not None:
            return self._orchestrator
        if self._orchestrator_factory is not None:
            return self._orchestrator_factory()
        return Orchestrator()


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    "IncrementalPipeline",
    "IncrementalRunReport",
    "PipelineError",
    "PipelineConfigurationError",
    "PIPELINE_SCHEMA_VERSION",
    "RESULT_STATUS_SUCCESS",
    "CACHE_STATUS_SAVED",
    "CACHE_STATUS_DEDUPLICATED",
    "CACHE_STATUS_DISABLED",
    "CACHE_STATUS_SAVE_SKIPPED",
    "COMPARISON_STATUS_NO_PRIOR",
    "COMPARISON_STATUS_PRIOR_CORRUPT",
    "COMPARISON_STATUS_COMPARED",
    "COMPARISON_STATUS_DISABLED",
]