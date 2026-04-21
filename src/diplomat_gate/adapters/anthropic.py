"""Anthropic Messages API ``tool_use`` adapter.

Translates ``tool_use`` content blocks emitted by ``messages.create`` into
:class:`diplomat_gate.models.ToolCall` instances and evaluates them
through a :class:`Gate`. Works with both raw dicts and SDK objects with
``.type`` / ``.id`` / ``.name`` / ``.input``.
"""

from __future__ import annotations

from typing import Any

from ..engine import Gate
from ..models import ToolCall
from .base import GatedCall, dispatch, partition


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def is_tool_use_block(block: Any) -> bool:
    return _get(block, "type") == "tool_use"


def to_tool_call(block: Any, *, agent_id: str = "") -> ToolCall:
    """Translate a single Anthropic ``tool_use`` block into a :class:`ToolCall`."""
    name = _get(block, "name", default="") or ""
    raw_input = _get(block, "input", default=None)
    if isinstance(raw_input, dict):
        params = raw_input
    elif raw_input is None:
        params = {}
    else:
        params = {"_value": raw_input}
    block_id = _get(block, "id", default="")
    context: dict[str, Any] = {}
    if block_id:
        context["anthropic_tool_use_id"] = block_id
    return ToolCall(action=str(name), params=dict(params), agent_id=agent_id, context=context)


def gate_tool_use_blocks(gate: Gate, content: list[Any], *, agent_id: str = "") -> list[GatedCall]:
    """Evaluate every ``tool_use`` block in ``content`` (other blocks are skipped).

    The Anthropic Messages API returns a heterogeneous list of content
    blocks (``text``, ``tool_use``, …); only the ``tool_use`` blocks are
    forwarded to the gate. The order of the returned list matches the
    order of the matching blocks in ``content``.
    """
    results: list[GatedCall] = []
    for block in content or []:
        if not is_tool_use_block(block):
            continue
        tc = to_tool_call(block, agent_id=agent_id)
        results.append(dispatch(gate, tc, raw=block))
    return results


def filter_allowed(
    gate: Gate, content: list[Any], *, agent_id: str = ""
) -> tuple[list[Any], list[GatedCall], list[GatedCall]]:
    """Convenience: return ``(allowed_raw_blocks, review, blocked)``."""
    gated = gate_tool_use_blocks(gate, content, agent_id=agent_id)
    allowed, review, blocked = partition(gated)
    return [c.raw for c in allowed], review, blocked


__all__ = [
    "to_tool_call",
    "gate_tool_use_blocks",
    "filter_allowed",
    "is_tool_use_block",
]
