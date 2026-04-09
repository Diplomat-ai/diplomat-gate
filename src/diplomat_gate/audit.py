"""Local SQLite audit trail for gate verdicts."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import Verdict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    agent_id TEXT DEFAULT '',
    action TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    decision TEXT NOT NULL,
    policies_evaluated INTEGER NOT NULL,
    policies_failed INTEGER NOT NULL,
    violations TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_verdicts_decision ON verdicts(decision);
CREATE INDEX IF NOT EXISTS idx_verdicts_timestamp ON verdicts(timestamp);
"""


class AuditLog:
    def __init__(self, path: str = "./diplomat-audit.db"):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, verdict: Verdict) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO verdicts
                   (verdict_id, timestamp, agent_id, action, params_hash,
                    decision, policies_evaluated, policies_failed,
                    violations, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    verdict.receipt.verdict_id,
                    verdict.receipt.timestamp,
                    verdict.tool_call.agent_id,
                    verdict.tool_call.action,
                    verdict.receipt.tool_call_hash,
                    verdict.decision.value,
                    verdict.receipt.policies_evaluated,
                    verdict.receipt.policies_failed,
                    json.dumps(verdict.receipt.violations),
                    verdict.latency_ms,
                ),
            )
            self._conn.commit()

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
