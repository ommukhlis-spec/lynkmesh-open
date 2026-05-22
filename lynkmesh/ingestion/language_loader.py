"""
Language Loader – wraps legacy parsers behind a uniform interface.
Stage 4.2.5.5C – Prefers internal PHP bridge, legacy is fallback.
"""
import sys
import os
import importlib
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional, Protocol, Type, Callable

from lynkmesh.config import (
    get_parser_path,
    get_legacy_lynkmesh_path,
    resolve_parser_path,
)

logger = logging.getLogger(__name__)

# Stage 4.2.4 – callback type for adapter sub‑phase timing
PhaseCallback = Callable[[str, str, float], None]

# ------------------------------------------------------------------
class LanguageParser(Protocol):
    @property
    def parallel_available(self) -> bool: ...
    def parse_parallel(self, project_path: str, files: List[str], max_workers: int) -> Optional[List[Dict[str, Any]]]: ...
    def parse_fallback(self, project_path: str) -> List[Dict[str, Any]]: ...

# ------------------------------------------------------------------
class PHPLegacyParserAdapter:
    """
    Adapter for PHP parsing using internal ParallelParser (preferred)
    or legacy ParallelParser / IREngine (fallback).

    Ensures legacy modules are importable under their original names
    (e.g., 'core.parallel_parser', 'ir_engine') so multiprocessing workers
    can reload them correctly.
    """
    def __init__(self):
        self._parallel_parser_class = None
        self._ir_engine_class = None
        self._ir_build_error_class = None
        self._bootstrapped = False
        self._legacy_root_str: str = ""
        self._on_phase: Optional[PhaseCallback] = None
        self._phase_timings: Dict[str, float] = {}
        self._last_parser_diagnostics: Optional[Dict[str, Any]] = None
        self._parser_resolution: Optional[Dict[str, Any]] = None
        self._parser_path: Optional[Path] = None
        self._parallel_parser_source: Optional[str] = None

    @property
    def last_parser_diagnostics(self) -> Optional[Dict[str, Any]]:
        """Return the diagnostics captured from the most recent legacy parse run, if any."""
        return self._last_parser_diagnostics

    def set_phase_callback(self, on_phase: Optional[PhaseCallback]) -> None:
        """Attach or clear the phase callback used during the next parse call."""
        self._on_phase = on_phase

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

    def _enrich_parser_diagnostics(self, diagnostics):
        if not isinstance(diagnostics, dict):
            return diagnostics

        enriched = dict(diagnostics)

        if isinstance(self._parser_resolution, dict):
            source = self._parser_resolution.get("source")
            if source is not None:
                enriched["parser_source"] = source
            enriched["parser_resolution"] = dict(self._parser_resolution)

        if self._parallel_parser_source is not None:
            enriched["parallel_parser_source"] = self._parallel_parser_source

        return enriched

    def _bootstrap(self):
        if self._bootstrapped:
            return

        parser_path, parser_resolution = resolve_parser_path()
        self._parser_resolution = parser_resolution
        self._parser_path = parser_path

        if parser_path is None:
            # Preserve old public error behavior via get_parser_path().
            parser_path = get_parser_path()
            self._parser_path = parser_path

        parser_script = str(parser_path)
        logger.info(f"[PHPLegacyAdapter] Parser path: {parser_script}")
        logger.info(f"[PHPLegacyAdapter] Parser exists: {Path(parser_script).exists()}")

        # Prefer internal bridge
        try:
            from lynkmesh.ingestion.php_bridge.parallel_parser import ParallelParser

            self._parallel_parser_class = ParallelParser
            self._parallel_parser_source = "internal_bundle"
            self._bootstrapped = True
            logger.info("[PHPLegacyAdapter] Using internal PHP bridge ParallelParser")
            return
        except Exception as e:
            logger.warning(
                "[PHPLegacyAdapter] Internal PHP bridge import failed; "
                "falling back to legacy runtime: %s",
                e,
            )

        # Fallback to legacy runtime
        legacy_root = get_legacy_lynkmesh_path()
        self._legacy_root_str = str(legacy_root)

        if self._legacy_root_str not in sys.path:
            sys.path.insert(0, self._legacy_root_str)

        import core.parallel_parser as pp_mod
        import ir_engine as ie_mod

        pp_mod.PARSER_SCRIPT = parser_script

        def patched_resolve_parser_path(self):
            return Path(parser_script)

        ie_mod.IREngine._resolve_parser_path = patched_resolve_parser_path

        self._parallel_parser_class = pp_mod.ParallelParser
        self._ir_engine_class = ie_mod.IREngine
        self._ir_build_error_class = ie_mod.IRBuildError
        self._parallel_parser_source = "legacy_root_fallback"

        self._bootstrapped = True

    @property
    def parallel_available(self) -> bool:
        return True

    def _ensure_legacy_pythonpath(self):
        """Temporarily add legacy root to PYTHONPATH so spawned workers inherit it.
        Only needed when using legacy runtime (not internal bridge)."""
        if self._parallel_parser_source != "legacy_root_fallback":
            return False
        current = os.environ.get('PYTHONPATH', '')
        if self._legacy_root_str not in current:
            os.environ['PYTHONPATH'] = self._legacy_root_str + os.pathsep + current
            return True  # we modified it
        return False

    def _restore_pythonpath(self, modified: bool):
        if not modified or self._parallel_parser_source != "legacy_root_fallback":
            return
        # revert to previous value (simple approach: remove from beginning)
        parts = os.environ.get('PYTHONPATH', '').split(os.pathsep)
        if parts and parts[0] == self._legacy_root_str:
            os.environ['PYTHONPATH'] = os.pathsep.join(parts[1:])
        # else leave as is (safety)

    def parse_parallel(self, project_path: str, files: List[str], max_workers: int = 4) -> Optional[List[Dict[str, Any]]]:
        self._phase_timings = {}
        self._last_parser_diagnostics = None
        with self._phase("bootstrap"):
            self._bootstrap()
        path_modified = self._ensure_legacy_pythonpath()
        try:
            parser = self._parallel_parser_class(
                parser_script=str(self._parser_path or get_parser_path()),
                max_workers=max_workers
            )
            with self._phase("legacy_parallel_run"):
                ast = parser.run(project_path, files)
            self._last_parser_diagnostics = self._enrich_parser_diagnostics(
                getattr(parser, "last_diagnostics", None)
            )
            if isinstance(ast, list):
                return ast
        except Exception as e:
            logger.error(f"[PHPLegacyAdapter] Parallel parser error: {e}")
        finally:
            if path_modified:
                self._restore_pythonpath(path_modified)
        return None

    def parse_fallback(self, project_path: str) -> List[Dict[str, Any]]:
        self._phase_timings = {}
        self._last_parser_diagnostics = None
        with self._phase("bootstrap"):
            self._bootstrap()

        # Ensure legacy fallback classes are loaded if internal bridge was chosen
        if self._ir_engine_class is None or self._ir_build_error_class is None:
            try:
                legacy_root = get_legacy_lynkmesh_path()
                self._legacy_root_str = str(legacy_root)
                if self._legacy_root_str not in sys.path:
                    sys.path.insert(0, self._legacy_root_str)

                parser_script = str(self._parser_path or get_parser_path())
                import ir_engine as ie_mod

                def patched_resolve_parser_path(self):
                    return Path(parser_script)

                ie_mod.IREngine._resolve_parser_path = patched_resolve_parser_path

                self._ir_engine_class = ie_mod.IREngine
                self._ir_build_error_class = ie_mod.IRBuildError
            except Exception as e:
                logger.error(f"[PHPLegacyAdapter] Legacy fallback unavailable: {e}")
                return []

        # Fallback usually runs in single process, but set PYTHONPATH anyway for safety
        path_modified = self._ensure_legacy_pythonpath()
        try:
            engine = self._ir_engine_class()
            with self._phase("legacy_fallback_run"):
                ast = engine.parse(project_path)
            self._last_parser_diagnostics = self._enrich_parser_diagnostics(
                getattr(engine, "last_diagnostics", None)
            )
            if isinstance(ast, list):
                logger.info(f"[PHPLegacyAdapter] Fallback succeeded: {len(ast)} files")
                return ast
        except self._ir_build_error_class as e:
            logger.error(f"[PHPLegacyAdapter] IRBuildError: {e}")
        except Exception as e:
            logger.exception(f"[PHPLegacyAdapter] Unexpected fallback error: {e}")
        finally:
            if path_modified:
                self._restore_pythonpath(path_modified)
        return []

# ------------------------------------------------------------------
class LanguageLoader:
    REGISTRY: Dict[str, Type[LanguageParser]] = {
        "php": PHPLegacyParserAdapter,
    }

    def __init__(self):
        self._instances: Dict[str, LanguageParser] = {}

    def load(self, language: str = "php") -> LanguageParser:
        if language not in self.REGISTRY:
            raise ValueError(f"No parser adapter for language: {language}")
        if language not in self._instances:
            self._instances[language] = self.REGISTRY[language]()
        return self._instances[language]