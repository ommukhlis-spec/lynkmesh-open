"""
Parser Engine – Central ingestion orchestrator.
Delegates to language-specific adapters loaded via LanguageLoader.
"""

import logging
import time
from contextlib import contextmanager
from typing import List, Dict, Any, Callable, Optional

from .file_scanner import FileScanner
from .language_loader import LanguageLoader

logger = logging.getLogger(__name__)

# Stage 4.2.4 – callback type for internal sub‑phase timing
PhaseCallback = Callable[[str, str, float], None]


class ParserEngine:
    """
    Single entry point for parsing a codebase into raw AST (IR) data.

    Strategy (per language adapter):
        1. Parallel parsing (preferred)
        2. Fallback to legacy IREngine
    """

    def __init__(
        self,
        language: str = "php",
        max_workers: int = 4,
        *,
        on_phase: Optional[PhaseCallback] = None,
    ):
        self.language = language
        self.max_workers = max_workers
        self.loader = LanguageLoader()
        self._on_phase = on_phase
        self._phase_timings: Dict[str, float] = {}
        self._last_parser_diagnostics: Optional[Dict[str, Any]] = None

    @property
    def last_parser_diagnostics(self) -> Optional[Dict[str, Any]]:
        """Return the diagnostics captured from the most recent adapter parse, if any."""
        return self._last_parser_diagnostics

    def set_phase_callback(self, on_phase: Optional[PhaseCallback]) -> None:
        """Attach or clear the phase callback used during the next parse."""
        self._on_phase = on_phase

    def parse(self, project_path: str) -> List[Dict[str, Any]]:
        logger.info("[ParserEngine] Starting ingestion pipeline")

        # Reset per‑run timings
        self._phase_timings = {}
        self._last_parser_diagnostics = None

        with self._phase("load_adapter"):
            adapter = self.loader.load(self.language)

        with self._phase("scan_files"):
            files = self._scan_files(project_path)
            if not files:
                logger.warning("[ParserEngine] No files found to parse")
                return []

        # Attempt parallel, then fallback
        if adapter.parallel_available:
            # Forward/clear callback on adapter
            if hasattr(adapter, "set_phase_callback"):
                adapter.set_phase_callback(self._make_adapter_callback())
            with self._phase("parse_parallel"):
                ast = adapter.parse_parallel(
                    project_path,
                    files,
                    max_workers=self.max_workers
                )
            self._last_parser_diagnostics = getattr(adapter, "last_parser_diagnostics", None)
            if ast is not None:
                logger.info(
                    f"[ParserEngine] Parallel parsing succeeded: {len(ast)}/{len(files)} files"
                )
                return ast
            logger.warning("[ParserEngine] Parallel parsing failed, falling back to legacy")

        # Fallback
        if hasattr(adapter, "set_phase_callback"):
            adapter.set_phase_callback(self._make_adapter_callback())
        with self._phase("parse_fallback"):
            fallback_result = adapter.parse_fallback(project_path)
        self._last_parser_diagnostics = getattr(adapter, "last_parser_diagnostics", None)
        return fallback_result

    def _scan_files(self, project_path: str) -> List[str]:
        scanner = FileScanner()
        return scanner.scan(project_path)

    # ------------------------------------------------------------------
    # Phase diagnostics helpers (Stage 4.2.4)
    # ------------------------------------------------------------------
    def _safe_emit_phase(self, name: str, event: str, elapsed: float) -> None:
        """Call the on_phase callback if set, swallowing any exceptions."""
        if self._on_phase is None:
            return
        try:
            self._on_phase(name, event, elapsed)
        except Exception:
            pass

    @staticmethod
    def _sanitize_phase_elapsed(elapsed: float) -> float:
        """Return a safe float duration, clamping invalid values to 0.0."""
        try:
            val = float(elapsed)
            if val < 0.0 or val != val or val == float("inf") or val == float("-inf"):
                return 0.0
            return val
        except (ValueError, TypeError):
            return 0.0

    @contextmanager
    def _phase(self, name: str):
        """Context manager that records timing for a named phase."""
        start = time.perf_counter()
        self._safe_emit_phase(name, "start", 0.0)
        try:
            yield
        finally:
            end = time.perf_counter()
            elapsed = self._sanitize_phase_elapsed(end - start)
            self._phase_timings[name] = self._phase_timings.get(name, 0.0) + elapsed
            self._safe_emit_phase(name, "end", elapsed)

    def _make_adapter_callback(self) -> Optional[PhaseCallback]:
        """Create a callback that prefixes adapter sub‑phase names with 'parse_parallel.'"""
        parent = self._on_phase
        if parent is None:
            return None

        def cb(name: str, event: str, elapsed: float) -> None:
            try:
                parent(f"parse_parallel.{name}", event, elapsed)
            except Exception:
                pass

        return cb