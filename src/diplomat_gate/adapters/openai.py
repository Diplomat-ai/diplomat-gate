"""OpenAI Chat Completions tool-call adapter.

Translates the ``tool_calls`` array returned by ``chat.completions`` into
:class:`diplomat_gate.models.ToolCall` instances and runs them through a
:class:`Gate`. Works with both raw dicts (as returned by the HTTP API)
and the SDK's pydantic objects (anything that exposes ``.id``,
``.function.name``, ``.function.arguments``).
"""

from __future__ import annotations

import json
from typing import Any

from ..engine import Gate
from ..models import ToolCall
from .base import GatedCall, dispatch, partition


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first attribute or dict key found among ``names``."""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, (str, bytes)):
        try:
            parsed = json.loads(arguments)
        except (ValueError, TypeError):
            return {
                "_raw_arguments": arguments
                if isinstance(arguments, str)
                else arguments.decode("utf-8", "replace")
            }
        return parsed if isinstance(parsed, dict) else {"_value": parsed}
    return {"_value": arguments}


def to_tool_call(raw: Any, *, agent_id: str = "") -> ToolCall:
    """Translate a single OpenAI tool call into a :class:`ToolCall`.

    Accepts either the raw API dict shape::

        {"id": "...", "type": "function",
         "function": {"name": "send_email", "arguments": "{\\"to\\": ...}"}}

    or any object exposing ``.id`` / ``.function.name`` /
    ``.function.arguments``.
    """
    function = _get(raw, "function", default={})
    name = _get(function, "name", default="") or ""
    arguments = _get(function, "arguments", default=None)
    params = _parse_arguments(arguments)
    call_id = _get(raw, "id", default="")
    context: dict[str, Any] = {}
    if call_id:
        context["openai_tool_call_id"] = call_id
    return ToolCall(action=str(name), params=params, agent_id=agent_id, context=context)


def gate_tool_calls(gate: Gate, tool_calls: list[Any], *, agent_id: str = "") -> list[GatedCall]:
    """Evaluate every tool call in ``tool_calls`` and return wrapped results.

    The order of the returned list matches the input. Use
    :func:`diplomat_gate.adapters.base.partition` to split into allowed /
    review / blocked groups.
    """
    results: list[GatedCall] = []
    for raw in tool_calls or []:
        tc = to_tool_call(raw, agent_id=agent_id)
        results.append(dispatch(gate, tc, raw=raw))
    return results


def filter_allowed(
    gate: Gate, tool_calls: list[Any], *, agent_id: str = ""
) -> tuple[list[Any], list[GatedCall], list[GatedCall]]:
    """Convenience: return ``(allowed_raw, review, blocked)``.

    ``allowed_raw`` is the subset of the original ``tool_calls`` that passed
    the gate, in the original order — ready to be handed back to the
    OpenAI tool-execution loop. ``review`` and ``blocked`` are the
    corresponding :class:`GatedCall` lists.
    """
    gated = gate_tool_calls(gate, tool_calls, agent_id=agent_id)
    allowed, review, blocked = partition(gated)
    return [c.raw for c in allowed], review, blocked


__all__ = ["to_tool_call", "gate_tool_calls", "filter_allowed"]
