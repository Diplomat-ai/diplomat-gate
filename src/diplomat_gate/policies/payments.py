"""Payment policies — amount limit, velocity, daily limit, duplicate detection, recipient blocklist."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from ..models import PolicyResult, ToolCall
from ..state import StateStore
from .base import Policy


def _parse_window(window: str) -> float:
    window = window.strip().lower()
    if window.endswith("h"):
        return float(window[:-1]) * 3600
    if window.endswith("m"):
        return float(window[:-1]) * 60
    if window.endswith("s"):
        return float(window[:-1])
    if window.endswith("d"):
        return float(window[:-1]) * 86400
    return float(window)


def _get_amount(tool_call: ToolCall) -> float:
    amount = tool_call.params.get("amount", 0)
    return float(amount) if isinstance(amount, (str, int, float)) else 0.0


def _get_recipient(tool_call: ToolCall) -> str:
    for key in ("customer_id", "recipient", "to", "destination", "account"):
        val = tool_call.params.get(key, "")
        if val:
            return str(val)
    return ""


@dataclass
class AmountLimitPolicy(Policy):
    max_amount: float = 10_000
    currency: str = ""

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        amount = _get_amount(tool_call)
        if self.currency and tool_call.params.get("currency", "").lower() != self.currency.lower():
            return PolicyResult.PASS
        return PolicyResult.FAIL if amount > self.max_amount else PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        amount = _get_amount(tool_call)
        cur = f" {self.currency.upper()}" if self.currency else ""
        return f"Amount {amount} exceeds limit of {self.max_amount}{cur}"


@dataclass
class VelocityPolicy(Policy):
    max_txn: int = 20
    window: str = "1h"

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        window_s = _parse_window(self.window)
        scope = tool_call.agent_id or "_global"
        count = state.count_events(self.policy_id, scope, window_s)
        if count >= self.max_txn:
            return PolicyResult.FAIL
        state.record_event(self.policy_id, scope)
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return f"Velocity limit exceeded: max {self.max_txn} transactions per {self.window}"


@dataclass
class DailyLimitPolicy(Policy):
    max_daily: float = 50_000

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        amount = _get_amount(tool_call)
        scope = f"{tool_call.agent_id or '_global'}:daily_sum"
        current = state.sum_values(self.policy_id, scope, 86400.0)
        if current + amount > self.max_daily:
            return PolicyResult.FAIL
        state.record_value(self.policy_id, scope, amount)
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return f"Daily spending limit of {self.max_daily} would be exceeded"


@dataclass
class DuplicateDetectionPolicy(Policy):
    window: str = "5m"

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        amount = _get_amount(tool_call)
        recipient = _get_recipient(tool_call)
        scope = f"{amount}:{recipient}"
        window_s = _parse_window(self.window)
        if state.find_duplicate(self.policy_id, scope, window_s):
            return PolicyResult.FAIL
        state.record_event(self.policy_id, scope)
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return f"Duplicate transaction detected within {self.window}"


@dataclass
class RecipientBlocklistPolicy(Policy):
    blocked: list[str] = field(default_factory=list)

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        recipient = _get_recipient(tool_call)
        if not recipient:
            return PolicyResult.PASS
        for pattern in self.blocked:
            if fnmatch.fnmatch(recipient.lower(), pattern.lower()):
                return PolicyResult.FAIL
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return f"Recipient '{_get_recipient(tool_call)}' is on the blocklist"
