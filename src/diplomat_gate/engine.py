"""Gate — the core evaluation engine."""

from __future__ import annotations

import time
from typing import Any

from .audit import AuditLog
from .models import Decision, PolicyResult, ToolCall, Verdict, Violation, _make_receipt
from .policies.base import Policy
from .policies.loader import load_from_dict, load_from_yaml
from .review import ReviewQueue
from .state import StateStore


class Gate:
    """Evaluates tool calls against policies. Returns Verdicts.

    Usage:
        gate = Gate.from_yaml("gate.yaml")
        verdict = gate.evaluate({"action": "charge_card", "amount": 15000})
    """

    def __init__(
        self,
        policies: list[Policy],
        audit_path: str | None = None,
        review_queue_path: str | None = None,
    ):
        self.policies = policies
        self.state = StateStore()
        self.audit = AuditLog(audit_path) if audit_path else None
        self.review_queue = ReviewQueue(review_queue_path) if review_queue_path else None

    @classmethod
    def from_yaml(
        cls, path: str, audit_path: str | None = None, review_queue_path: str | None = None
    ) -> Gate:
        policies = load_from_yaml(path)
        try:
            import yaml

            with open(path) as f:
                config = yaml.safe_load(f)
            if config.get("audit", {}).get("enabled") and audit_path is None:
                audit_path = config["audit"].get("path", "./diplomat-audit.db")
            if config.get("review_queue", {}).get("enabled") and review_queue_path is None:
                review_queue_path = config["review_queue"].get("path", "./diplomat-review.db")
        except ImportError:
            pass
        return cls(
            policies=policies,
            audit_path=audit_path,
            review_queue_path=review_queue_path,
        )

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
        audit_path: str | None = None,
        review_queue_path: str | None = None,
    ) -> Gate:
        policies = load_from_dict(config)
        if config.get("audit", {}).get("enabled") and audit_path is None:
            audit_path = config["audit"].get("path", "./diplomat-audit.db")
        if config.get("review_queue", {}).get("enabled") and review_queue_path is None:
            review_queue_path = config["review_queue"].get("path", "./diplomat-review.db")
        return cls(
            policies=policies,
            audit_path=audit_path,
            review_queue_path=review_queue_path,
        )

    def evaluate(self, tool_call: dict[str, Any] | ToolCall) -> Verdict:
        """Evaluate a tool call. Returns a Verdict.

        Resolution: STOP > REVIEW > CONTINUE (most severe wins).
        """
        start = time.perf_counter()

        tc = ToolCall.from_dict(tool_call) if isinstance(tool_call, dict) else tool_call

        violations: list[Violation] = []
        evaluated = 0
        stop = False
        review = False

        for policy in self.policies:
            if not policy.enabled or not policy.matches_domain(tc.action):
                continue
            evaluated += 1
            result = policy.evaluate(tc, self.state)
            if result in (PolicyResult.FAIL, PolicyResult.WARN):
                violations.append(policy.make_violation(tc, result))
                if policy.on_fail == "STOP":
                    stop = True
                elif policy.on_fail == "REVIEW":
                    review = True

        decision = Decision.STOP if stop else Decision.REVIEW if review else Decision.CONTINUE
        receipt = _make_receipt(tc, decision, violations, evaluated)
        latency = round((time.perf_counter() - start) * 1000, 3)

        verdict = Verdict(
            decision=decision,
            violations=violations,
            receipt=receipt,
            latency_ms=latency,
            tool_call=tc,
        )

        if self.audit:
            self.audit.record(verdict)
        if self.review_queue and decision == Decision.REVIEW:
            self.review_queue.enqueue(verdict)

        return verdict

    def close(self) -> None:
        if self.audit:
            self.audit.close()
        if self.review_queue:
            self.review_queue.close()
