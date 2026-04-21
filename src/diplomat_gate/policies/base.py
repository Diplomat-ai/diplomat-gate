"""Base policy class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..models import PolicyResult, ToolCall, Violation
from ..state import StateStore


@dataclass
class Policy(ABC):
    """Abstract base for all gate policies."""

    policy_id: str
    name: str
    domain: str  # "payment" | "email" | "any"
    severity: str = "high"
    on_fail: str = "STOP"  # "STOP" | "REVIEW"
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult: ...

    @abstractmethod
    def violation_message(self, tool_call: ToolCall) -> str: ...

    def make_violation(self, tool_call: ToolCall, result: PolicyResult) -> Violation:
        return Violation(
            policy_id=self.policy_id,
            policy_name=self.name,
            severity=self.severity,
            message=self.violation_message(tool_call),
            result=result.value,
        )

    def matches_domain(self, action: str) -> bool:
        if self.domain == "any":
            return True
        action_lower = action.lower()
        if self.domain == "payment":
            return any(
                kw in action_lower
                for kw in (
                    "pay",
                    "charge",
                    "invoice",
                    "refund",
                    "transfer",
                    "subscription",
                    "billing",
                    "stripe",
                    "payment",
                )
            )
        if self.domain == "email":
            return any(
                kw in action_lower
                for kw in (
                    "email",
                    "mail",
                    "smtp",
                    "sendmail",
                    "send_email",
                    "compose",
                    "draft",
                )
            )
        return False
