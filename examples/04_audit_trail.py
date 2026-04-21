"""04 — persistent audit trail with hash-chain verification.

Writes to a temporary SQLite database, evaluates a few tool calls, then
verifies the hash chain via the public API. The same can be done from
the shell with::

    diplomat-gate audit verify --db <path>

Run::

    python examples/04_audit_trail.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from diplomat_gate import Gate
from diplomat_gate.audit import verify_chain


def main() -> None:
    db = Path(tempfile.gettempdir()) / "diplomat-gate-example-04.db"
    db.unlink(missing_ok=True)
    print(f"audit db: {db}")

    gate = Gate.from_dict(
        {"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]},
        audit_path=str(db),
    )
    for amount in (100, 500, 1500, 800):
        gate.evaluate({"action": "charge_card", "amount": amount, "agent_id": "demo"})
    gate.close()

    result = verify_chain(str(db))
    print(
        f"chain valid={result.valid} records={result.records_checked} "
        f"first_invalid={result.first_invalid_sequence}"
    )


if __name__ == "__main__":
    main()
