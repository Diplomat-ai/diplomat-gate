"""Human-in-the-loop review queue for ``REVIEW`` verdicts.

Backed by a separate SQLite database from the audit log so that operator
decisions (approve / reject) live in their own auditable table without
polluting the immutable hash chain. Each row stores enough information
to reconstruct the original verdict for an operator UI.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import _redact_violations
from .models import Verdict

#: Allowed values for the ``status`` column.
PENDING: str = "pending"
APPROVED: str = "approved"
REJECTED: str = "rejected"
EXPIRED: str = "expired"

_VALID_STATUSES = (PENDING, APPROVED, REJECTED, EXPIRED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_items (
    item_id TEXT PRIMARY KEY,
    verdict_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    agent_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    params TEXT NOT NULL,
    violations TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_items(status);
CREATE INDEX IF NOT EXISTS idx_review_created ON review_items(created_at);
"""


class ReviewQueueError(Exception):
    """Raised when an operation cannot be performed on a review item."""


@dataclass
class ReviewItem:
    """A pending or decided review entry."""

    item_id: str
    verdict_id: str
    created_at: str
    status: str
    agent_id: str
    action: str
    params: dict[str, Any]
    violations: list[dict[str, Any]]
    expires_at: float | None = None
    decided_at: str | None = None
    decided_by: str | None = None
    decision_note: str | None = None

    @property
    def pending(self) -> bool:
        return self.status == PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "verdict_id": self.verdict_id,
            "created_at": self.created_at,
            "status": self.status,
            "agent_id": self.agent_id,
            "action": self.action,
            "params": self.params,
            "violations": self.violations,
            "expires_at": self.expires_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "decision_note": self.decision_note,
        }


def _row_to_item(row: tuple) -> ReviewItem:
    (
        item_id,
        verdict_id,
        created_at,
        expires_at,
        status,
        agent_id,
        action,
        params,
        violations,
        decided_at,
        decided_by,
        decision_note,
    ) = row
    return ReviewItem(
        item_id=item_id,
        verdict_id=verdict_id,
        created_at=created_at,
        expires_at=expires_at,
        status=status,
        agent_id=agent_id,
        action=action,
        params=json.loads(params or "{}"),
        violations=json.loads(violations or "[]"),
        decided_at=decided_at,
        decided_by=decided_by,
        decision_note=decision_note,
    )


_SELECT_COLUMNS = (
    "item_id, verdict_id, created_at, expires_at, status, agent_id, action, "
    "params, violations, decided_at, decided_by, decision_note"
)


class ReviewQueue:
    """SQLite-backed queue for verdicts that require human approval."""

    def __init__(
        self,
        path: str = "./diplomat-review.db",
        *,
        redact_params: bool = True,
        ttl_seconds: float | None = None,
    ):
        """Open or create the queue database.

        ``redact_params`` mirrors the audit log: when true, sensitive
        fields inside the stored ``violations`` payload are hashed before
        persistence. The raw call is **not** stored beyond what the
        verdict already exposes — operators see what the gate saw.

        ``ttl_seconds`` sets a default expiry for newly enqueued items.
        Pass ``None`` to disable; pending items past their ``expires_at``
        become :data:`EXPIRED` on the next read or via :meth:`expire_due`.
        """
        self._path = Path(path)
        self._lock = threading.Lock()
        self._redact = redact_params
        self._ttl = ttl_seconds
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # write path
    # ------------------------------------------------------------------

    def enqueue(self, verdict: Verdict, *, ttl_seconds: float | None = None) -> str:
        """Persist ``verdict`` as a pending review item. Returns ``item_id``."""
        item_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        expires_at = (time.time() + ttl) if ttl is not None else None

        violations_payload = (
            _redact_violations(verdict.receipt.violations)
            if self._redact
            else verdict.receipt.violations
        )
        params_payload = dict(verdict.tool_call.params)
        if self._redact:
            from .audit import _redact_value
            from .models import SENSITIVE_FIELDS

            for key in list(params_payload.keys()):
                if key in SENSITIVE_FIELDS:
                    params_payload[key] = _redact_value(params_payload[key])

        with self._lock:
            self._conn.execute(
                """INSERT INTO review_items
                   (item_id, verdict_id, created_at, expires_at, status, agent_id,
                    action, params, violations)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    verdict.receipt.verdict_id,
                    created_at,
                    expires_at,
                    PENDING,
                    verdict.tool_call.agent_id,
                    verdict.tool_call.action,
                    json.dumps(params_payload, default=str),
                    json.dumps(violations_payload),
                ),
            )
        return item_id

    def approve(self, item_id: str, reviewer: str, *, note: str = "") -> ReviewItem:
        return self._decide(item_id, APPROVED, reviewer, note)

    def reject(self, item_id: str, reviewer: str, *, note: str = "") -> ReviewItem:
        return self._decide(item_id, REJECTED, reviewer, note)

    def _decide(self, item_id: str, status: str, reviewer: str, note: str) -> ReviewItem:
        decided_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            committed = False
            try:
                row = self._conn.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM review_items WHERE item_id = ?",
                    (item_id,),
                ).fetchone()
                if row is None:
                    raise ReviewQueueError(f"unknown review item: {item_id}")
                current = _row_to_item(row)
                if current.status != PENDING:
                    raise ReviewQueueError(
                        f"review item {item_id} is {current.status}, cannot transition"
                    )
                self._conn.execute(
                    "UPDATE review_items SET status = ?, decided_at = ?, "
                    "decided_by = ?, decision_note = ? WHERE item_id = ?",
                    (status, decided_at, reviewer, note, item_id),
                )
                self._conn.execute("COMMIT")
                committed = True
            finally:
                if not committed:
                    self._conn.execute("ROLLBACK")
        # Re-read with the new status.
        item = self.get(item_id)
        assert item is not None
        return item

    def expire_due(self, *, now: float | None = None) -> int:
        """Mark every overdue pending item as :data:`EXPIRED`. Returns the count."""
        now_ts = time.time() if now is None else now
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE review_items SET status = 'expired' "
                "WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at < ?",
                (now_ts,),
            )
            return cursor.rowcount or 0

    # ------------------------------------------------------------------
    # read path
    # ------------------------------------------------------------------

    def get(self, item_id: str) -> ReviewItem | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM review_items WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        return _row_to_item(row) if row else None

    def list(
        self,
        status: str | None = PENDING,
        *,
        limit: int = 100,
    ) -> list[ReviewItem]:
        """List items, newest first. Pass ``status=None`` to list every status."""
        if status is not None and status not in _VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {_VALID_STATUSES}")
        sql = f"SELECT {_SELECT_COLUMNS} FROM review_items"
        params: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_item(r) for r in rows]

    def count(self, status: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM review_items"
        params: list[Any] = []
        if status is not None:
            if status not in _VALID_STATUSES:
                raise ValueError(f"invalid status {status!r}")
            sql += " WHERE status = ?"
            params.append(status)
        with self._lock:
            return int(self._conn.execute(sql, params).fetchone()[0])

    def pending_count(self) -> int:
        return self.count(PENDING)

    def close(self) -> None:
        self._conn.close()


__all__ = [
    "ReviewQueue",
    "ReviewItem",
    "ReviewQueueError",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EXPIRED",
]
