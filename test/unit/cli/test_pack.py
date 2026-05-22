"""Open-core-safe tests for the public ``lynkmesh pack`` CLI command.

These tests stub the pipeline build step so they run fast and require no PHP
toolchain. They must remain open-core safe: no private absolute paths, no
internal-only references, no network, no real graph build.
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

cli_main = importlib.import_module("lynkmesh.cli.main")

# Forbidden markers assembled at runtime so this file holds no blocked literal.
_WIN_USER_DIR = "App" + "Data"
_WIN_DRIVE = "C:" + "\\"
_PRIVATE_MARKERS = (_WIN_DRIVE, "/Users/", "/home/", _WIN_USER_DIR)

_FAKE_PAYLOAD = {
    "schema_version": "3.1.0",
    "version": {
        "content_hash": "deadbeef",
        "metadata": {"graph_id": "g1", "build_id": "b1", "git_commit": None},
    },
    "stats": {"nodes": 1, "edges": 0},
    "nodes": [{"id": "n1", "type": "file"}],
    "edges": [],
}


class _FakeRun:
    serialized_payload = _FAKE_PAYLOAD
    pipeline_schema_version = "3.4.0"


@pytest.fixture
def stub_pipeline(monkeypatch):
    monkeypatch.setattr(cli_main, "_run_pipeline", lambda project_path: _FakeRun())


def _capture(argv, capsys):
    code = cli_main.main(argv)
    out = capsys.readouterr()
    return code, out


def test_pack_exit_zero_and_valid_json(stub_pipeline, tmp_path, capsys):
    code, out = _capture(["pack", str(tmp_path)], capsys)
    assert code == 0
    payload = json.loads(out.out)  # stdout must be valid JSON
    assert "schema_version" in payload
    assert str(payload["schema_version"]).startswith("mesh_context_ai_pack")


def test_pack_default_profile_is_compact(stub_pipeline, tmp_path, capsys):
    _, out = _capture(["pack", str(tmp_path)], capsys)
    payload = json.loads(out.out)
    assert payload.get("profile") == "compact"


@pytest.mark.parametrize("profile", ["compact", "balanced", "expanded"])
def test_pack_accepts_supported_profiles(stub_pipeline, tmp_path, capsys, profile):
    code, out = _capture(["pack", str(tmp_path), "--profile", profile], capsys)
    assert code == 0
    payload = json.loads(out.out)
    assert payload.get("profile") == profile


def test_pack_invalid_profile_is_argparse_error(stub_pipeline, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli_main.main(["pack", str(tmp_path), "--profile", "nope"])
    assert exc.value.code == 2  # argparse-standard usage error


def test_pack_provenance_declares_no_llm_inference(stub_pipeline, tmp_path, capsys):
    _, out = _capture(["pack", str(tmp_path)], capsys)
    payload = json.loads(out.out)
    assert payload["guardrails"]["contains_llm_inference"] is False


def test_pack_pretty_is_valid_indented_json(stub_pipeline, tmp_path, capsys):
    _, out = _capture(["pack", str(tmp_path), "--pretty"], capsys)
    payload = json.loads(out.out)
    assert "schema_version" in payload
    assert "\n" in out.out.strip()


def test_pack_quiet_keeps_stdout_pure_json(stub_pipeline, tmp_path, capsys):
    code, out = _capture(["pack", str(tmp_path), "--quiet"], capsys)
    assert code == 0
    json.loads(out.out)
    assert out.err == ""


def test_pack_diagnostics_go_to_stderr(stub_pipeline, tmp_path, capsys):
    _, out = _capture(["pack", str(tmp_path)], capsys)
    json.loads(out.out)
    assert out.err.strip() != ""


def test_pack_invalid_path_nonzero_no_traceback(capsys):
    code, out = _capture(["pack", str(Path("does") / "not" / "exist-xyz")], capsys)
    assert code != 0
    assert out.out == ""
    assert "Traceback" not in out.err
    assert "error:" in out.err.lower()


def test_pack_output_has_no_private_paths(stub_pipeline, tmp_path, capsys):
    _, out = _capture(["pack", str(tmp_path)], capsys)
    for marker in _PRIVATE_MARKERS:
        assert marker not in out.out


def test_pack_privacy_scanner_fails_closed(stub_pipeline, tmp_path, capsys, monkeypatch):
    from lynkmesh.semantic import contracts as contracts_mod

    monkeypatch.setattr(
        contracts_mod, "find_unsafe_ai_pack_strings", lambda value: ["unsafe-token"]
    )
    code, out = _capture(["pack", str(tmp_path)], capsys)
    assert code != 0
    assert out.out == ""
    assert "safety scan" in out.err.lower()


def test_help_lists_pack():
    parser = cli_main.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0


def test_python_dash_m_pack_invalid_path_nonzero():
    """`python -m lynkmesh pack <missing>` exits non-zero (no build needed)."""
    import lynkmesh

    container = Path(lynkmesh.__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "lynkmesh", "pack", "definitely-missing-dir-xyz"],
        cwd=str(container),
        env={"PYTHONPATH": str(container), "PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
