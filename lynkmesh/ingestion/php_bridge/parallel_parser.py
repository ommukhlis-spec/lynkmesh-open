# lynkmesh/legacy/core/parallel_parser.py
"""
Parallel parser for PHP files using external PHP script.
V3.4 – Windows‑safe default executor (thread) with explicit override.
"""

import os
import sys
import json
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================================
# DEPRECATED: only kept for backward compatibility
# ============================================================
PARSER_SCRIPT = None


# ============================================================
# Helper: diagnostic envelope factory
# ============================================================
def _result_envelope(
    file_path: str,
    *,
    status: str,
    ir: Optional[Dict[str, Any]] = None,
    duration_seconds: float = 0.0,
    error_type: Optional[str] = None,
    returncode: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "file_path": file_path,
        "ir": ir,
        "status": status,
        "duration_seconds": float(duration_seconds) if duration_seconds >= 0 else 0.0,
        "error_type": error_type,
        "returncode": returncode,
    }


# ============================================================
# Stdio tail helpers (Stage 4.2.5.3)
# ============================================================
_STDERR_TAIL_MAX_CHARS = 500
_STDOUT_TAIL_MAX_CHARS = 500


def _tail_string(s, max_chars: int) -> Optional[str]:
    """Return the tail of a string, clamped to max_chars, or None if empty."""
    if s is None:
        return None
    if isinstance(s, bytes):
        try:
            s = s.decode("utf-8", errors="replace")
        except Exception:
            return None
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return None
    if not s.strip():
        return None
    return s if len(s) <= max_chars else s[-max_chars:]


def _build_subprocess_diag(
    *,
    cmd,
    timeout: int,
    stdout=None,
    stderr=None,
    include_stdout_tail: bool = False,
) -> Dict[str, Any]:
    """Build a bounded diagnostic dict for a single subprocess invocation."""
    php_command = None
    if cmd and len(cmd) > 0:
        php_command = os.path.basename(str(cmd[0]))
    diag: Dict[str, Any] = {
        "timeout_seconds": timeout,
        "cwd_basename": os.path.basename(os.getcwd()) or None,
        "php_command": php_command,
        "cmd_arg_count": len(cmd) if cmd is not None else 0,
        "stderr_tail": _tail_string(stderr, _STDERR_TAIL_MAX_CHARS),
    }
    if include_stdout_tail:
        diag["stdout_tail"] = _tail_string(stdout, _STDOUT_TAIL_MAX_CHARS)
    return diag


# ============================================================
# Helper: run parser on a single file
# ============================================================
def parse_one_file(file_path: str, parser_script: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Run parser.php on a single file and return a diagnostic envelope.

    Returns:
        dict with keys: file_path, ir, status, duration_seconds, error_type, returncode
        On error/timeout also includes: timeout_seconds, cwd_basename, php_command,
        cmd_arg_count, stderr_tail, stdout_tail
    """
    if not parser_script or not os.path.exists(parser_script):
        logger.debug(f"Parser script missing: {parser_script}")
        env = _result_envelope(file_path, status="missing_parser", error_type="missing_parser")
        env.update(_build_subprocess_diag(cmd=[], timeout=timeout))
        return env

    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        env = _result_envelope(file_path, status="missing_file", error_type="missing_file")
        env.update(_build_subprocess_diag(cmd=[], timeout=timeout))
        return env

    cmd = ['php', parser_script, file_path, '--minify']
    start = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            encoding='utf-8',
        )
        elapsed = time.perf_counter() - start
        returncode = result.returncode

        if result.returncode != 0:
            logger.error(f"Parser error for {file_path}: {result.stderr[:500] if result.stderr else 'N/A'}")
            env = _result_envelope(file_path, status="nonzero_exit", duration_seconds=elapsed,
                                    error_type="nonzero_exit", returncode=returncode)
            env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout,
                                               stderr=result.stderr, stdout=result.stdout,
                                               include_stdout_tail=True))
            return env

        stdout = result.stdout.strip()
        if not stdout:
            logger.warning(f"Empty output from parser for {file_path}")
            env = _result_envelope(file_path, status="empty_output", duration_seconds=elapsed,
                                    error_type="empty_output", returncode=returncode)
            env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout,
                                               stderr=result.stderr, stdout=result.stdout,
                                               include_stdout_tail=True))
            return env

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {file_path}: {e}")
            logger.debug(f"Raw output: {stdout[:500]}")
            env = _result_envelope(file_path, status="json_error", duration_seconds=elapsed,
                                    error_type="json_error", returncode=returncode)
            env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout,
                                               stderr=result.stderr, stdout=stdout,
                                               include_stdout_tail=True))
            return env

        if isinstance(data, list):
            if len(data) == 0:
                env = _result_envelope(file_path, status="empty_output", duration_seconds=elapsed,
                                        error_type="empty_output", returncode=returncode)
                env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout,
                                                   stderr=result.stderr, stdout=result.stdout,
                                                   include_stdout_tail=True))
                return env
            ir = data[0]
        else:
            ir = data

        env = _result_envelope(file_path, status="ok", ir=ir, duration_seconds=elapsed,
                                returncode=returncode)
        # On success, include stderr_tail only if non-empty
        stderr_tail = _tail_string(result.stderr, _STDERR_TAIL_MAX_CHARS)
        if stderr_tail:
            env.update({"stderr_tail": stderr_tail})
        # Always include subprocess metadata for ok entries
        env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout,
                                           stderr=result.stderr,
                                           include_stdout_tail=False))
        return env

    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start
        logger.error(f"Timeout parsing {file_path}")
        stdout_str = _tail_string(exc.stdout if hasattr(exc, 'stdout') else None, _STDOUT_TAIL_MAX_CHARS)
        stderr_str = _tail_string(exc.stderr if hasattr(exc, 'stderr') else None, _STDERR_TAIL_MAX_CHARS)
        env = _result_envelope(file_path, status="timeout", duration_seconds=elapsed,
                                error_type="timeout")
        env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout,
                                           stdout=stdout_str, stderr=stderr_str,
                                           include_stdout_tail=True))
        return env
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error(f"Unexpected error parsing {file_path}: {e}")
        env = _result_envelope(file_path, status="unexpected_error", duration_seconds=elapsed,
                                error_type="unexpected_error")
        env.update(_build_subprocess_diag(cmd=cmd, timeout=timeout))
        return env


# ============================================================
# Main parallel parser
# ============================================================

# Executor strategy env vars
_EXECUTOR_ENV_VAR = "LYNKMESH_PARSER_EXECUTOR"
_LEGACY_EXECUTOR_ENV_VAR = "LYNKMESH_LEGACY_PARSER_EXECUTOR"

_EXECUTOR_MODE_PROCESS = "process"
_EXECUTOR_MODE_THREAD = "thread"

_EXECUTOR_SOURCE_ENV_OVERRIDE = "env_override"
_EXECUTOR_SOURCE_LEGACY_ENV_OVERRIDE = "legacy_env_override"
_EXECUTOR_SOURCE_PLATFORM_DEFAULT_WIN = "platform_default_windows"
_EXECUTOR_SOURCE_PLATFORM_DEFAULT_NON_WIN = "platform_default_non_windows"
_EXECUTOR_SOURCE_AFTER_INVALID_ENV = "platform_default_after_invalid_env"


def _platform_default_executor():
    """Return the default executor mode and class for the current platform."""
    if sys.platform == "win32":
        return _EXECUTOR_MODE_THREAD, ThreadPoolExecutor
    return _EXECUTOR_MODE_PROCESS, ProcessPoolExecutor


def _resolve_executor_strategy():
    """
    Determine which concurrent executor to use.

    Returns:
        (executor_mode, executor_class, invalid_value, source)
    """
    raw = os.environ.get(_EXECUTOR_ENV_VAR)
    source = _EXECUTOR_SOURCE_ENV_OVERRIDE
    active_env_var = _EXECUTOR_ENV_VAR

    if raw is None or not raw.strip():
        legacy_raw = os.environ.get(_LEGACY_EXECUTOR_ENV_VAR)
        if legacy_raw is not None and legacy_raw.strip():
            raw = legacy_raw
            source = _EXECUTOR_SOURCE_LEGACY_ENV_OVERRIDE
            active_env_var = _LEGACY_EXECUTOR_ENV_VAR

    if raw is None or not raw.strip():
        # Platform default
        mode, cls = _platform_default_executor()
        source = _EXECUTOR_SOURCE_PLATFORM_DEFAULT_WIN if mode == _EXECUTOR_MODE_THREAD else _EXECUTOR_SOURCE_PLATFORM_DEFAULT_NON_WIN
        return mode, cls, None, source

    normalized = raw.strip().lower()
    if normalized == _EXECUTOR_MODE_THREAD:
        return _EXECUTOR_MODE_THREAD, ThreadPoolExecutor, None, source
    if normalized == _EXECUTOR_MODE_PROCESS:
        return _EXECUTOR_MODE_PROCESS, ProcessPoolExecutor, None, source

    logger.warning(
        "Unrecognised %s value %r; falling back to platform default",
        active_env_var, raw,
    )
    mode, cls = _platform_default_executor()
    return mode, cls, raw, _EXECUTOR_SOURCE_AFTER_INVALID_ENV


class ParallelParser:
    def __init__(self, parser_script: str, max_workers: int = 4):
        """
        Args:
            parser_script: Absolute path to parser.php
            max_workers: Number of parallel workers
        """
        self.max_workers = max_workers
        self.parser_script = parser_script
        self.last_diagnostics: Dict[str, Any] = {}
        self._last_parse_envelopes: List[Dict[str, Any]] = []

        if not self.parser_script or not os.path.exists(self.parser_script):
            raise RuntimeError(f"Parser script not found at {self.parser_script}")

    @staticmethod
    def _sanitize_diag_path(file_path: str, project_path: Optional[str]) -> str:
        if project_path:
            try:
                rel = os.path.relpath(file_path, project_path)
                if not rel.startswith(".."):
                    return rel.replace("\\", "/")
            except (ValueError, OSError):
                pass
        return os.path.basename(file_path)

    def _build_diagnostics(
        self,
        *,
        project_path: Optional[str],
        file_paths: List[str],
        envelopes: List[Dict[str, Any]],
        duration_seconds: float,
        executor_mode: Optional[str] = None,
        executor_class: Optional[str] = None,
        executor_invalid_value: Optional[str] = None,
        executor_mode_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        succeeded = 0
        timeout = 0
        json_err = 0
        empty = 0
        nonzero = 0
        missing_parser = 0
        missing_file = 0
        unexpected = 0
        total_subprocess_sec = 0.0
        slowest: List[Dict[str, Any]] = []

        for env in envelopes:
            status = env.get("status", "unexpected_error")
            dur = float(env.get("duration_seconds", 0.0))
            total_subprocess_sec += dur
            if status == "ok":
                succeeded += 1
            elif status == "timeout":
                timeout += 1
            elif status == "json_error":
                json_err += 1
            elif status == "empty_output":
                empty += 1
            elif status == "nonzero_exit":
                nonzero += 1
            elif status == "missing_parser":
                missing_parser += 1
            elif status == "missing_file":
                missing_file += 1
            elif status == "unexpected_error":
                unexpected += 1
            # else future_error etc.
            entry = {
                "file_path": env.get("file_path", ""),
                "seconds": dur,
                "status": status,
            }
            # Carry forward selected diagnostic keys into slowest entries
            for key in (
                "error_type",
                "timeout_seconds",
                "stderr_tail",
                "stdout_tail",
                "cwd_basename",
                "php_command",
                "cmd_arg_count",
            ):
                if key in env and env[key] is not None:
                    entry[key] = env[key]
            slowest.append(entry)

        # Sort slowest descending and keep top 10
        slowest.sort(key=lambda x: x["seconds"], reverse=True)
        top10 = []
        for entry in slowest[:10]:
            item = {
                "file": self._sanitize_diag_path(entry.pop("file_path"), project_path),
                "seconds": entry.pop("seconds"),
                "status": entry.pop("status"),
            }
            # Include remaining diagnostic keys if present
            for k, v in entry.items():
                if v is not None:
                    item[k] = v
            top10.append(item)

        file_count = len(file_paths)
        failed = file_count - succeeded
        avg = total_subprocess_sec / file_count if file_count else 0.0

        diag: Dict[str, Any] = {
            "file_count": file_count,
            "max_workers": self.max_workers,
            "duration_seconds": max(duration_seconds, 0.0),
            "subprocess_count": file_count,
            "succeeded_count": succeeded,
            "failed_count": failed,
            "timeout_count": timeout,
            "json_error_count": json_err,
            "empty_output_count": empty,
            "nonzero_exit_count": nonzero,
            "missing_parser_count": missing_parser,
            "missing_file_count": missing_file,
            "unexpected_error_count": unexpected,
            "total_subprocess_seconds": total_subprocess_sec,
            "avg_file_seconds": avg,
            "slowest_files": top10,
        }

        if executor_mode is not None:
            diag["executor_mode"] = executor_mode
        if executor_class is not None:
            diag["executor_class"] = executor_class
        if executor_invalid_value is not None:
            diag["executor_invalid_value"] = executor_invalid_value
        if executor_mode_source is not None:
            diag["executor_mode_source"] = executor_mode_source

        return diag

    def parse_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Parse multiple files in parallel.
        Returns a dict mapping file_path -> IR dict.
        """
        results: Dict[str, Any] = {}
        self._last_parse_envelopes = []
        self.last_diagnostics = {}

        if not file_paths:
            return results

        logger.debug(f"Parsing {len(file_paths)} files with {self.max_workers} workers")
        logger.debug(f"Parser script: {self.parser_script}")

        # Resolve executor strategy
        executor_mode, executor_cls, executor_invalid_value, executor_source = _resolve_executor_strategy()
        self._stage_4_2_5_2_executor_mode = executor_mode
        self._stage_4_2_5_2_executor_class = executor_cls.__name__
        self._stage_4_2_5_2_executor_invalid_value = executor_invalid_value
        self._stage_4_2_5_4_executor_source = executor_source

        start_time = time.perf_counter()
        envelopes: List[Dict[str, Any]] = []

        with executor_cls(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(parse_one_file, fp, self.parser_script): fp
                for fp in file_paths
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    envelope = future.result()
                except Exception as e:
                    logger.error(f"Exception fetching future for {file_path}: {e}")
                    envelope = _result_envelope(file_path, status="future_error",
                                                error_type="future_error")
                envelopes.append(envelope)

                if envelope.get("status") == "ok" and envelope.get("ir") is not None:
                    results[file_path] = envelope["ir"]
                else:
                    logger.warning(f"Failed to parse {file_path}")

        self._last_parse_envelopes = envelopes
        self.last_diagnostics = self._build_diagnostics(
            project_path=None,
            file_paths=file_paths,
            envelopes=envelopes,
            duration_seconds=time.perf_counter() - start_time,
            executor_mode=executor_mode,
            executor_class=executor_cls.__name__,
            executor_invalid_value=executor_invalid_value,
            executor_mode_source=executor_source,
        )
        return results

    def run(self, project_path: str, files: List[str]) -> List[Dict[str, Any]]:
        """
        Compatibility method expected by analysis_pipeline.
        Returns list of IR dictionaries.
        """
        result_map = self.parse_files(files)

        # Rebuild diagnostics with project_path for relative paths
        if self.last_diagnostics and self._last_parse_envelopes:
            self.last_diagnostics = self._build_diagnostics(
                project_path=project_path,
                file_paths=files,
                envelopes=self._last_parse_envelopes,
                duration_seconds=self.last_diagnostics.get("duration_seconds", 0.0),
                executor_mode=self.last_diagnostics.get("executor_mode"),
                executor_class=self.last_diagnostics.get("executor_class"),
                executor_invalid_value=self.last_diagnostics.get("executor_invalid_value"),
                executor_mode_source=self.last_diagnostics.get("executor_mode_source"),
            )

        ir_list = list(result_map.values())
        logger.info(f"Successfully parsed {len(ir_list)} out of {len(files)} files")
        if ir_list:
            sample = ir_list[0]
            logger.debug(f"Sample IR keys: {sample.keys()}")
            logger.debug(f"Sample classes: {len(sample.get('classes', []))}")
        return ir_list


# ============================================================
# For direct testing
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) < 2:
        print("Usage: python parallel_parser.py <directory_or_file>")
        sys.exit(1)
    path = sys.argv[1]

    # Collect files
    if os.path.isdir(path):
        files = []
        for root, dirs, names in os.walk(path):
            if 'vendor' in dirs:
                dirs.remove('vendor')
            for name in names:
                if name.endswith('.php'):
                    files.append(os.path.join(root, name))
    else:
        files = [path]

    # For direct test, get parser path from env or fallback
    script = os.environ.get("LYNKMESH_PARSER_PATH")
    if not script:
        # fallback to the old hardcoded logic for local testing only
        script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "ast_bridge",
            "parser.php"
        )
    parser = ParallelParser(script)
    results = parser.run(path, files)
    print(f"Parsed {len(results)} files")
    if results:
        print(json.dumps(results[0], indent=2)[:1000])

    # Print diagnostics if available
    if parser.last_diagnostics:
        print("\n--- Per-file diagnostics ---")
        print(json.dumps(parser.last_diagnostics, indent=2))