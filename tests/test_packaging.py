"""Packaging: the wheel must never ship tools/ (issue #30).

``tools/verify_receipts.py`` is meant to be run standalone by a third-party
auditor without installing this package (see docs/receipt-format.md). It is
excluded from the wheel today because ``[tool.hatch.build.targets.wheel]``
in pyproject.toml uses an allowlist (``packages = ["src/diplomat_gate"]``),
not an exclude list — this test locks that behavior in against regression,
by actually building the wheel and inspecting its real contents.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).parent.parent


def _build_wheel(tmp_path: Path) -> Path:
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path), str(REPO)],
        capture_output=True,
        text=True,
        cwd=tmp_path,  # isolate: nothing is written under the real repo tree
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = sorted(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0]


def test_wheel_excludes_tools_directory(tmp_path):
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert names, "wheel is empty"
    tools_entries = [n for n in names if n.startswith("tools/")]
    assert tools_entries == [], f"tools/ leaked into the wheel: {tools_entries}"


def test_wheel_contains_the_actual_package(tmp_path):
    """Sanity check for the test above: prove it isn't passing by building an
    empty or broken wheel."""
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert any(n.startswith("diplomat_gate/") and n.endswith("cli.py") for n in names), names
