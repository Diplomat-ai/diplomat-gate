"""End-to-end integration tests covering paths that span multiple modules:

- Configure a Gate from YAML with audit + review queue, run a workload that
  triggers all three decisions, verify the chain, and inspect the queue.
- Round-trip the CLI (audit verify, review list/approve) against the
  artefacts a real workload produced.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from diplomat_gate import Gate
from diplomat_gate.audit import verify_chain


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "diplomat_gate.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def test_full_workflow_audit_and_review(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    cfg = tmp_path / "gate.yaml"
    cfg.write_text(
        textwrap.dedent(
            """\
            version: "1"
            payment:
              - id: payment.amount_limit
                max_amount: 1000
                on_fail: STOP
              - id: payment.duplicate_detection
                window: 5m
                on_fail: REVIEW
            """
        )
    )
    audit_db = tmp_path / "audit.db"
    review_db = tmp_path / "review.db"

    gate = Gate.from_yaml(
        str(cfg),
        audit_path=str(audit_db),
        review_queue_path=str(review_db),
    )
    try:
        # CONTINUE.
        v1 = gate.evaluate({"action": "charge_card", "amount": 200, "agent_id": "ag"})
        assert v1.decision.value == "CONTINUE"
        # STOP.
        v2 = gate.evaluate({"action": "charge_card", "amount": 5000, "agent_id": "ag"})
        assert v2.decision.value == "STOP"
        # REVIEW: same call twice within the dedup window.
        gate.evaluate({"action": "charge_card", "amount": 300, "agent_id": "ag"})
        v3 = gate.evaluate({"action": "charge_card", "amount": 300, "agent_id": "ag"})
        assert v3.decision.value == "REVIEW"
        assert gate.review_queue.pending_count() == 1
    finally:
        gate.close()

    # Audit chain verifies via API.
    res = verify_chain(str(audit_db))
    assert res.valid is True
    assert res.records_checked == 4

    # Audit chain verifies via CLI.
    cli = _run_cli("--no-color", "audit", "verify", "--db", str(audit_db))
    assert cli.returncode == 0, cli.stderr
    assert "valid" in cli.stdout.lower()

    # Review queue is reachable via CLI.
    cli = _run_cli("review", "list", "--db", str(review_db), "--json")
    assert cli.returncode == 0, cli.stderr
    items = json.loads(cli.stdout)
    assert len(items) == 1
    item_id = items[0]["item_id"]

    # Approve via CLI.
    cli = _run_cli(
        "review",
        "approve",
        "--db",
        str(review_db),
        "--id",
        item_id,
        "--reviewer",
        "alice",
        "--note",
        "ok",
    )
    assert cli.returncode == 0, cli.stderr

    # Item is no longer pending.
    cli = _run_cli("review", "list", "--db", str(review_db), "--json")
    assert cli.returncode == 0
    assert json.loads(cli.stdout) == []


def test_chain_tampering_is_detected(tmp_path: Path) -> None:
    """Mutating any persisted field must invalidate the chain."""
    import sqlite3

    audit_db = tmp_path / "audit.db"
    gate = Gate.from_dict(
        {"payment": [{"id": "payment.amount_limit", "max_amount": 10_000}]},
        audit_path=str(audit_db),
    )
    try:
        for amount in (10, 20, 30):
            gate.evaluate({"action": "charge_card", "amount": amount})
    finally:
        gate.close()

    assert verify_chain(str(audit_db)).valid is True

    conn = sqlite3.connect(str(audit_db))
    try:
        conn.execute("UPDATE verdicts SET decision = 'STOP' WHERE sequence = 2")
        conn.commit()
    finally:
        conn.close()

    res = verify_chain(str(audit_db))
    assert res.valid is False
    assert res.first_invalid_sequence == 2
