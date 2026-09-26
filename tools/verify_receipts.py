#!/usr/bin/env python3
"""Standalone verifier for diplomat-gate audit receipts (receipt format v1).

Single file, Python standard library only. It does NOT require
``diplomat-gate`` to be installed, so an external auditor can run it on
an audit database with nothing but a Python 3 interpreter::

    python verify_receipts.py <audit.db>

The format it verifies is specified in ``docs/receipt-format.md``.

Exit codes (same as ``diplomat-gate audit verify``):
    0 - chain is valid
    1 - chain is invalid (tampering or corruption)
    2 - usage error, or the database cannot be opened / read

The database is opened read-only and is never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys

RECEIPT_FORMAT_VERSION = "1"

#: ``previous_hash`` of the first record of a chain.
GENESIS_HASH = "0" * 64

#: Fields covered by the hash (the *set* of keys; serialization order is
#: alphabetical, see docs/receipt-format.md).
HASH_FIELDS = (
    "verdict_id",
    "sequence",
    "timestamp",
    "agent_id",
    "action",
    "params_hash",
    "decision",
    "policies_evaluated",
    "policies_failed",
    "violations",
    "latency_ms",
    "previous_hash",
)

_COLUMNS = ", ".join((*HASH_FIELDS, "record_hash"))


def compute_record_hash(record: dict, previous_hash: str) -> str:
    """SHA-256 (hex) of the canonical JSON of ``record`` chained on ``previous_hash``."""
    payload = {name: record[name] for name in HASH_FIELDS if name != "previous_hash"}
    payload["previous_hash"] = previous_hash
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify(db_path: str) -> tuple[bool, int, int | None, str | None]:
    """Return ``(valid, records_checked, first_invalid_sequence, error)``.

    Raises ``sqlite3.Error`` if the database cannot be opened or read.
    """
    uri = "file:" + db_path.replace("?", "%3f").replace("#", "%23") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(f"SELECT {_COLUMNS} FROM verdicts ORDER BY sequence ASC").fetchall()
    finally:
        conn.close()

    expected_seq = 1
    expected_prev = GENESIS_HASH
    checked = 0
    for row in rows:
        record = dict(zip(HASH_FIELDS, row[:-1], strict=True))
        stored_hash = row[-1]
        seq = record["sequence"]
        if seq != expected_seq:
            return False, checked, seq, f"sequence gap: expected {expected_seq}, got {seq}"
        if record["previous_hash"] != expected_prev:
            return False, checked, seq, f"previous_hash mismatch at sequence {seq}"
        if compute_record_hash(record, record["previous_hash"]) != stored_hash:
            return False, checked, seq, f"record_hash mismatch at sequence {seq}"
        checked += 1
        expected_seq += 1
        expected_prev = stored_hash
    return True, checked, None, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_receipts.py",
        description="Verify the hash chain of a diplomat-gate audit database (read-only).",
    )
    parser.add_argument("db", help="path to the audit SQLite database")
    args = parser.parse_args(argv)

    try:
        valid, checked, first_bad, error = verify(args.db)
    except sqlite3.Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if valid:
        print(f"OK: chain valid ({checked} record(s) checked)")
        return 0
    print(
        f"INVALID: {error} (first invalid sequence: {first_bad}, "
        f"checked {checked} record(s) before failure)"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
