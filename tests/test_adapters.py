"""Tests for framework adapters.

These tests use duck-typed fakes — no third-party SDKs are required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from diplomat_gate import Blocked, Gate, NeedsReview
from diplomat_gate.adapters import GatedCall
from diplomat_gate.adapters.anthropic import filter_allowed as anthropic_filter_allowed
from diplomat_gate.adapters.anthropic import (
    gate_tool_use_blocks,
    is_tool_use_block,
)
from diplomat_gate.adapters.anthropic import (
    to_tool_call as anthropic_to_tool_call,
)
from diplomat_gate.adapters.langchain import GatedTool, gated_callable, gated_tool
from diplomat_gate.adapters.openai import (
    filter_allowed as openai_filter_allowed,
)
from diplomat_gate.adapters.openai import (
    gate_tool_calls as openai_gate_tool_calls,
)
from diplomat_gate.adapters.openai import (
    to_tool_call as openai_to_tool_call,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _email_gate() -> Gate:
    return Gate.from_dict({"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]})


def _payment_gate() -> Gate:
    return Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]})


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class TestOpenAIAdapter:
    def test_to_tool_call_dict_shape(self):
        raw = {
            "id": "call_abc",
            "type": "function",
            "function": {"name": "send_email", "arguments": json.dumps({"to": "x@ok.com"})},
        }
        tc = openai_to_tool_call(raw, agent_id="agent-1")
        assert tc.action == "send_email"
        assert tc.params == {"to": "x@ok.com"}
        assert tc.agent_id == "agent-1"
        assert tc.context["openai_tool_call_id"] == "call_abc"

    def test_to_tool_call_object_shape(self):
        @dataclass
        class _Function:
            name: str
            arguments: str

        @dataclass
        class _Call:
            id: str
            function: _Function
            type: str = "function"

        raw = _Call(id="call_x", function=_Function(name="charge", arguments='{"amount": 50}'))
        tc = openai_to_tool_call(raw)
        assert tc.action == "charge"
        assert tc.params == {"amount": 50}
        assert tc.context["openai_tool_call_id"] == "call_x"

    def test_to_tool_call_invalid_arguments_preserved(self):
        raw = {
            "id": "1",
            "function": {"name": "noop", "arguments": "this is not json"},
        }
        tc = openai_to_tool_call(raw)
        assert tc.params == {"_raw_arguments": "this is not json"}

    def test_to_tool_call_missing_arguments(self):
        raw = {"id": "1", "function": {"name": "noop"}}
        tc = openai_to_tool_call(raw)
        assert tc.params == {}

    def test_gate_tool_calls_returns_wrapped(self):
        gate = _email_gate()
        calls = [
            {
                "id": "1",
                "function": {"name": "send_email", "arguments": json.dumps({"to": "x@ok.com"})},
            },
            {
                "id": "2",
                "function": {"name": "send_email", "arguments": json.dumps({"to": "x@evil.com"})},
            },
        ]
        results = openai_gate_tool_calls(gate, calls)
        assert len(results) == 2
        assert all(isinstance(r, GatedCall) for r in results)
        assert results[0].allowed is True
        assert results[1].blocked is True
        assert results[0].raw is calls[0]
        assert results[1].raw is calls[1]

    def test_filter_allowed_preserves_order(self):
        gate = _email_gate()
        calls = [
            {
                "id": "a",
                "function": {"name": "send_email", "arguments": json.dumps({"to": "ok@ok.com"})},
            },
            {
                "id": "b",
                "function": {"name": "send_email", "arguments": json.dumps({"to": "x@evil.com"})},
            },
            {
                "id": "c",
                "function": {"name": "send_email", "arguments": json.dumps({"to": "ok2@ok.com"})},
            },
        ]
        allowed, review, blocked = openai_filter_allowed(gate, calls)
        assert [c["id"] for c in allowed] == ["a", "c"]
        assert review == []
        assert len(blocked) == 1 and blocked[0].raw["id"] == "b"

    def test_empty_input_returns_empty(self):
        gate = _email_gate()
        assert openai_gate_tool_calls(gate, []) == []
        assert openai_gate_tool_calls(gate, None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class TestAnthropicAdapter:
    def test_is_tool_use_block(self):
        assert is_tool_use_block({"type": "tool_use", "id": "1", "name": "x", "input": {}})
        assert not is_tool_use_block({"type": "text", "text": "hello"})

    def test_to_tool_call_dict_shape(self):
        block = {
            "type": "tool_use",
            "id": "tu_1",
            "name": "send_email",
            "input": {"to": "x@ok.com"},
        }
        tc = anthropic_to_tool_call(block, agent_id="a1")
        assert tc.action == "send_email"
        assert tc.params == {"to": "x@ok.com"}
        assert tc.agent_id == "a1"
        assert tc.context["anthropic_tool_use_id"] == "tu_1"

    def test_to_tool_call_object_shape(self):
        @dataclass
        class _Block:
            id: str
            name: str
            input: dict[str, Any]
            type: str = "tool_use"

        block = _Block(id="tu_2", name="charge", input={"amount": 100})
        tc = anthropic_to_tool_call(block)
        assert tc.action == "charge"
        assert tc.params == {"amount": 100}

    def test_gate_skips_non_tool_use_blocks(self):
        gate = _email_gate()
        content = [
            {"type": "text", "text": "thinking..."},
            {"type": "tool_use", "id": "1", "name": "send_email", "input": {"to": "ok@ok.com"}},
            {"type": "text", "text": "done"},
            {"type": "tool_use", "id": "2", "name": "send_email", "input": {"to": "boom@evil.com"}},
        ]
        results = gate_tool_use_blocks(gate, content)
        assert len(results) == 2
        assert results[0].allowed and results[1].blocked

    def test_filter_allowed_returns_blocks_in_order(self):
        gate = _email_gate()
        content = [
            {"type": "tool_use", "id": "a", "name": "send_email", "input": {"to": "ok@ok.com"}},
            {"type": "tool_use", "id": "b", "name": "send_email", "input": {"to": "x@evil.com"}},
        ]
        allowed, review, blocked = anthropic_filter_allowed(gate, content)
        assert [b["id"] for b in allowed] == ["a"]
        assert review == [] and len(blocked) == 1

    def test_empty_content(self):
        gate = _email_gate()
        assert gate_tool_use_blocks(gate, []) == []
        assert gate_tool_use_blocks(gate, None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LangChain
# ---------------------------------------------------------------------------


class _FakeTool:
    """Minimal LangChain-tool-like object: ``name`` + ``invoke(input)``."""

    name = "send_email"
    description = "Send an email"

    def __init__(self):
        self.calls: list[Any] = []

    def invoke(self, tool_input):
        self.calls.append(tool_input)
        return {"sent": True, "input": tool_input}


class TestLangChainAdapter:
    def test_invoke_when_allowed(self):
        gate = _email_gate()
        tool = _FakeTool()
        wrapped = gated_tool(tool, gate)
        result = wrapped.invoke({"to": "ok@ok.com"})
        assert result == {"sent": True, "input": {"to": "ok@ok.com"}}
        assert len(tool.calls) == 1

    def test_invoke_blocked_raises(self):
        gate = _email_gate()
        tool = _FakeTool()
        wrapped = gated_tool(tool, gate)
        with pytest.raises(Blocked):
            wrapped.invoke({"to": "x@evil.com"})
        assert tool.calls == []  # underlying must NOT have been called

    def test_invoke_blocked_returns_when_configured(self):
        gate = _email_gate()
        tool = _FakeTool()
        wrapped = gated_tool(tool, gate, on_block="return")
        out = wrapped.invoke({"to": "x@evil.com"})
        assert isinstance(out, GatedCall) and out.blocked
        assert tool.calls == []

    def test_evaluate_does_not_invoke(self):
        gate = _email_gate()
        tool = _FakeTool()
        wrapped = gated_tool(tool, gate)
        call = wrapped.evaluate({"to": "ok@ok.com"})
        assert isinstance(call, GatedCall) and call.allowed
        assert tool.calls == []

    def test_review_raises_needs_review(self):
        gate = Gate.from_dict(
            {
                "email": [
                    {"id": "email.domain_blocklist", "blocked": ["*.evil.com"], "on_fail": "REVIEW"}
                ]
            }
        )
        wrapped = gated_tool(_FakeTool(), gate)
        with pytest.raises(NeedsReview):
            wrapped.invoke({"to": "x@evil.com"})

    def test_action_override(self):
        gate = _payment_gate()

        def charge(amount):
            return amount

        wrapped = gated_callable(charge, gate, action="charge_card")
        assert wrapped.invoke({"amount": 500}) == 500
        with pytest.raises(Blocked):
            wrapped.invoke({"amount": 5000})

    def test_callable_without_input(self):
        gate = _email_gate()

        def noop():
            return "ok"

        wrapped = gated_callable(noop, gate, action="send_email")
        assert wrapped.invoke() == "ok"

    def test_invalid_on_block_value(self):
        with pytest.raises(ValueError):
            GatedTool(_FakeTool(), _email_gate(), on_block="ignore")

    def test_falls_back_to_run(self):
        class _RunOnlyTool:
            name = "send_email"
            description = ""

            def __init__(self):
                self.received = None

            def run(self, tool_input):
                self.received = tool_input
                return "ran"

        gate = _email_gate()
        tool = _RunOnlyTool()
        wrapped = gated_tool(tool, gate)
        assert wrapped.invoke({"to": "ok@ok.com"}) == "ran"
        assert tool.received == {"to": "ok@ok.com"}
