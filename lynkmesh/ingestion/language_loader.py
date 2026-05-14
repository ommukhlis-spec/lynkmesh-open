"""
Language Loader – wraps legacy parsers behind a uniform interface.
"""
import sys
import os
import importlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Protocol, Type

from lynkmesh.config import get_parser_path, get_legacy_lynkmesh_path

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
class LanguageParser(Protocol):
    @property
    def parallel_available(self) -> bool: ...
    def parse_parallel(self, project_path: str, files: List[str], max_workers: int) -> Optional[List[Dict[str, Any]]]: ...
    def parse_fallback(self, project_path: str) -> List[Dict[str, Any]]: ...

# ------------------------------------------------------------------
class PHPLegacyParserAdapter:
    """
    Adapter for PHP parsing using legacy ParallelParser and IREngine.
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

    def _bootstrap(self):
        if self._bootstrapped:
            return

        legacy_root = get_legacy_lynkmesh_path()
        self._legacy_root_str = str(legacy_root)

        # Add legacy root to sys.path permanently (main process) so
        # 'import core.parallel_parser' and 'import ir_engine' work.
        if self._legacy_root_str not in sys.path:
            sys.path.insert(0, self._legacy_root_str)

        parser_script = str(get_parser_path())
        logger.info(f"[PHPLegacyAdapter] Parser path: {parser_script}")
        logger.info(f"[PHPLegacyAdapter] Parser exists: {Path(parser_script).exists()}")

        # Import with original names (no 'legacy_' prefix)
        import core.parallel_parser as pp_mod
        import ir_engine as ie_mod

        # Monkey-patch PARSER_SCRIPT and _resolve_parser_path
        pp_mod.PARSER_SCRIPT = parser_script
        def patched_resolve_parser_path(self):
            return Path(parser_script)
        ie_mod.IREngine._resolve_parser_path = patched_resolve_parser_path

        self._parallel_parser_class = pp_mod.ParallelParser
        self._ir_engine_class = ie_mod.IREngine
        self._ir_build_error_class = ie_mod.IRBuildError

        self._bootstrapped = True

    @property
    def parallel_available(self) -> bool:
        return True

    def _ensure_legacy_pythonpath(self):
        """Temporarily add legacy root to PYTHONPATH so spawned workers inherit it."""
        current = os.environ.get('PYTHONPATH', '')
        if self._legacy_root_str not in current:
            os.environ['PYTHONPATH'] = self._legacy_root_str + os.pathsep + current
            return True  # we modified it
        return False

    def _restore_pythonpath(self, modified: bool):
        if modified:
            # revert to previous value (simple approach: remove from beginning)
            parts = os.environ.get('PYTHONPATH', '').split(os.pathsep)
            if parts and parts[0] == self._legacy_root_str:
                os.environ['PYTHONPATH'] = os.pathsep.join(parts[1:])
            # else leave as is (safety)

    def parse_parallel(self, project_path: str, files: List[str], max_workers: int = 4) -> Optional[List[Dict[str, Any]]]:
        self._bootstrap()
        path_modified = self._ensure_legacy_pythonpath()
        try:
            parser = self._parallel_parser_class(
                parser_script=str(get_parser_path()),
                max_workers=max_workers
            )
            ast = parser.run(project_path, files)
            if isinstance(ast, list):
                return ast
        except Exception as e:
            logger.error(f"[PHPLegacyAdapter] Parallel parser error: {e}")
        finally:
            if path_modified:
                self._restore_pythonpath(path_modified)
        return None

    def parse_fallback(self, project_path: str) -> List[Dict[str, Any]]:
        self._bootstrap()
        # Fallback usually runs in single process, but set PYTHONPATH anyway for safety
        path_modified = self._ensure_legacy_pythonpath()
        try:
            engine = self._ir_engine_class()
            ast = engine.parse(project_path)
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