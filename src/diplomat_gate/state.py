"""In-memory state store for stateful policies (rate limits, velocity, dedup).

Thread-safe. State is lost on process restart — intentional for the open-source
version. Diplomat hosted uses persistent storage.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Entry:
    timestamps: list[float] = field(default_factory=list)


class StateStore:
    """Simple in-memory store keyed by (policy_id, scope)."""

    def __init__(self):
        self._data: dict[str, _Entry] = defaultdict(_Entry)
        self._lock = threading.Lock()

    def _key(self, policy_id: str, scope: str) -> str:
        return f"{policy_id}:{scope}"

    def record_event(self, policy_id: str, scope: str) -> None:
        key = self._key(policy_id, scope)
        with self._lock:
            self._data[key].timestamps.append(time.time())

    def count_events(self, policy_id: str, scope: str, window_seconds: float) -> int:
        key = self._key(policy_id, scope)
        cutoff = time.time() - window_seconds
        with self._lock:
            entry = self._data[key]
            entry.timestamps = [t for t in entry.timestamps if t > cutoff]
            return len(entry.timestamps)

    def last_event_time(self, policy_id: str, scope: str) -> float | None:
        key = self._key(policy_id, scope)
        with self._lock:
            entry = self._data[key]
            return entry.timestamps[-1] if entry.timestamps else None

    def find_duplicate(self, policy_id: str, scope: str, window_seconds: float) -> bool:
        return self.count_events(policy_id, scope, window_seconds) > 0

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
