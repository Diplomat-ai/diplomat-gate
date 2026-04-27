"""Integration tests for `diplomat-gate validate`. Uses subprocess + PYTHONUTF8=1."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "validation"

ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "diplomat_gate.cli", *args],
        capture_output=True,
        text=True,
        timeout=15,
        env=ENV,
    )


@pytest.mark.integration
def test_cli_validate_help_responds():
    result = _run("validate", "--help")
    assert result.returncode == 0
    assert "validate" in result.stdout.lower()


@pytest.mark.integration
def test_cli_validate_valid_minimal_exit_zero():
    result = _run("validate", str(FIXTURES / "valid_minimal.yaml"))
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


@pytest.mark.integration
def test_cli_validate_invalid_exit_one():
    result = _run("validate", str(FIXTURES / "error_unknown_policy.yaml"))
    assert result.returncode == 1
    assert "INVALID" in result.stdout


@pytest.mark.integration
def test_cli_validate_missing_file_exit_two(tmp_path):
    nope = tmp_path / "nope.yaml"
    result = _run("validate", str(nope))
    assert result.returncode == 2
    assert "file not found" in result.stderr.lower()


@pytest.mark.integration
def test_cli_validate_json_flag_outputs_valid_json():
    result = _run("validate", str(FIXTURES / "valid_minimal.yaml"), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["format_version"] == "1"
    assert list(payload.keys()) == [
        "ok",
        "format_version",
        "config_path",
        "policies_loaded",
        "errors",
        "warnings",
    ]


@pytest.mark.integration
def test_cli_validate_quiet_suppresses_stdout():
    result = _run("validate", str(FIXTURES / "valid_minimal.yaml"), "--quiet")
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.integration
def test_cli_validate_quiet_invalid_still_exits_one():
    result = _run("validate", str(FIXTURES / "error_unknown_policy.yaml"), "--quiet")
    assert result.returncode == 1
    assert result.stdout == ""


@pytest.mark.integration
def test_cli_validate_output_writes_file(tmp_path):
    out = tmp_path / "report.json"
    result = _run(
        "validate",
        str(FIXTURES / "valid_minimal.yaml"),
        "--output",
        str(out),
        "--quiet",
    )
    assert result.returncode == 0
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["ok"] is True
    assert payload["format_version"] == "1"


@pytest.mark.integration
def test_cli_validate_no_color_global_flag():
    """--no-color is a parser-level flag — must come BEFORE the subcommand."""
    result = _run("--no-color", "validate", str(FIXTURES / "valid_minimal.yaml"))
    assert result.returncode == 0
    assert "\x1b[" not in result.stdout


@pytest.mark.integration
def test_cli_validate_full_example_passes():
    """The shipped gate.yaml.example must validate cleanly (exit 0)."""
    result = _run("validate", str(REPO / "gate.yaml.example"))
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


@pytest.mark.integration
def test_cli_validate_warn_shows_ok_with_warnings():
    result = _run("validate", str(FIXTURES / "warn_unknown_field.yaml"))
    assert result.returncode == 0
    assert "OK with warnings" in result.stdout


@pytest.mark.integration
def test_cli_validate_output_and_stdout_both_produced(tmp_path):
    """Without --quiet, --output still shows summary on stdout."""
    out = tmp_path / "report.json"
    result = _run(
        "validate",
        str(FIXTURES / "valid_minimal.yaml"),
        "--output",
        str(out),
    )
    assert result.returncode == 0
    assert out.exists()
    assert result.stdout.strip()  # summary on stdout
