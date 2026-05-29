#!/usr/bin/env python3
"""Release validation gate — 14 steps, stop at first failure.

Usage:
    python scripts/validate_release.py

Each step prints ✓ PASS or ✗ FAIL with up to 3 lines of context.
Exit 0 if all pass, exit 1 on first failure.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
PYTHON = sys.executable
TOTAL_STEPS = 14


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


def _surface_check() -> bool:
    """Step 14 — README surface consistency (4 sub-checks aggregated)."""
    label = f"[{TOTAL_STEPS}/{TOTAL_STEPS} README surface check]"
    readme_path = REPO / "README.md"
    pyproject_path = REPO / "pyproject.toml"

    if not readme_path.exists() or not pyproject_path.exists():
        print(f"  ✗ FAIL  {label}")
        print("         README.md or pyproject.toml not found")
        return False

    readme = readme_path.read_text(encoding="utf-8")
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    failures: list[str] = []
    notes: list[str] = []

    # Check A — every actions/workflows/X.yml referenced in README must exist.
    workflows_dir = REPO / ".github" / "workflows"
    for wf in sorted(set(re.findall(r"actions/workflows/([\w.-]+\.yml)", readme))):
        if not (workflows_dir / wf).exists():
            failures.append(
                f"A: README references actions/workflows/{wf} but .github/workflows/{wf} missing"
            )

    # Check B — every diplomat-gate[<extra>] in README must exist in pyproject.
    extras_in_readme = sorted(set(re.findall(r"diplomat-gate\[(\w+)\]", readme)))
    declared_extras: set[str] = set()
    try:
        import tomllib  # type: ignore[import-not-found]

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        declared_extras = set(
            data.get("project", {}).get("optional-dependencies", {}).keys()
        )
    except ImportError:
        # Python 3.10 fallback: best-effort regex parse of the section.
        section = re.search(
            r"\[project\.optional-dependencies\](.*?)(?:\n\[|\Z)",
            pyproject_text,
            re.DOTALL,
        )
        if section:
            declared_extras = set(re.findall(r"^(\w+)\s*=", section.group(1), re.MULTILINE))
    for extra in extras_in_readme:
        if extra not in declared_extras:
            failures.append(
                f"B: README uses diplomat-gate[{extra}] but extra not declared in pyproject.toml"
            )

    # Check C — yaml blocks with `version:` in first two non-comment lines must parse.
    try:
        import yaml as _yaml  # type: ignore[import-not-found]
    except ImportError:
        _yaml = None
        notes.append("Check C skipped (pyyaml not installed)")

    if _yaml is not None:
        for m in re.finditer(r"```yaml\n(.*?)```", readme, re.DOTALL):
            block = m.group(1)
            head = [
                ln
                for ln in block.splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")
            ][:2]
            if any("version:" in ln for ln in head):
                try:
                    _yaml.safe_load(block)
                except Exception as exc:
                    failures.append(f"C: yaml block with 'version:' fails to parse: {exc}")

    # Check D — every '<N>-step' mention in README must equal TOTAL_STEPS.
    step_counts = set(int(m) for m in re.findall(r"(\d+)-step", readme))
    if not step_counts:
        failures.append(
            f"D: README mentions no '<N>-step' value; script declares {TOTAL_STEPS}"
        )
    elif step_counts != {TOTAL_STEPS}:
        failures.append(
            f"D: README mentions {sorted(step_counts)} '-step' value(s); script declares {TOTAL_STEPS}"
        )

    if failures:
        print(f"  ✗ FAIL  {label}")
        for line in failures[:6]:
            print(f"         {line}")
        for note in notes:
            print(f"         ({note})")
        return False
    print(f"  ✓ PASS  {label}")
    for note in notes:
        print(f"         ({note})")
    return True


def main() -> None:
    print(f"\n  diplomat-gate release validation\n  {'─' * 40}")

    steps: list[tuple[str, list[str]]] = [
        ("1/14 ruff check", [PYTHON, "-m", "ruff", "check", "."]),
        ("2/14 ruff format", [PYTHON, "-m", "ruff", "format", "--check", "."]),
        (
            "3/14 pytest --cov",
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
            "4/14 pytest integration",
            [PYTHON, "-m", "pytest", "-m", "integration", "-q", "--tb=short"],
        ),
        (
            "5/14 benchmarks p95<5ms",
            [
                PYTHON,
                "benchmarks/run.py",
                "--iterations",
                "1000",
                "--assert-p95-under",
                "5.0",
            ],
        ),
        ("6/14 build sdist+wheel", [PYTHON, "-m", "build"]),
        ("7/14 twine check", [PYTHON, "-m", "twine", "check", "dist/*"]),
    ]

    for step, cmd in steps:
        if not _check(step, cmd):
            sys.exit(1)

    # Step 8 — fresh venv smoke install
    print(f"  {'─' * 40}")
    print("  [8/14 fresh-venv smoke install]", flush=True)
    dist_wheels = sorted(REPO.glob("dist/*.whl"))
    if not dist_wheels:
        print("  ✗ FAIL  [8/14] no wheel found in dist/")
        sys.exit(1)
    wheel = dist_wheels[-1]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        venv = tmp_path / "venv"
        r1 = _run([PYTHON, "-m", "venv", str(venv)])
        if r1.returncode != 0:
            print("  ✗ FAIL  [8/14] venv creation failed")
            sys.exit(1)
        venv_python = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        r2 = _run([str(venv_python), "-m", "pip", "install", str(wheel), "--quiet"])
        if r2.returncode != 0:
            print("  ✗ FAIL  [8/14] pip install failed")
            lines = (r2.stderr or r2.stdout or "").splitlines()[:3]
            for ln in lines:
                print(f"         {ln}")
            sys.exit(1)
        print("  ✓ PASS  [8/14 fresh-venv smoke install]")

        # Step 9 — diplomat-gate --help
        venv_bin = venv / ("Scripts" if sys.platform == "win32" else "bin")
        diplomat_cmd = venv_bin / (
            "diplomat-gate.exe" if sys.platform == "win32" else "diplomat-gate"
        )
        if not _check("9/14 diplomat-gate --help", [str(diplomat_cmd), "--help"]):
            sys.exit(1)

        # Step 10 — audit verify --help
        if not _check(
            "10/14 audit verify --help", [str(diplomat_cmd), "audit", "verify", "--help"]
        ):
            sys.exit(1)

        # Step 11 — validate --help
        if not _check("11/14 validate --help", [str(diplomat_cmd), "validate", "--help"]):
            sys.exit(1)

        # Step 12 — validate gate.yaml.example
        if not _check(
            "12/14 validate gate.yaml.example",
            [str(diplomat_cmd), "validate", str(REPO / "gate.yaml.example")],
        ):
            sys.exit(1)

    # Step 13 — demo --ci
    demo_path = REPO / "demos" / "openclaw" / "run.py"
    if demo_path.exists():
        if not _check("13/14 demo --ci", [PYTHON, str(demo_path), "--ci"]):
            sys.exit(1)
    else:
        print("  ⚠ SKIP  [13/14 demo --ci] demos/openclaw/run.py not yet created")

    # Step 14 — README surface consistency check
    if not _surface_check():
        sys.exit(1)

    print(f"\n  {'─' * 40}")
    print("  All checks passed. Ready to release.\n")


if __name__ == "__main__":
    main()
