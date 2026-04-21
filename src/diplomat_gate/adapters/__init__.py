"""Framework adapters — translate third-party tool-call shapes into ``ToolCall``.

Each submodule depends only on ``diplomat_gate`` itself; the third-party
SDKs (``openai``, ``anthropic``, ``langchain-core``) are optional and only
needed if you actually use their convenience helpers. Translation
functions accept duck-typed objects (dicts or SDK message objects) so that
unit tests do not need the SDKs installed.
"""

from __future__ import annotations

from .base import GatedCall, dispatch

__all__ = ["GatedCall", "dispatch"]
