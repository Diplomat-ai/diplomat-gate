"""Smoke tests: every script in examples/ must run cleanly from the repo root
and from inside the examples/ directory itself."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
SCRIPTS = sorted(p.name for p in EXAMPLES_DIR.glob("[0-9][0-9]_*.py"))


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("cwd_label", ["repo_root", "examples_dir"])
def test_example_runs(script: str, cwd_label: str) -> None:
    cwd = REPO_ROOT if cwd_label == "repo_root" else EXAMPLES_DIR
    script_path = EXAMPLES_DIR / script if cwd_label == "repo_root" else Path(script)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"{script} (cwd={cwd_label}) exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.stdout.strip(), f"{script} produced no stdout"
