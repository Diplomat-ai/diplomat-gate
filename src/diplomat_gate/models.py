"""Core data models — ToolCall, Verdict, Violation, Receipt, Decision, PolicyResult."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

#: Parameter keys whose values are considered sensitive and may be redacted
#: by the audit log before persistence. Mutable on purpose: integrators can
#: extend (or restrict) the list at runtime, e.g.
#: ``diplomat_gate.models.SENSITIVE_FIELDS.append("ssn")``.
SENSITIVE_FIELDS: list[str] = [
    "recipient",
    "to",
    "email",
    "domain",
    "amount",
    "card_last4",
    "phone",
]


class Decision(str, Enum):
    """The three possible gate verdicts."""

    CONTINUE = "CONTINUE"
    REVIEW = "REVIEW"
    STOP = "STOP"


class PolicyResult(str, Enum):
    """Result of a single policy evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ToolCall:
    """What the agent wants to do.

    Can be constructed from a dict for convenience:
        ToolCall.from_dict({"action": "charge_card", "amount": 15000})
    """

    action: str
    params: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ToolCall:
        """Build a ToolCall from a flat dict.

        The 'action' key is required. All other keys become params,
        except 'agent_id' and 'context' which are extracted if present.
        """
        d = dict(d)  # shallow copy so we don't mutate the caller's dict
        action = d.pop("action", "")
        agent_id = d.pop("agent_id", "")
        context = d.pop("context", {})
        return cls(
            action=action,
            params=d,
            agent_id=str(agent_id),
            context=context if isinstance(context, dict) else {},
        )

    def hash(self) -> str:
        """SHA-256 of the canonical JSON representation."""
        canonical = json.dumps(
            {"action": self.action, "params": self.params, "agent_id": self.agent_id},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class Violation:
    """A single policy that failed or warned."""

    policy_id: str
    policy_name: str
    severity: str
    message: str
    result: str = "FAIL"


@dataclass
class Receipt:
    """Proof of a gate decision. Immutable after creation."""

    verdict_id: str
    timestamp: str
    tool_call_hash: str
    decision: str
    policies_evaluated: int
    policies_failed: int
    violations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "timestamp": self.timestamp,
            "tool_call_hash": self.tool_call_hash,
            "decision": self.decision,
            "policies_evaluated": self.policies_evaluated,
            "policies_failed": self.policies_failed,
            "violations": self.violations,
        }


@dataclass
class Verdict:
    """The complete result of a gate evaluation."""

    decision: Decision
    violations: list[Violation]
    receipt: Receipt
    latency_ms: float
    tool_call: ToolCall

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.CONTINUE

    @property
    def blocked(self) -> bool:
        return self.decision == Decision.STOP

    @property
    def needs_review(self) -> bool:
        return self.decision == Decision.REVIEW

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "violations": [
                {
                    "policy_id": v.policy_id,
                    "policy_name": v.policy_name,
                    "severity": v.severity,
                    "message": v.message,
                }
                for v in self.violations
            ],
            "receipt": self.receipt.to_dict(),
            "latency_ms": self.latency_ms,
        }


def _make_receipt(
    tool_call: ToolCall,
    decision: Decision,
    violations: list[Violation],
    policies_evaluated: int,
) -> Receipt:
    """Factory to create a Receipt from evaluation results."""
    context = {k: tool_call.params[k] for k in SENSITIVE_FIELDS if k in tool_call.params}
    return Receipt(
        verdict_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool_call_hash=tool_call.hash(),
        decision=decision.value,
        policies_evaluated=policies_evaluated,
        policies_failed=len([v for v in violations if v.result == "FAIL"]),
        violations=[
            {
                "policy_id": v.policy_id,
                "severity": v.severity,
                "message": v.message,
                "context": dict(context),
            }
            for v in violations
        ],
    )
