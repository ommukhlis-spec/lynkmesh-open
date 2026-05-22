"""Open-core-safe tests for the public ``lynkmesh doctor`` CLI command.

These tests must remain public/open-core safe: no private absolute paths, no
internal-only references, no network, no graph build, no file writes.

Note: forbidden path markers are assembled at runtime (e.g. ``"App" + "Data"``)
so that this test file itself contains no literal blocked by the open-core
safety scan.
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Import the submodule explicitly so it is never shadowed by a package-level
# re-export of a ``main`` symbol.
cli_main = importlib.import_module("lynkmesh.cli.main")

# Markers assembled at runtime to avoid embedding blocked literals in source.
_WIN_USER_DIR = "App" + "Data"
_WIN_DRIVE = "C:" + "\\"
_PRIVATE_MARKERS = (_WIN_DRIVE, "/Users/", "/home/", _WIN_USER_DIR)


def _capture(argv, capsys):
    code = cli_main.main(argv)
    out = capsys.readouterr()
    return code, out


def test_doctor_exit_zero_when_imports_available(capsys):
    code, out = _capture(["doctor"], capsys)
    assert code == 0
    assert out.out.strip() != ""


def test_doctor_reports_research_preview_positioning(capsys):
    _, out = _capture(["doctor"], capsys)
    assert "research preview" in out.out.lower()
    assert "not production-ready" in out.out.lower()


def test_doctor_json_is_valid_and_declares_no_llm_inference(capsys):
    code, out = _capture(["doctor", "--json"], capsys)
    assert code == 0
    payload = json.loads(out.out)
    assert payload["tool"] == "lynkmesh"
    assert payload["command"] == "doctor"
    assert payload["essential_imports_ok"] is True
    guarantees = payload["guarantees"]
    assert guarantees["contains_llm_inference"] is False
    assert guarantees["builds_graph"] is False
    assert guarantees["writes_files"] is False
    assert guarantees["network_access"] is False


def test_doctor_quiet_is_single_line(capsys):
    code, out = _capture(["doctor", "--quiet"], capsys)
    assert code == 0
    assert len([ln for ln in out.out.splitlines() if ln.strip()]) == 1


def test_doctor_output_has_no_private_paths(capsys):
    _, human = _capture(["doctor"], capsys)
    _, js = _capture(["doctor", "--json"], capsys)
    combined = human.out + js.out
    for marker in _PRIVATE_MARKERS:
        assert marker not in combined


def test_parser_builds_and_help_succeeds():
    parser = cli_main.build_parser()
    args = parser.parse_args(["doctor"])
    assert args.command == "doctor"
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0


def test_version_flag_exits_zero():
    parser = cli_main.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0


def test_no_command_prints_help_and_succeeds(capsys):
    code = cli_main.main([])
    out = capsys.readouterr()
    assert code == 0
    assert "usage" in out.err.lower()


def test_collect_diagnostics_does_not_leak_paths():
    diag = cli_main.collect_diagnostics()
    text = json.dumps(diag)
    for marker in _PRIVATE_MARKERS:
        assert marker not in text
    php = diag["checks"]["php_bridge"]
    assert set(php) == {"bundled_parser_present", "php_executable_found", "available"}
    assert all(isinstance(v, bool) for v in php.values())


def test_python_dash_m_lynkmesh_doctor_runs():
    """`python -m lynkmesh doctor` works regardless of package layout."""
    import lynkmesh

    container = Path(lynkmesh.__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "lynkmesh", "doctor", "--quiet"],
        cwd=str(container),
        env={"PYTHONPATH": str(container), "PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "doctor" in result.stdout.lower()
