import json
import subprocess
import sys

import pytest

from lynkmesh.cli import main as cli_main


def _benchmark_payload(profiles=None):
    profiles = profiles or ["compact"]
    return {
        "schema_version": "mesh_context_token_benchmark.v0.1",
        "benchmark_source_kind": "mesh_context_report",
        "source_baselines": {
            "mesh_context_report": {"estimated_tokens": 100},
            "serialized_graph_payload": {"estimated_tokens": 200},
        },
        "calibration_notes": ["fixture"],
        "guardrails": {"contains_llm_inference": False},
        "profiles": {
            profile: {"estimated_input_tokens": 123}
            for profile in profiles
        },
    }


def _stub_benchmark(monkeypatch):
    calls = {}

    def fake_build(path, profiles):
        calls["profiles"] = profiles
        return _benchmark_payload(profiles)

    monkeypatch.setattr(cli_main, "build_benchmark_dict", fake_build)
    return calls


def test_benchmark_exit_zero_and_valid_json(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0
    data = json.loads(captured.out)
    assert data["schema_version"] == "mesh_context_token_benchmark.v0.1"


def test_benchmark_default_profile_compact(tmp_path, capsys, monkeypatch):
    calls = _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert calls["profiles"] == ["compact"]
    assert "compact" in data["profiles"]


@pytest.mark.parametrize("profile", ["compact", "balanced", "expanded"])
def test_benchmark_profile_choices(tmp_path, capsys, monkeypatch, profile):
    calls = _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path), "--profile", profile])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert calls["profiles"] == [profile]
    assert profile in data["profiles"]


def test_benchmark_profiles_multi(tmp_path, capsys, monkeypatch):
    calls = _stub_benchmark(monkeypatch)

    code = cli_main.main(
        ["benchmark", str(tmp_path), "--profiles", "compact,balanced,expanded"]
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert calls["profiles"] == ["compact", "balanced", "expanded"]
    assert {"compact", "balanced", "expanded"}.issubset(set(data["profiles"]))


def test_benchmark_invalid_profile_argparse(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli_main.main(["benchmark", str(tmp_path), "--profile", "bad"])

    assert exc.value.code == 2


def test_benchmark_invalid_profiles_list(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path), "--profiles", "compact,bad"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "unsupported profile(s)" in captured.err


def test_benchmark_contains_calibration_fields(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert data["benchmark_source_kind"] == "mesh_context_report"
    assert "source_baselines" in data
    assert "mesh_context_report" in data["source_baselines"]
    assert "serialized_graph_payload" in data["source_baselines"]
    assert "calibration_notes" in data


def test_benchmark_declares_no_llm_inference(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert data["guardrails"]["contains_llm_inference"] is False


def test_benchmark_pretty_is_valid_indented_json(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path), "--pretty"])

    captured = capsys.readouterr()
    assert code == 0
    assert "\n  " in captured.out
    json.loads(captured.out)


def test_benchmark_quiet_keeps_stdout_pure_json(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path), "--quiet"])

    captured = capsys.readouterr()
    assert code == 0
    json.loads(captured.out)
    assert captured.err == ""


def test_benchmark_diagnostics_go_to_stderr(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0
    assert "Building deterministic MeshContext Token Benchmark" in captured.err
    assert "Done." in captured.err
    json.loads(captured.out)


def test_benchmark_invalid_path_nonzero_no_traceback(tmp_path, capsys):
    missing = tmp_path / "missing"

    code = cli_main.main(["benchmark", str(missing)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "does not exist" in captured.err
    assert "Traceback" not in captured.err


def test_benchmark_file_path_rejected(tmp_path, capsys):
    file_path = tmp_path / "file.php"
    file_path.write_text("<?php", encoding="utf-8")

    code = cli_main.main(["benchmark", str(file_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "must be a directory" in captured.err


def test_benchmark_output_has_no_private_paths(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0
    forbidden = [
        "C:" + "\\",
        "Users",
        "App" + "Data",
        "private" + "_tests",
        "mcp" + "_server",
    ]
    for marker in forbidden:
        assert marker not in captured.out
        assert marker not in captured.err


def test_benchmark_privacy_scanner_fails_closed(tmp_path, capsys, monkeypatch):
    _stub_benchmark(monkeypatch)
    monkeypatch.setattr(
        cli_main,
        "build_benchmark_dict",
        lambda path, profiles: {"unsafe": "payload"},
    )

    import lynkmesh.semantic.contracts as contracts

    monkeypatch.setattr(
        contracts,
        "find_unsafe_token_benchmark_strings",
        lambda payload: ["unsafe"],
    )

    code = cli_main.main(["benchmark", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "failed the privacy safety scan" in captured.err


def test_help_lists_benchmark(capsys):
    with pytest.raises(SystemExit) as exc:
        cli_main.main(["--help"])

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "benchmark" in captured.out


def test_python_dash_m_benchmark_invalid_path_nonzero(tmp_path):
    missing = tmp_path / "missing"
    proc = subprocess.run(
        [sys.executable, "-m", "lynkmesh", "benchmark", str(missing)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert proc.stdout == ""
    assert "does not exist" in proc.stderr
    assert "Traceback" not in proc.stderr
