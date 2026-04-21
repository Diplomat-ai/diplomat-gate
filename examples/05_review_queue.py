"""05 — human-in-the-loop review queue.

A REVIEW verdict is auto-enqueued. We then act as the operator, list
pending items, approve one and reject another. The same operations are
available from the shell::

    diplomat-gate review list    --db <path>
    diplomat-gate review approve --db <path> --id <item_id> --reviewer alice

Run::

    python examples/05_review_queue.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from diplomat_gate import Gate


def main() -> None:
    db = Path(tempfile.gettempdir()) / "diplomat-gate-example-05.db"
    db.unlink(missing_ok=True)
    print(f"review db: {db}")

    gate = Gate.from_dict(
        {
            "email": [
                {
                    "id": "email.domain_blocklist",
                    "blocked": ["*.review.com"],
                    "on_fail": "REVIEW",
                }
            ]
        },
        review_queue_path=str(db),
    )

    for to in ("alice@hold.review.com", "bob@hold.review.com"):
        verdict = gate.evaluate({"action": "send_email", "to": to})
        print(f"to={to} -> {verdict.decision.value}")

    pending = gate.review_queue.list()
    print(f"pending: {len(pending)}")

    approved = gate.review_queue.approve(pending[0].item_id, reviewer="alice", note="ok")
    rejected = gate.review_queue.reject(pending[1].item_id, reviewer="alice", note="suspicious")
    print(f"approved {approved.item_id} ({approved.status})")
    print(f"rejected {rejected.item_id} ({rejected.status})")
    print(f"pending now: {gate.review_queue.pending_count()}")
    gate.close()


if __name__ == "__main__":
    main()
