"""Common helpers shared by every framework adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..engine import Gate
from ..exceptions import Blocked, NeedsReview
from ..models import Decision, ToolCall, Verdict


@dataclass
class GatedCall:
    """A single tool call paired with the gate verdict produced for it.

    ``raw`` is the original framework-specific payload (a dict from the
    OpenAI API, an ``anthropic`` ``ToolUseBlock``, a LangChain tool-input
    dict, …). ``tool_call`` is the normalized :class:`ToolCall` that was
    submitted to the gate. ``verdict`` is the resulting :class:`Verdict`.
    """

    raw: Any
    tool_call: ToolCall
    verdict: Verdict

    @property
    def allowed(self) -> bool:
        return self.verdict.decision == Decision.CONTINUE

    @property
    def blocked(self) -> bool:
        return self.verdict.decision == Decision.STOP

    @property
    def needs_review(self) -> bool:
        return self.verdict.decision == Decision.REVIEW


def dispatch(
    gate: Gate, tool_call: ToolCall, *, raw: Any = None, raise_on_block: bool = False
) -> GatedCall:
    """Evaluate ``tool_call`` against ``gate`` and wrap the result.

    When ``raise_on_block`` is true, a STOP verdict raises
    :class:`diplomat_gate.exceptions.Blocked` and a REVIEW verdict raises
    :class:`diplomat_gate.exceptions.NeedsReview`.
    """
    verdict = gate.evaluate(tool_call)
    call = GatedCall(
        raw=raw if raw is not None else tool_call, tool_call=tool_call, verdict=verdict
    )
    if raise_on_block:
        if call.blocked:
            raise Blocked(verdict)
        if call.needs_review:
            raise NeedsReview(verdict)
    return call


def partition(calls: list[GatedCall]) -> tuple[list[GatedCall], list[GatedCall], list[GatedCall]]:
    """Split a list of :class:`GatedCall` into ``(allowed, review, blocked)``."""
    allowed: list[GatedCall] = []
    review: list[GatedCall] = []
    blocked: list[GatedCall] = []
    for c in calls:
        if c.allowed:
            allowed.append(c)
        elif c.needs_review:
            review.append(c)
        else:
            blocked.append(c)
    return allowed, review, blocked
