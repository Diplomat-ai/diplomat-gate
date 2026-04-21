"""Local SQLite audit trail for gate verdicts.

Each row carries a monotonically increasing ``sequence`` and a SHA-256
``record_hash`` computed over the row contents and the previous row's
hash. Tampering with any historical row breaks the chain and is detected
by :func:`verify_chain`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SENSITIVE_FIELDS, Verdict

#: Sentinel ``previous_hash`` used by the very first record in a chain.
GENESIS_HASH: str = "0" * 64

#: Field order used to build the canonical JSON payload that is hashed.
_HASH_FIELDS: tuple[str, ...] = (
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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id TEXT PRIMARY KEY,
    sequence INTEGER NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    decision TEXT NOT NULL,
    policies_evaluated INTEGER NOT NULL,
    policies_failed INTEGER NOT NULL,
    violations TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_verdicts_decision ON verdicts(decision);
CREATE INDEX IF NOT EXISTS idx_verdicts_timestamp ON verdicts(timestamp);
CREATE INDEX IF NOT EXISTS idx_verdicts_sequence ON verdicts(sequence);
"""

_BUSY_RETRIES = 5
_BUSY_BASE_DELAY = 0.01


def _redact_value(value: object) -> str:
    """Return a short, deterministic hash marker for a sensitive value."""
    return "h:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _redact_violations(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hash sensitive context values inside each violation entry."""
    redacted: list[dict[str, Any]] = []
    for v in violations:
        v_copy = dict(v)
        ctx = dict(v_copy.get("context") or {})
        for key in list(ctx.keys()):
            if key in SENSITIVE_FIELDS:
                ctx[key] = _redact_value(ctx[key])
        v_copy["context"] = ctx
        redacted.append(v_copy)
    return redacted


def compute_record_hash(record: dict[str, Any], previous_hash: str) -> str:
    """Compute the SHA-256 record hash for ``record`` chained on ``previous_hash``.

    Pure function: same inputs always yield the same digest. The canonical
    JSON encoding uses ``sort_keys=True`` and the compact separators so the
    output is reproducible across platforms and Python versions.
    """
    payload = {name: record[name] for name in _HASH_FIELDS if name != "previous_hash"}
    payload["previous_hash"] = previous_hash
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ChainVerificationResult:
    """Outcome of :func:`verify_chain`."""

    valid: bool
    records_checked: int
    first_invalid_sequence: int | None
    error: str | None


class AuditLog:
    """Append-only, hash-chained SQLite audit log."""

    def __init__(
        self,
        path: str = "./diplomat-audit.db",
        *,
        redact_violations: bool = True,
    ):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._redact = redact_violations
        # ``isolation_level=None`` puts pysqlite in autocommit mode, which
        # lets us drive ``BEGIN IMMEDIATE`` / ``COMMIT`` ourselves without
        # the implicit transaction machinery interfering.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(verdicts)")}
        legacy_missing = {"sequence", "previous_hash", "record_hash"} - cols
        if legacy_missing:
            # Legacy schema (0.1.x): patch in the chain columns with safe
            # defaults so reads keep working. Existing rows stay un-chained
            # until ``rebuild_chain`` runs.
            for col, decl in (
                ("sequence", "INTEGER NOT NULL DEFAULT 0"),
                ("previous_hash", "TEXT NOT NULL DEFAULT ''"),
                ("record_hash", "TEXT NOT NULL DEFAULT ''"),
            ):
                if col in legacy_missing:
                    self._conn.execute(f"ALTER TABLE verdicts ADD COLUMN {col} {decl}")
            warnings.warn(
                "diplomat-gate: legacy audit schema migrated; existing rows are "
                "un-chained. Run `diplomat-gate audit rebuild-chain --db <path>` "
                "to compute sequence/previous_hash/record_hash for them.",
                UserWarning,
                stacklevel=3,
            )
        # Indexes are created last so they only reference columns that
        # exist after any in-place migration.
        self._conn.executescript(_INDEXES)

    # ------------------------------------------------------------------
    # write path
    # ------------------------------------------------------------------

    def record(self, verdict: Verdict) -> None:
        violations_payload = (
            _redact_violations(verdict.receipt.violations)
            if self._redact
            else verdict.receipt.violations
        )
        violations_json = json.dumps(violations_payload)

        last_error: Exception | None = None
        for attempt in range(_BUSY_RETRIES):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        row = self._conn.execute(
                            "SELECT sequence, record_hash FROM verdicts "
                            "WHERE record_hash != '' "
                            "ORDER BY sequence DESC LIMIT 1"
                        ).fetchone()
                        if row is None:
                            sequence = 1
                            previous_hash = GENESIS_HASH
                        else:
                            sequence = int(row[0]) + 1
                            previous_hash = row[1] or GENESIS_HASH

                        record = {
                            "verdict_id": verdict.receipt.verdict_id,
                            "sequence": sequence,
                            "timestamp": verdict.receipt.timestamp,
                            "agent_id": verdict.tool_call.agent_id,
                            "action": verdict.tool_call.action,
                            "params_hash": verdict.receipt.tool_call_hash,
                            "decision": verdict.decision.value,
                            "policies_evaluated": verdict.receipt.policies_evaluated,
                            "policies_failed": verdict.receipt.policies_failed,
                            "violations": violations_json,
                            "latency_ms": verdict.latency_ms,
                        }
                        record_hash = compute_record_hash(record, previous_hash)

                        self._conn.execute(
                            """INSERT INTO verdicts
                               (verdict_id, sequence, timestamp, agent_id, action,
                                params_hash, decision, policies_evaluated,
                                policies_failed, violations, latency_ms,
                                previous_hash, record_hash)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                record["verdict_id"],
                                sequence,
                                record["timestamp"],
                                record["agent_id"],
                                record["action"],
                                record["params_hash"],
                                record["decision"],
                                record["policies_evaluated"],
                                record["policies_failed"],
                                violations_json,
                                record["latency_ms"],
                                previous_hash,
                                record_hash,
                            ),
                        )
                        self._conn.execute("COMMIT")
                        return
                    except Exception:
                        self._conn.execute("ROLLBACK")
                        raise
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "locked" in msg or "busy" in msg:
                    last_error = exc
                    time.sleep(_BUSY_BASE_DELAY * (2**attempt))
                    continue
                raise
        assert last_error is not None  # for type-checkers
        raise sqlite3.OperationalError(
            f"audit log: SQLITE_BUSY after {_BUSY_RETRIES} retries"
        ) from last_error

    # ------------------------------------------------------------------
    # read path
    # ------------------------------------------------------------------

    def query(self, decision: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM verdicts"
        params: list[Any] = []
        if decision:
            sql += " WHERE decision = ?"
            params.append(decision)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cursor = self._conn.execute(sql, params)
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def count(self, decision: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM verdicts"
        params: list[Any] = []
        if decision:
            sql += " WHERE decision = ?"
            params.append(decision)
        with self._lock:
            return self._conn.execute(sql, params).fetchone()[0]

    def close(self) -> None:
        self._conn.close()


# ----------------------------------------------------------------------
# module-level helpers (used by the CLI and by external tooling)
# ----------------------------------------------------------------------


def _row_to_record(row: tuple) -> dict[str, Any]:
    (
        verdict_id,
        sequence,
        timestamp,
        agent_id,
        action,
        params_hash,
        decision,
        p_eval,
        p_fail,
        violations,
        latency_ms,
        previous_hash,
        _record_hash,
    ) = row
    return {
        "verdict_id": verdict_id,
        "sequence": int(sequence),
        "timestamp": timestamp,
        "agent_id": agent_id,
        "action": action,
        "params_hash": params_hash,
        "decision": decision,
        "policies_evaluated": int(p_eval),
        "policies_failed": int(p_fail),
        "violations": violations,
        "latency_ms": float(latency_ms),
        "previous_hash": previous_hash,
    }


_VERIFY_COLUMNS = (
    "verdict_id, sequence, timestamp, agent_id, action, params_hash, "
    "decision, policies_evaluated, policies_failed, violations, latency_ms, "
    "previous_hash, record_hash"
)


def verify_chain(db_path: str) -> ChainVerificationResult:
    """Verify the hash chain of an audit database.

    Read-only: this function does not mutate the database. Returns a
    :class:`ChainVerificationResult` describing the outcome.
    """
    conn = sqlite3.connect(db_path)
    try:
        try:
            rows = conn.execute(
                f"SELECT {_VERIFY_COLUMNS} FROM verdicts ORDER BY sequence ASC"
            ).fetchall()
        except sqlite3.OperationalError as exc:
            return ChainVerificationResult(False, 0, None, f"cannot read audit table: {exc}")
    finally:
        conn.close()

    expected_seq = 1
    expected_prev = GENESIS_HASH
    checked = 0
    for row in rows:
        record = _row_to_record(row)
        stored_record_hash = row[-1]
        if record["sequence"] != expected_seq:
            return ChainVerificationResult(
                valid=False,
                records_checked=checked,
                first_invalid_sequence=record["sequence"],
                error=f"sequence gap: expected {expected_seq}, got {record['sequence']}",
            )
        if record["previous_hash"] != expected_prev:
            return ChainVerificationResult(
                valid=False,
                records_checked=checked,
                first_invalid_sequence=record["sequence"],
                error=f"previous_hash mismatch at sequence {record['sequence']}",
            )
        computed = compute_record_hash(record, record["previous_hash"])
        if computed != stored_record_hash:
            return ChainVerificationResult(
                valid=False,
                records_checked=checked,
                first_invalid_sequence=record["sequence"],
                error=f"record_hash mismatch at sequence {record['sequence']}",
            )
        checked += 1
        expected_seq += 1
        expected_prev = stored_record_hash

    return ChainVerificationResult(
        valid=True, records_checked=checked, first_invalid_sequence=None, error=None
    )


def rebuild_chain(db_path: str) -> int:
    """Recompute ``sequence`` / ``previous_hash`` / ``record_hash`` for every row.

    Rows are re-numbered in (timestamp, rowid) ascending order. Returns the
    number of rows that were rewritten. Intended for migrations from the
    legacy 0.1.x schema or for explicit recovery after manual edits.
    """
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        rows = conn.execute(
            "SELECT verdict_id, timestamp, agent_id, action, params_hash, "
            "decision, policies_evaluated, policies_failed, violations, "
            "latency_ms FROM verdicts ORDER BY timestamp ASC, rowid ASC"
        ).fetchall()
        if not rows:
            return 0
        conn.execute("BEGIN IMMEDIATE")
        try:
            previous_hash = GENESIS_HASH
            for sequence, row in enumerate(rows, start=1):
                (
                    verdict_id,
                    timestamp,
                    agent_id,
                    action,
                    params_hash,
                    decision,
                    p_eval,
                    p_fail,
                    violations,
                    latency_ms,
                ) = row
                record = {
                    "verdict_id": verdict_id,
                    "sequence": sequence,
                    "timestamp": timestamp,
                    "agent_id": agent_id,
                    "action": action,
                    "params_hash": params_hash,
                    "decision": decision,
                    "policies_evaluated": int(p_eval),
                    "policies_failed": int(p_fail),
                    "violations": violations,
                    "latency_ms": float(latency_ms),
                }
                record_hash = compute_record_hash(record, previous_hash)
                conn.execute(
                    "UPDATE verdicts SET sequence = ?, previous_hash = ?, "
                    "record_hash = ? WHERE verdict_id = ?",
                    (sequence, previous_hash, record_hash, verdict_id),
                )
                previous_hash = record_hash
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return len(rows)
    finally:
        conn.close()
