"""
Parser Engine – Central ingestion orchestrator.
Delegates to language-specific adapters loaded via LanguageLoader.
"""

import logging
from typing import List, Dict, Any

from .file_scanner import FileScanner
from .language_loader import LanguageLoader

logger = logging.getLogger(__name__)


class ParserEngine:
    """
    Single entry point for parsing a codebase into raw AST (IR) data.

    Strategy (per language adapter):
        1. Parallel parsing (preferred)
        2. Fallback to legacy IREngine
    """

    def __init__(self, language: str = "php", max_workers: int = 4):
        self.language = language
        self.max_workers = max_workers
        self.loader = LanguageLoader()

    def parse(self, project_path: str) -> List[Dict[str, Any]]:
        logger.info("[ParserEngine] Starting ingestion pipeline")
        adapter = self.loader.load(self.language)

        files = self._scan_files(project_path)
        if not files:
            logger.warning("[ParserEngine] No files found to parse")
            return []

        # Attempt parallel, then fallback
        if adapter.parallel_available:
            ast = adapter.parse_parallel(
                project_path,
                files,
                max_workers=self.max_workers
            )
            if ast is not None:
                logger.info(
                    f"[ParserEngine] Parallel parsing succeeded: {len(ast)}/{len(files)} files"
                )
                return ast
            logger.warning("[ParserEngine] Parallel parsing failed, falling back to legacy")

        return adapter.parse_fallback(project_path)

    def _scan_files(self, project_path: str) -> List[str]:
        scanner = FileScanner()
        return scanner.scan(project_path)