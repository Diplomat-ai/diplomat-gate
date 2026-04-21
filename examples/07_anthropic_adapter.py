"""07 — gate Anthropic ``tool_use`` content blocks.

Runs offline with hand-built blocks that mirror what the Anthropic
Messages API returns alongside ``text`` blocks. Only ``tool_use`` blocks
are forwarded to the gate; everything else is left untouched.

Run::

    python examples/07_anthropic_adapter.py
"""

from __future__ import annotations

from diplomat_gate import Gate
from diplomat_gate.adapters.anthropic import filter_allowed


def fake_anthropic_content() -> list[dict]:
    return [
        {"type": "text", "text": "thinking..."},
        {
            "type": "tool_use",
            "id": "tu_1",
            "name": "charge_card",
            "input": {"amount": 200, "customer_id": "cus_1"},
        },
        {"type": "text", "text": "and then..."},
        {
            "type": "tool_use",
            "id": "tu_2",
            "name": "charge_card",
            "input": {"amount": 5000, "customer_id": "cus_2"},
        },
    ]


def main() -> None:
    gate = Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]})
    allowed_blocks, review, blocked = filter_allowed(gate, fake_anthropic_content())
    print(f"allowed: {[b['id'] for b in allowed_blocks]}")
    print(f"review:  {[c.tool_call.action for c in review]}")
    print(f"blocked: {[c.raw['id'] for c in blocked]}")


if __name__ == "__main__":
    main()
