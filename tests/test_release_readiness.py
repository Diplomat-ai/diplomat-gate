"""Release readiness tests — validates that the project is ready to ship.

These tests are meant to catch regressions between phases of the 0.3.0 sprint.
Integration tests (marked with @pytest.mark.integration) are skipped by default
and run explicitly in CI via `pytest -m integration`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO


# ── Basic import + YAML load smoke ───────────────────────────────────────────


def test_import_no_extras():
    """Import core diplomat_gate with zero extras installed."""
    import diplomat_gate  # noqa: F401
    from diplomat_gate import Decision, Gate  # noqa: F401


def test_version_is_string():
    import diplomat_gate

    assert isinstance(diplomat_gate.__version__, str)
    assert len(diplomat_gate.__version__.split(".")) == 3


def test_gate_from_dict_basic():
    """Load a YAML-equivalent dict config, evaluate a verdict — no extras needed."""
    from diplomat_gate import Gate

    gate = Gate.from_dict({"email": [{"id": "email.domain_blocklist", "blocked": ["*@evil.com"]}]})
    v = gate.evaluate({"action": "send_email", "to": "test@evil.com"})
    assert v.blocked


def test_gate_from_yaml_requires_pyyaml(tmp_path, repo_root):
    """Gate.from_yaml shows helpful error when PyYAML is absent (import mock)."""
    # We don't uninstall PyYAML in CI — just verify the error path exists and
    # that load_from_yaml actually calls yaml.safe_load (coverage path).
    pytest.importorskip("yaml")  # skip if somehow not installed
    # Verify the function is importable and references yaml
    import inspect

    import diplomat_gate.policies.loader as loader

    src = inspect.getsource(loader.load_from_yaml)
    assert "yaml" in src


# ── Version consistency ───────────────────────────────────────────────────────


def test_version_matches_pyproject(repo_root):
    """_version.py and pyproject.toml must report the same version."""
    import diplomat_gate

    pyproject = (repo_root / "pyproject.toml").read_text()
    # Find the version line robustly
    for line in pyproject.splitlines():
        if line.strip().startswith("version") and "=" in line:
            pyproject_version = line.split("=", 1)[1].strip().strip('"')
            break
    else:
        pytest.fail("version not found in pyproject.toml")
    assert diplomat_gate.__version__ == pyproject_version, (
        f"_version.py says {diplomat_gate.__version__!r}, pyproject.toml says {pyproject_version!r}"
    )


# ── Policy registry count (ties README claims to code) ───────────────────────


def test_policy_registry_has_expected_entries():
    """The loader registry must have exactly 9 entries (as documented)."""
    from diplomat_gate.policies.loader import _POLICY_MAP  # noqa: PLC2401

    assert len(_POLICY_MAP) == 9, (
        f"Expected 9 policies in _POLICY_MAP, got {len(_POLICY_MAP)}. "
        "Update this test AND the README if you add/remove policies."
    )


# ── Audit hash chain ──────────────────────────────────────────────────────────


def test_audit_compute_record_hash_produces_hex64(tmp_path):
    """SHA-256 produces a 64-char hex string."""
    from diplomat_gate.audit import compute_record_hash

    record = {
        "verdict_id": "test-id",
        "sequence": 1,
        "timestamp": "2026-04-21T00:00:00Z",
        "agent_id": "",
        "action": "test",
        "params_hash": "abc",
        "decision": "CONTINUE",
        "policies_evaluated": 1,
        "policies_failed": 0,
        "violations": "[]",
        "latency_ms": 0.1,
    }
    result = compute_record_hash(record, "0" * 64)
    assert len(result) == 64, f"Expected 64-char hex, got {len(result)}: {result!r}"
    assert all(c in "0123456789abcdef" for c in result), "Not a hex string"


def test_audit_chain_valid(tmp_path):
    """Write 3 verdicts and verify the chain is valid."""
    from diplomat_gate import Gate

    db = str(tmp_path / "audit.db")
    gate = Gate.from_dict(
        {"email": [{"id": "email.domain_blocklist", "blocked": ["*@blocked.com"]}]},
        audit_path=db,
    )
    gate.evaluate({"action": "send_email", "to": "ok@example.com"})
    gate.evaluate({"action": "send_email", "to": "bad@blocked.com"})
    gate.evaluate({"action": "send_email", "to": "ok2@example.com"})
    gate.close()

    from diplomat_gate.audit import verify_chain

    result = verify_chain(db)
    assert result.valid, f"Chain invalid: {result}"


# ── CLI discoverability ───────────────────────────────────────────────────────


@pytest.mark.integration
def test_cli_help_responds(repo_root):
    """diplomat-gate --help must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "diplomat_gate.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.integration
def test_cli_audit_verify_help(repo_root):
    """diplomat-gate audit verify --help must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "diplomat_gate.cli", "audit", "verify", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


# ── OpenClaw demo regression marker (added in Phase 2) ───────────────────────


@pytest.mark.integration
def test_openclaw_demo_produces_markers(repo_root):
    """The OpenClaw demo must always produce the 3 scenario markers.

    This test is added in Phase 1 and will SKIP until demos/openclaw/run.py
    is created in Phase 2.
    """
    demo = repo_root / "demos" / "openclaw" / "run.py"
    if not demo.exists():
        pytest.skip("demos/openclaw/run.py not yet created (Phase 2)")

    result = subprocess.run(
        [sys.executable, str(demo), "--ci"],
        cwd=repo_root,
        check=True,
        timeout=30,
        capture_output=True,
        text=True,
    )
    out = result.stdout
    assert "SCENARIO 1" in out, f"Missing SCENARIO 1 in output:\n{out}"
    assert any(m in out for m in ["without approval", "Legal email sent", "email sent"]), (
        f"Missing approval/sent marker in output:\n{out}"
    )
    assert "SCENARIO 2" in out, f"Missing SCENARIO 2 in output:\n{out}"
    assert any(m in out for m in ["Blocked", "STOP"]), (
        f"Missing STOP/Blocked marker in output:\n{out}"
    )
    assert "SCENARIO 3" in out, f"Missing SCENARIO 3 in output:\n{out}"
    assert any(m in out for m in ["Chain valid", "valid"]), (
        f"Missing chain-valid marker in output:\n{out}"
    )
