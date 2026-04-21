"""06 — gate an OpenAI Chat Completions ``tool_calls`` array.

This example uses a hand-built payload that mirrors the OpenAI API
response shape, so it runs offline. Replace it with the real
``response.choices[0].message.tool_calls`` in production.

Run::

    python examples/06_openai_adapter.py
"""

from __future__ import annotations

import json

from diplomat_gate import Gate
from diplomat_gate.adapters.openai import filter_allowed


def fake_openai_tool_calls() -> list[dict]:
    return [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "send_email",
                "arguments": json.dumps({"to": "ok@example.com", "body": "hi"}),
            },
        },
        {
            "id": "call_2",
            "type": "function",
            "function": {
                "name": "send_email",
                "arguments": json.dumps({"to": "boom@evil.com", "body": "hi"}),
            },
        },
    ]


def main() -> None:
    gate = Gate.from_dict({"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]})
    allowed_raw, review, blocked = filter_allowed(gate, fake_openai_tool_calls())
    print(f"allowed: {[c['id'] for c in allowed_raw]}")
    print(f"review:  {[c.tool_call.action for c in review]}")
    print(f"blocked: {[c.raw['id'] for c in blocked]}")
    # ``allowed_raw`` is the subset to forward to your tool-execution loop.


if __name__ == "__main__":
    main()
