#!/usr/bin/env python3
"""Release validation gate — 13 steps, stop at first failure.

Usage:
    python scripts/validate_release.py

Each step prints ✓ PASS or ✗ FAIL with up to 3 lines of context.
Exit 0 if all pass, exit 1 on first failure.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
PYTHON = sys.executable


def _run(
    cmd: list[str], *, cwd: Path | None = None, capture: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd or REPO,
        capture_output=capture,
        text=True,
    )


def _check(step: str, cmd: list[str], *, cwd: Path | None = None) -> bool:
    label = f"[{step}]"
    result = _run(cmd, cwd=cwd)
    if result.returncode == 0:
        print(f"  ✓ PASS  {label}")
        return True
    # Collect stderr+stdout, show first 3 non-empty lines
    output = (result.stderr or result.stdout or "").strip()
    lines = [ln for ln in output.splitlines() if ln.strip()][:3]
    context = "\n".join(f"         {ln}" for ln in lines)
    print(f"  ✗ FAIL  {label}")
    if context:
        print(context)
    return False


def main() -> None:
    print(f"\n  diplomat-gate release validation\n  {'─' * 40}")

    steps: list[tuple[str, list[str]]] = [
        ("1/13 ruff check", [PYTHON, "-m", "ruff", "check", "."]),
        ("2/13 ruff format", [PYTHON, "-m", "ruff", "format", "--check", "."]),
        (
            "3/13 pytest --cov",
            [
                PYTHON,
                "-m",
                "pytest",
                "--cov=diplomat_gate",
                "--cov-fail-under=80",
                "-q",
                "--tb=short",
            ],
        ),
        (
            "4/13 pytest integration",
            [PYTHON, "-m", "pytest", "-m", "integration", "-q", "--tb=short"],
        ),
        (
            "5/13 benchmarks p95<5ms",
            [
                PYTHON,
                "benchmarks/run.py",
                "--iterations",
                "1000",
                "--assert-p95-under",
                "5.0",
            ],
        ),
        ("6/13 build sdist+wheel", [PYTHON, "-m", "build"]),
        ("7/13 twine check", [PYTHON, "-m", "twine", "check", "dist/*"]),
    ]

    for step, cmd in steps:
        if not _check(step, cmd):
            sys.exit(1)

    # Step 8 — fresh venv smoke install
    print(f"  {'─' * 40}")
    print("  [8/13 fresh-venv smoke install]", flush=True)
    dist_wheels = sorted(REPO.glob("dist/*.whl"))
    if not dist_wheels:
        print("  ✗ FAIL  [8/13] no wheel found in dist/")
        sys.exit(1)
    wheel = dist_wheels[-1]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        venv = tmp_path / "venv"
        r1 = _run([PYTHON, "-m", "venv", str(venv)])
        if r1.returncode != 0:
            print("  ✗ FAIL  [8/13] venv creation failed")
            sys.exit(1)
        venv_python = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        r2 = _run([str(venv_python), "-m", "pip", "install", str(wheel), "--quiet"])
        if r2.returncode != 0:
            print("  ✗ FAIL  [8/13] pip install failed")
            lines = (r2.stderr or r2.stdout or "").splitlines()[:3]
            for ln in lines:
                print(f"         {ln}")
            sys.exit(1)
        print("  ✓ PASS  [8/13 fresh-venv smoke install]")

        # Step 9 — diplomat-gate --help
        venv_bin = venv / ("Scripts" if sys.platform == "win32" else "bin")
        diplomat_cmd = venv_bin / (
            "diplomat-gate.exe" if sys.platform == "win32" else "diplomat-gate"
        )
        if not _check("9/13 diplomat-gate --help", [str(diplomat_cmd), "--help"]):
            sys.exit(1)

        # Step 10 — audit verify --help
        if not _check(
            "10/13 audit verify --help", [str(diplomat_cmd), "audit", "verify", "--help"]
        ):
            sys.exit(1)

        # Step 10bis — validate --help
        if not _check("10bis/13 validate --help", [str(diplomat_cmd), "validate", "--help"]):
            sys.exit(1)

        # Step 10ter — validate gate.yaml.example
        if not _check(
            "10ter/13 validate gate.yaml.example",
            [str(diplomat_cmd), "validate", str(REPO / "gate.yaml.example")],
        ):
            sys.exit(1)

    # Step 11 — demo --ci
    demo_path = REPO / "demos" / "openclaw" / "run.py"
    if demo_path.exists():
        if not _check("11/13 demo --ci", [PYTHON, str(demo_path), "--ci"]):
            sys.exit(1)
    else:
        print("  ⚠ SKIP  [11/13 demo --ci] demos/openclaw/run.py not yet created (Phase 2)")

    print(f"\n  {'─' * 40}")
    print("  All checks passed. Ready to release.\n")


if __name__ == "__main__":
    main()
