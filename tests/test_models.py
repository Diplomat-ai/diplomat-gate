"""Tests for core data models."""

from diplomat_gate.models import Decision, ToolCall, Verdict, _make_receipt


class TestToolCall:
    def test_from_dict_basic(self):
        tc = ToolCall.from_dict({"action": "charge_card", "amount": 100})
        assert tc.action == "charge_card"
        assert tc.params == {"amount": 100}
        assert tc.agent_id == ""

    def test_from_dict_extracts_agent_id(self):
        tc = ToolCall.from_dict({"action": "pay", "amount": 50, "agent_id": "agent-1"})
        assert tc.agent_id == "agent-1"
        assert "agent_id" not in tc.params

    def test_from_dict_extracts_context(self):
        tc = ToolCall.from_dict({"action": "pay", "context": {"session": "abc"}})
        assert tc.context == {"session": "abc"}
        assert "context" not in tc.params

    def test_hash_deterministic(self):
        tc = ToolCall(action="charge_card", params={"amount": 100}, agent_id="a1")
        assert tc.hash() == tc.hash()

    def test_hash_differs_on_amount(self):
        h1 = ToolCall(action="charge_card", params={"amount": 100}).hash()
        h2 = ToolCall(action="charge_card", params={"amount": 200}).hash()
        assert h1 != h2


class TestDecision:
    def test_values(self):
        assert Decision.CONTINUE.value == "CONTINUE"
        assert Decision.REVIEW.value == "REVIEW"
        assert Decision.STOP.value == "STOP"


class TestVerdict:
    def _make(self, decision: Decision) -> Verdict:
        tc = ToolCall(action="pay", params={})
        receipt = _make_receipt(tc, decision, [], 1)
        return Verdict(
            decision=decision, violations=[], receipt=receipt, latency_ms=1.0, tool_call=tc
        )

    def test_allowed(self):
        assert self._make(Decision.CONTINUE).allowed

    def test_blocked(self):
        assert self._make(Decision.STOP).blocked

    def test_needs_review(self):
        assert self._make(Decision.REVIEW).needs_review

    def test_to_dict(self):
        v = self._make(Decision.CONTINUE)
        d = v.to_dict()
        assert d["decision"] == "CONTINUE"
        assert "receipt" in d
