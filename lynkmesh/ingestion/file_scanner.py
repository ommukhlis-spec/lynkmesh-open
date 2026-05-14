# lynkmesh/ingestion/file_scanner.py
"""
File Scanner - Recursive file discovery with filtering.
Production-grade, minimal dependencies.
"""

import os
from pathlib import Path
from typing import List, Set, Optional
import logging

logger = logging.getLogger(__name__)

# Directories to always ignore
DEFAULT_IGNORE_DIRS = {
    "vendor",
    "node_modules",
    ".git",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "storage",
    "bootstrap/cache",
}


class FileScanner:
    """
    Recursively scans a project directory for files with specific extensions.
    """

    def __init__(
        self,
        allowed_extensions: Optional[Set[str]] = None,
        ignore_dirs: Optional[Set[str]] = None,
    ):
        self.allowed_extensions = allowed_extensions or {".php"}
        self.ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS

    def scan(self, project_path: str) -> List[str]:
        """
        Scan project directory and return list of absolute file paths.
        """
        project_path = Path(project_path).resolve()
        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")

        logger.info(f"[Scanner] Scanning: {project_path}")
        files = []

        for root, dirs, filenames in os.walk(project_path):
            # Filter ignored directories using relative path
            dirs[:] = [
                d for d in dirs
                if not self._should_ignore(os.path.join(root, d))
            ]

            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self.allowed_extensions:
                    continue
                full_path = os.path.join(root, filename)
                files.append(str(Path(full_path).resolve()))

        logger.info(f"[Scanner] Found {len(files)} files")
        return files

    def _should_ignore(self, path: str) -> bool:
        """Check if a directory path should be ignored."""
        normalized = path.replace("\\", "/")
        for ignore in self.ignore_dirs:
            # Simple substring match works for nested dirs like "bootstrap/cache"
            if ignore in normalized:
                return True
        return False