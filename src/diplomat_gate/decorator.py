"""@gate() decorator for wrapping functions with automatic policy evaluation."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from .engine import Gate
from .exceptions import Blocked, NeedsReview
from .models import Decision

_default_gate: Gate | None = None


def configure(gate: Gate) -> None:
    """Set the module-level default Gate used by @gate() decorators."""
    global _default_gate
    _default_gate = gate


def gate(
    *,
    action: str = "",
    domain: str = "auto",
    gate_instance: Gate | None = None,
    param_map: dict[str, str] | None = None,
) -> Callable:
    """Decorator: evaluates gate before function execution.

    On CONTINUE → function runs normally.
    On STOP     → raises Blocked(verdict).
    On REVIEW   → raises NeedsReview(verdict).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            g = gate_instance or _default_gate
            if g is None:
                raise RuntimeError("No Gate configured. Call diplomat_gate.configure(gate) first.")

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            params = dict(bound.arguments)

            if param_map:
                params = {param_map.get(k, k): v for k, v in params.items()}

            act = action or func.__name__
            if domain != "auto" and domain not in act.lower():
                act = f"{domain}_{act}"

            verdict = g.evaluate({"action": act, **params})

            if verdict.decision == Decision.STOP:
                raise Blocked(verdict)
            if verdict.decision == Decision.REVIEW:
                raise NeedsReview(verdict)

            return func(*args, **kwargs)

        return wrapper

    return decorator
