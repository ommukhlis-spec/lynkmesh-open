"""LynkMesh command-line interface (research preview / early validation).

This module implements the public CLI entry point. In this stage the only
command is ``doctor``, which reports local environment diagnostics.

Design contract for every command in this module:

* local-first: no network access
* deterministic: same environment -> same output
* safe defaults: no files are written
* privacy: never print raw absolute filesystem paths or private project names
* no LLM inference

``doctor`` specifically does NOT build a graph and does NOT scan a user project.
It only inspects the local Python environment and the installed package.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Sequence

POSITIONING = (
    "LynkMesh is a research preview / early validation. Not production-ready."
)

MIN_PYTHON = (3, 11)


def _get_version() -> str:
    """Return the installed package version, or a source-checkout sentinel.

    Never raises and never returns a filesystem path.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("lynkmesh")
        except PackageNotFoundError:
            return "unknown (source checkout)"
    except Exception:  # pragma: no cover - defensive
        return "unknown"


def _check_import(module_name: str) -> tuple[bool, str]:
    """Try to import a module. Return (ok, short_detail).

    The detail is an exception type name only (never a message or path), so it
    cannot leak private paths.
    """
    try:
        __import__(module_name)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 - diagnostics must be resilient
        return False, type(exc).__name__


def _php_bridge_status() -> dict:
    """Detect PHP analysis availability without building or scanning anything.

    Returns booleans only. Never returns an absolute path.
    """
    bundled_parser_present = False
    try:
        import lynkmesh

        pkg_dir = Path(lynkmesh.__file__).resolve().parent
        bundled_parser_present = (
            pkg_dir / "ingestion" / "php_bridge" / "parser.php"
        ).is_file()
    except Exception:  # pragma: no cover - defensive
        bundled_parser_present = False

    php_executable_found = shutil.which("php") is not None
    return {
        "bundled_parser_present": bundled_parser_present,
        "php_executable_found": php_executable_found,
        "available": bundled_parser_present and php_executable_found,
    }


def collect_diagnostics() -> dict:
    """Gather deterministic, privacy-safe environment diagnostics.

    Does not build a graph, scan a project, write files, or access the network.
    """
    info = sys.version_info
    python_version = f"{info.major}.{info.minor}.{info.micro}"
    python_supported = (info.major, info.minor) >= MIN_PYTHON

    lynkmesh_ok, lynkmesh_detail = _check_import("lynkmesh")
    contracts_ok, contracts_detail = _check_import("lynkmesh.semantic.contracts")

    hashseed = os.environ.get("PYTHONHASHSEED")
    essential_ok = lynkmesh_ok and contracts_ok

    return {
        "tool": "lynkmesh",
        "command": "doctor",
        "version": _get_version(),
        "positioning": POSITIONING,
        "checks": {
            "python_version": python_version,
            "python_version_supported": python_supported,
            "minimum_python": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            "import_lynkmesh": lynkmesh_ok,
            "import_lynkmesh_detail": lynkmesh_detail,
            "import_semantic_contracts": contracts_ok,
            "import_semantic_contracts_detail": contracts_detail,
            "pythonhashseed": hashseed,
            "deterministic_recommended_value": "0",
            "deterministic_mode_active": hashseed == "0",
            "php_bridge": _php_bridge_status(),
        },
        "essential_imports_ok": essential_ok,
        "guarantees": {
            "builds_graph": False,
            "writes_files": False,
            "network_access": False,
            "contains_llm_inference": False,
        },
    }


def _ok(flag: bool) -> str:
    return "ok" if flag else "FAIL"


def _php_summary(php: dict) -> str:
    if php["available"]:
        return "available (PHP analysis enabled)"
    if not php["bundled_parser_present"]:
        return "not detected (bundled parser missing)"
    if not php["php_executable_found"]:
        return "not detected (php executable not on PATH)"
    return "not detected"


def render_human(diag: dict, quiet: bool = False) -> str:
    checks = diag["checks"]
    ready = diag["essential_imports_ok"]

    if quiet:
        state = "ready" if ready else "NOT ready"
        return f"lynkmesh doctor: {state} (v{diag['version']})"

    seed = checks["pythonhashseed"]
    seed_display = seed if seed is not None else "unset"
    seed_note = (
        "ok"
        if checks["deterministic_mode_active"]
        else "recommend PYTHONHASHSEED=0 for deterministic output"
    )
    py_note = "" if checks["python_version_supported"] else "  (3.11+ required)"

    lines = [
        f"LynkMesh {diag['version']}",
        f"  {diag['positioning']}",
        f"  python                {checks['python_version']}   {_ok(checks['python_version_supported'])}{py_note}",
        f"  import lynkmesh       {_ok(checks['import_lynkmesh'])}",
        f"  semantic.contracts    {_ok(checks['import_semantic_contracts'])}",
        f"  PYTHONHASHSEED        {seed_display}   {seed_note}",
        f"  php bridge            {_php_summary(checks['php_bridge'])}",
        "  guarantees            no graph build, no file writes, no network, no LLM inference",
        f"Result: {'ready' if ready else 'NOT ready - essential imports failed'}",
    ]
    return "\n".join(lines)


def cmd_doctor(args: argparse.Namespace) -> int:
    diag = collect_diagnostics()
    if getattr(args, "json", False):
        sys.stdout.write(json.dumps(diag, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_human(diag, quiet=getattr(args, "quiet", False)) + "\n")
    return 0 if diag["essential_imports_ok"] else 1


def _run_pipeline(project_path: str):
    """Run a deterministic, no-cache build and return the run report.

    Imports are deferred so that ``doctor`` and ``--help`` never pay the cost of
    importing the pipeline, and so a pipeline import problem cannot break them.

    The pipeline runs with caching disabled and cache-save skipped, so no files
    are written. No network access is performed.
    """
    from lynkmesh.pipeline.incremental_pipeline import IncrementalPipeline

    pipeline = IncrementalPipeline(cache_dir=None)
    return pipeline.run(project_path, skip_cache_save=True)


def build_report_dict(project_path: str) -> dict:
    """Build a deterministic MeshContext Report dict for a local project path.

    Pure projection over the serialized graph payload. Contains no LLM
    inference and writes no files.
    """
    from lynkmesh.semantic.contracts import build_mesh_context_report

    run = _run_pipeline(project_path)
    payload = getattr(run, "serialized_payload", None)
    if not payload:
        raise RuntimeError("pipeline did not produce a serialized graph payload")

    display_name = Path(project_path).name or None
    report = build_mesh_context_report(
        payload,
        project_display_name=display_name,
        pipeline_schema_version=getattr(run, "pipeline_schema_version", None),
        generator_version=_get_version(),
    )
    return report.to_dict()


def cmd_report(args: argparse.Namespace) -> int:
    quiet = getattr(args, "quiet", False)

    def diag(message: str) -> None:
        if not quiet:
            sys.stderr.write(message + "\n")

    path = Path(args.path)
    if not path.exists():
        sys.stderr.write("error: path does not exist\n")
        return 1
    if not path.is_dir():
        sys.stderr.write("error: path must be a directory\n")
        return 1

    diag("Building deterministic MeshContext Report (no LLM inference, no files written)...")
    try:
        report_dict = build_report_dict(str(path))
    except Exception as exc:  # noqa: BLE001 - report a friendly error, no traceback
        sys.stderr.write(f"error: failed to build MeshContext Report ({type(exc).__name__})\n")
        return 1

    # Privacy: fail closed if the projection contains unsafe strings.
    try:
        from lynkmesh.semantic.contracts import find_unsafe_report_strings

        unsafe = find_unsafe_report_strings(report_dict)
    except Exception:  # noqa: BLE001 - scanner must never crash the command
        unsafe = []
    if unsafe:
        sys.stderr.write(
            "error: report payload failed the privacy safety scan; "
            "output withheld\n"
        )
        return 1

    if getattr(args, "pretty", False):
        sys.stdout.write(json.dumps(report_dict, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(json.dumps(report_dict, sort_keys=True) + "\n")
    diag("Done.")
    return 0


def build_pack_dict(project_path: str, profile: str = "compact") -> dict:
    """Build a deterministic MeshContext AI Context Pack dict for a project path.

    Reuses the same public-safe report path as ``report`` and projects the AI
    Context Pack from it. Contains no LLM inference and writes no files.
    """
    from lynkmesh.semantic.contracts import build_mesh_context_ai_pack

    report_dict = build_report_dict(project_path)
    return build_mesh_context_ai_pack(report_dict, profile=profile)


def cmd_pack(args: argparse.Namespace) -> int:
    quiet = getattr(args, "quiet", False)

    def diag(message: str) -> None:
        if not quiet:
            sys.stderr.write(message + "\n")

    path = Path(args.path)
    if not path.exists():
        sys.stderr.write("error: path does not exist\n")
        return 1
    if not path.is_dir():
        sys.stderr.write("error: path must be a directory\n")
        return 1

    profile = getattr(args, "profile", "compact")
    diag(
        "Building deterministic MeshContext AI Context Pack "
        f"(profile={profile}, no LLM inference, no files written)..."
    )
    try:
        pack_dict = build_pack_dict(str(path), profile=profile)
    except ValueError as exc:  # unsupported profile from the contract layer
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001 - friendly error, no traceback
        sys.stderr.write(
            f"error: failed to build MeshContext AI Context Pack ({type(exc).__name__})\n"
        )
        return 1

    # Privacy: fail closed if the projection contains unsafe strings.
    try:
        from lynkmesh.semantic.contracts import find_unsafe_ai_pack_strings

        unsafe = find_unsafe_ai_pack_strings(pack_dict)
    except Exception:  # noqa: BLE001 - scanner must never crash the command
        unsafe = []
    if unsafe:
        sys.stderr.write(
            "error: AI Context Pack payload failed the privacy safety scan; "
            "output withheld\n"
        )
        return 1

    if getattr(args, "pretty", False):
        sys.stdout.write(json.dumps(pack_dict, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(json.dumps(pack_dict, sort_keys=True) + "\n")
    diag("Done.")
    return 0


_SUPPORTED_PROFILES = ("compact", "balanced", "expanded")


def build_benchmark_dict(project_path: str, profiles: Sequence[str]) -> dict:
    """Build a deterministic MeshContext Token Benchmark dict for a project path.

    Reuses the same public-safe report path as ``report``. The token benchmark
    contract builds the AI Context Pack(s) internally. The serialized graph
    payload is supplied as an additional calibration baseline. Contains no LLM
    inference and writes no files.
    """
    from lynkmesh.semantic.contracts import (
        build_mesh_context_report,
        build_mesh_context_token_benchmark,
    )

    run = _run_pipeline(project_path)
    payload = getattr(run, "serialized_payload", None)
    if not payload:
        raise RuntimeError("pipeline did not produce a serialized graph payload")

    display_name = Path(project_path).name or None
    report = build_mesh_context_report(
        payload,
        project_display_name=display_name,
        pipeline_schema_version=getattr(run, "pipeline_schema_version", None),
        generator_version=_get_version(),
    )
    return build_mesh_context_token_benchmark(
        report.to_dict(),
        profiles=list(profiles),
        source_baselines={"serialized_graph_payload": payload},
        benchmark_source_kind="mesh_context_report",
    )


def cmd_benchmark(args: argparse.Namespace) -> int:
    quiet = getattr(args, "quiet", False)

    def diag(message: str) -> None:
        if not quiet:
            sys.stderr.write(message + "\n")

    path = Path(args.path)
    if not path.exists():
        sys.stderr.write("error: path does not exist\n")
        return 1
    if not path.is_dir():
        sys.stderr.write("error: path must be a directory\n")
        return 1

    raw_profiles = getattr(args, "profiles", None)
    if raw_profiles:
        profiles = [p.strip() for p in raw_profiles.split(",") if p.strip()]
    else:
        profiles = [getattr(args, "profile", "compact")]

    invalid = [p for p in profiles if p not in _SUPPORTED_PROFILES]
    if invalid or not profiles:
        supported = ", ".join(_SUPPORTED_PROFILES)
        detail = ", ".join(invalid) if invalid else "(none provided)"
        sys.stderr.write(
            f"error: unsupported profile(s): {detail}; choose from {supported}\n"
        )
        return 2

    diag(
        "Building deterministic MeshContext Token Benchmark "
        f"(profiles={','.join(profiles)}, no LLM inference, no files written)..."
    )
    try:
        benchmark_dict = build_benchmark_dict(str(path), profiles)
    except ValueError as exc:  # unsupported profile from the contract layer
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001 - friendly error, no traceback
        sys.stderr.write(
            f"error: failed to build MeshContext Token Benchmark ({type(exc).__name__})\n"
        )
        return 1

    # Privacy: fail closed if the projection contains unsafe strings.
    try:
        from lynkmesh.semantic.contracts import find_unsafe_token_benchmark_strings

        unsafe = find_unsafe_token_benchmark_strings(benchmark_dict)
    except Exception:  # noqa: BLE001 - scanner must never crash the command
        unsafe = []
    if unsafe:
        sys.stderr.write(
            "error: token benchmark payload failed the privacy safety scan; "
            "output withheld\n"
        )
        return 1

    if getattr(args, "pretty", False):
        sys.stdout.write(json.dumps(benchmark_dict, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(json.dumps(benchmark_dict, sort_keys=True) + "\n")
    diag("Done.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lynkmesh",
        description=(
            "LynkMesh command-line interface "
            "(research preview / early validation - not production-ready)."
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"lynkmesh {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    doctor = subparsers.add_parser(
        "doctor",
        help="Local environment diagnostics (no graph build, no file writes).",
        description=(
            "Report local environment diagnostics. Does not build a graph, "
            "scan a project, write files, or access the network."
        ),
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Emit diagnostics as JSON to stdout.",
    )
    doctor.add_argument(
        "--quiet",
        action="store_true",
        help="Print only a one-line result summary.",
    )
    doctor.set_defaults(func=cmd_doctor)

    report = subparsers.add_parser(
        "report",
        help="Build a deterministic MeshContext Report for a local project (JSON to stdout).",
        description=(
            "Build a deterministic MeshContext Report for a local project path "
            "and print it as JSON to stdout. Research preview. Deterministic, "
            "no LLM inference, not production-ready. No files are written and no "
            "network access is performed."
        ),
    )
    report.add_argument(
        "path",
        help="Path to a local project directory to analyze.",
    )
    report.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the JSON output.",
    )
    report.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-JSON diagnostics on stderr.",
    )
    report.set_defaults(func=cmd_report)

    pack = subparsers.add_parser(
        "pack",
        help="Build a deterministic MeshContext AI Context Pack for a local project (JSON to stdout).",
        description=(
            "Build a deterministic MeshContext AI Context Pack for a local "
            "project path and print it as JSON to stdout. Research preview. "
            "Deterministic, no LLM inference, not production-ready. No files are "
            "written and no network access is performed."
        ),
    )
    pack.add_argument(
        "path",
        help="Path to a local project directory to analyze.",
    )
    pack.add_argument(
        "--profile",
        choices=("compact", "balanced", "expanded"),
        default="compact",
        help="AI Context Pack profile (default: compact).",
    )
    pack.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the JSON output.",
    )
    pack.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-JSON diagnostics on stderr.",
    )
    pack.set_defaults(func=cmd_pack)

    benchmark = subparsers.add_parser(
        "benchmark",
        help="Build a deterministic MeshContext Token Benchmark for a local project (JSON to stdout).",
        description=(
            "Build a deterministic MeshContext Token Benchmark for a local "
            "project path and print it as JSON to stdout. Research preview. "
            "Deterministic, no LLM inference, not production-ready. No files are "
            "written and no network access is performed."
        ),
    )
    benchmark.add_argument(
        "path",
        help="Path to a local project directory to analyze.",
    )
    benchmark.add_argument(
        "--profile",
        choices=("compact", "balanced", "expanded"),
        default="compact",
        help="Token benchmark profile (default: compact).",
    )
    benchmark.add_argument(
        "--profiles",
        default=None,
        help=(
            "Comma-separated profiles to benchmark, e.g. "
            "compact,balanced,expanded. Overrides --profile when provided."
        ),
    )
    benchmark.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the JSON output.",
    )
    benchmark.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-JSON diagnostics on stderr.",
    )
    benchmark.set_defaults(func=cmd_benchmark)





    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "command", None) is None:
        # Friendly first-run behavior: show help on stderr, succeed.
        parser.print_help(sys.stderr)
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
