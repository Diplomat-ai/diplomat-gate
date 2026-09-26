"""Receipt format v1: the standalone verifier must agree with the library.

``tools/verify_receipts.py`` re-implements the hash chain check with the
standard library only. A verifier that drifts from the writer is worse
than none (false INVALID on a healthy database), so these tests compare
both implementations on the same data, row by row.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from diplomat_gate import Gate
from diplomat_gate.audit import GENESIS_HASH, compute_record_hash, verify_chain

REPO = Path(__file__).parent.parent
VERIFIER = REPO / "tools" / "verify_receipts.py"
SPEC_DOC = REPO / "docs" / "receipt-format.md"

# Golden vectors: derived from docs/receipt-format.md sections 2-4 by
# hand-writing the canonical string and hashing it with sha256sum. They
# are NOT copied from the output of diplomat_gate.
GOLDEN_1 = {
    "verdict_id": "00000000-0000-4000-8000-000000000001",
    "sequence": 1,
    "timestamp": "2026-01-01T00:00:00+00:00",
    "agent_id": "demo-agent",
    "action": "charge_card",
    "params_hash": "ab" * 32,
    "decision": "STOP",
    "policies_evaluated": 1,
    "policies_failed": 1,
    "violations": '[{"policy_id":"payment.amount_limit"}]',
    "latency_ms": 0.25,
}
GOLDEN_1_HASH = "3b759ae20fa503e3289d43cac2e51a024b922457916c5c890b5c3d30f80bb41c"
GOLDEN_2 = {
    "verdict_id": "00000000-0000-4000-8000-000000000002",
    "sequence": 2,
    "timestamp": "2026-01-01T00:00:01+00:00",
    "agent_id": "",
    "action": "send_email",
    "params_hash": "cd" * 32,
    "decision": "CONTINUE",
    "policies_evaluated": 2,
    "policies_failed": 0,
    "violations": "[]",
    "latency_ms": 1.5,
}
GOLDEN_2_HASH = "15e71cea9a920104a316e4b63cb578ffb42cd1f48808ce8de6772d64093bdb23"
GOLDEN_3 = {
    "verdict_id": "00000000-0000-4000-8000-000000000003",
    "sequence": 3,
    "timestamp": "2026-01-01T00:00:02+00:00",
    "agent_id": "agent-é",
    "action": "charge_card",
    "params_hash": "ef" * 32,
    "decision": "REVIEW",
    "policies_evaluated": 1,
    "policies_failed": 0,
    "violations": "[]",
    "latency_ms": 5e-05,
}
GOLDEN_3_HASH = "c7c90bbbdc5c52273f851ee86f36970760b0b9a757b1d7842dd85d5b39969051"

_COLUMNS = (
    "verdict_id, sequence, timestamp, agent_id, action, params_hash, decision, "
    "policies_evaluated, policies_failed, violations, latency_ms, previous_hash, record_hash"
)


@pytest.fixture(scope="module")
def verifier():
    spec = importlib.util.spec_from_file_location("verify_receipts", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_db(path: Path) -> str:
    """Write a realistic chain: STOP/CONTINUE mix, unicode agent id, varied latencies."""
    gate = Gate.from_dict(
        {"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]},
        audit_path=str(path),
    )
    for i, amount in enumerate((100, 1500, 500, 9000, 42, 2500)):
        gate.evaluate(
            {
                "action": "charge_card",
                "amount": amount,
                "agent_id": "agent-é✓" if i % 2 else f"bot-{i}",
            }
        )
    gate.close()
    return str(path)


def _rows(db: str) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT {_COLUMNS} FROM verdicts ORDER BY sequence").fetchall()
    finally:
        conn.close()


def _exec(db: str, sql: str) -> None:
    conn = sqlite3.connect(db)
    try:
        conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


# --- golden vectors ---------------------------------------------------------


def test_golden_vectors_both_implementations(verifier):
    assert compute_record_hash(GOLDEN_1, GENESIS_HASH) == GOLDEN_1_HASH
    assert verifier.compute_record_hash(GOLDEN_1, GENESIS_HASH) == GOLDEN_1_HASH
    assert compute_record_hash(GOLDEN_2, GOLDEN_1_HASH) == GOLDEN_2_HASH
    assert verifier.compute_record_hash(GOLDEN_2, GOLDEN_1_HASH) == GOLDEN_2_HASH
    assert compute_record_hash(GOLDEN_3, GOLDEN_2_HASH) == GOLDEN_3_HASH
    assert verifier.compute_record_hash(GOLDEN_3, GOLDEN_2_HASH) == GOLDEN_3_HASH


def test_published_doc_contains_vectors_that_hash_correctly():
    """The canonical strings printed in the spec must hash to the printed digests."""
    text = SPEC_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(\{\"action\".*?\})\n```", text)
    assert len(blocks) == 3
    hashes = (GOLDEN_1_HASH, GOLDEN_2_HASH, GOLDEN_3_HASH)
    for canonical, expected in zip(blocks, hashes, strict=True):
        assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == expected
        assert expected in text


# --- concordance on a real database ----------------------------------------


def test_record_hash_identical_on_every_row(tmp_path, verifier):
    db = _make_db(tmp_path / "a.db")
    rows = _rows(db)
    assert len(rows) == 6
    fields = _COLUMNS.split(", ")
    for row in rows:
        record = dict(zip(fields, row, strict=True))
        stored = record.pop("record_hash")
        previous = record["previous_hash"]
        lib = compute_record_hash(record, previous)
        std = verifier.compute_record_hash(record, previous)
        assert lib == std == stored


def test_healthy_chain_same_result(tmp_path, verifier):
    db = _make_db(tmp_path / "a.db")
    lib = verify_chain(db)
    valid, checked, first_bad, error = verifier.verify(db)
    assert (valid, checked, first_bad, error) == (
        lib.valid,
        lib.records_checked,
        lib.first_invalid_sequence,
        lib.error,
    )
    assert valid and checked == 6


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE verdicts SET decision='STOP' WHERE sequence=1",
        "UPDATE verdicts SET decision='CONTINUE' WHERE sequence=4",
        "UPDATE verdicts SET latency_ms=latency_ms+1 WHERE sequence=3",
        "UPDATE verdicts SET agent_id='forged' WHERE sequence=6",
        "UPDATE verdicts SET previous_hash='' WHERE sequence=2",
        "DELETE FROM verdicts WHERE sequence=3",
    ],
)
def test_tampered_chain_same_result(tmp_path, verifier, sql):
    db = _make_db(tmp_path / "a.db")
    _exec(db, sql)
    lib = verify_chain(db)
    valid, checked, first_bad, error = verifier.verify(db)
    assert not lib.valid and not valid
    assert first_bad == lib.first_invalid_sequence
    assert checked == lib.records_checked
    assert error == lib.error


def test_tail_truncation_is_not_detected(tmp_path, verifier):
    """Documented limit (spec section 7): a shortened chain is still valid."""
    db = _make_db(tmp_path / "a.db")
    _exec(db, "DELETE FROM verdicts WHERE sequence > 4")
    assert verify_chain(db).valid
    assert verifier.verify(db)[0] is True


# --- standalone script behaviour -------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VERIFIER), *args], capture_output=True, text=True)


def test_cli_exit_codes(tmp_path):
    db = _make_db(tmp_path / "a.db")
    ok = _run(db)
    assert ok.returncode == 0 and ok.stdout.strip() == "OK: chain valid (6 record(s) checked)"

    # sequence 1 is a CONTINUE (amount 100): flip it to STOP.
    _exec(db, "UPDATE verdicts SET decision='STOP' WHERE sequence=1")
    bad = _run(db)
    assert bad.returncode == 1
    assert "INVALID" in bad.stdout and "first invalid sequence: 1" in bad.stdout


def test_cli_exit_2_on_io_errors(tmp_path):
    missing = _run(str(tmp_path / "nope.db"))
    assert missing.returncode == 2 and "error:" in missing.stderr

    junk = tmp_path / "junk.db"
    junk.write_bytes(b"this is not a sqlite database" * 100)
    assert _run(str(junk)).returncode == 2

    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert _run(str(empty)).returncode == 2


def test_never_writes_to_database(tmp_path):
    db = Path(_make_db(tmp_path / "a.db"))
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    db.chmod(0o444)
    try:
        result = _run(str(db))
    finally:
        db.chmod(0o644)
    assert result.returncode == 0
    # The database file is byte-identical. (SQLite itself may create a
    # ``-shm`` side file when reading a WAL-mode database; that is not a
    # write to the database.)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_imports_are_stdlib_only():
    tree = ast.parse(VERIFIER.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "hashlib", "json", "sqlite3", "sys", "argparse"}, imported


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0.25, "0.25"),
        (2.0, "2.0"),
        (0.0, "0.0"),
        (0.0001, "0.0001"),
        (1e15, "1000000000000000.0"),
        (5e-05, "5e-05"),
        (1.5e-05, "1.5e-05"),
        (9.999e-05, "9.999e-05"),
        (1e16, "1e+16"),
        (123456789012345678.0, "1.2345678901234568e+17"),
    ],
)
def test_latency_float_rule_matches_spec(verifier, value, text):
    """Spec section 3, rule 4: the examples printed in the spec are what json.dumps emits."""
    import json

    assert json.dumps(value) == text
    payload = dict(GOLDEN_1, latency_ms=value)
    canonical = json.dumps(
        {**{k: v for k, v in payload.items()}, "previous_hash": GENESIS_HASH},
        sort_keys=True,
        separators=(",", ":"),
    )
    assert f'"latency_ms":{text},' in canonical
    assert hashlib.sha256(canonical.encode()).hexdigest() == verifier.compute_record_hash(
        payload, GENESIS_HASH
    )
