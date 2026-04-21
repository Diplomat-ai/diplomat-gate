"""LangChain adapter — wrap a tool with gate enforcement.

This module is duck-typed: it does not import ``langchain`` or
``langchain_core`` at module load. Anything exposing a ``name`` attribute
and an ``invoke(input)`` method (or being a plain callable) can be
wrapped.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..engine import Gate
from ..exceptions import Blocked, NeedsReview
from ..models import ToolCall, Verdict
from .base import GatedCall, dispatch


def _coerce_input(tool_input: Any) -> dict[str, Any]:
    if tool_input is None:
        return {}
    if isinstance(tool_input, dict):
        return dict(tool_input)
    return {"_value": tool_input}


class GatedTool:
    """Wrap a LangChain-style tool so every invocation is gated.

    The wrapper exposes the same ``name`` / ``description`` attributes as
    the underlying tool plus an ``invoke(tool_input)`` method that runs
    the gate first. Behaviour on a non-CONTINUE verdict is controlled by
    ``on_block`` / ``on_review``:

    * ``"raise"`` (default): raise :class:`Blocked` / :class:`NeedsReview`.
    * ``"return"``: return the :class:`GatedCall` instead of executing
      the underlying tool.
    """

    def __init__(
        self,
        tool: Any,
        gate: Gate,
        *,
        action: str | None = None,
        agent_id: str = "",
        on_block: str = "raise",
        on_review: str = "raise",
    ):
        if on_block not in {"raise", "return"}:
            raise ValueError("on_block must be 'raise' or 'return'")
        if on_review not in {"raise", "return"}:
            raise ValueError("on_review must be 'raise' or 'return'")
        self._tool = tool
        self._gate = gate
        self._agent_id = agent_id
        self._on_block = on_block
        self._on_review = on_review
        self.name: str = action or getattr(tool, "name", None) or getattr(tool, "__name__", "tool")
        self.description: str = getattr(tool, "description", "")

    # ------------------------------------------------------------------
    # gate plumbing
    # ------------------------------------------------------------------

    def evaluate(self, tool_input: Any = None) -> GatedCall:
        """Run the gate without invoking the underlying tool."""
        params = _coerce_input(tool_input)
        tc = ToolCall(action=self.name, params=params, agent_id=self._agent_id)
        return dispatch(self._gate, tc, raw=tool_input)

    # ------------------------------------------------------------------
    # invocation
    # ------------------------------------------------------------------

    def invoke(self, tool_input: Any = None, **kwargs: Any) -> Any:
        call = self.evaluate(tool_input)
        if call.blocked:
            if self._on_block == "raise":
                raise Blocked(call.verdict)
            return call
        if call.needs_review:
            if self._on_review == "raise":
                raise NeedsReview(call.verdict)
            return call
        return _invoke_underlying(self._tool, tool_input, **kwargs)

    __call__ = invoke

    @property
    def last_verdict(self) -> Verdict | None:  # pragma: no cover - convenience
        return None


def _invoke_underlying(tool: Any, tool_input: Any, **kwargs: Any) -> Any:
    """Best-effort dispatch onto a LangChain-style tool or plain callable."""
    if hasattr(tool, "invoke"):
        return tool.invoke(tool_input, **kwargs) if kwargs else tool.invoke(tool_input)
    if hasattr(tool, "run"):
        return tool.run(tool_input, **kwargs) if kwargs else tool.run(tool_input)
    if callable(tool):
        if isinstance(tool_input, dict):
            return tool(**tool_input, **kwargs)
        if tool_input is None:
            return tool(**kwargs) if kwargs else tool()
        return tool(tool_input, **kwargs)
    raise TypeError(f"Cannot invoke object of type {type(tool).__name__!r}")


def gated_tool(
    tool: Any,
    gate: Gate,
    *,
    action: str | None = None,
    agent_id: str = "",
    on_block: str = "raise",
    on_review: str = "raise",
) -> GatedTool:
    """Functional helper around :class:`GatedTool`."""
    return GatedTool(
        tool,
        gate,
        action=action,
        agent_id=agent_id,
        on_block=on_block,
        on_review=on_review,
    )


def gated_callable(
    func: Callable[..., Any],
    gate: Gate,
    *,
    action: str | None = None,
    agent_id: str = "",
) -> Callable[..., Any]:
    """Wrap a plain callable so it is gated when called via ``f(**kwargs)``.

    Convenience for users who don't have a ``BaseTool`` instance handy.
    """
    return GatedTool(func, gate, action=action, agent_id=agent_id)


__all__ = ["GatedTool", "gated_tool", "gated_callable"]
