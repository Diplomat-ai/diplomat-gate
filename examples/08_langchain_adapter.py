"""08 — wrap a LangChain-style tool with GatedTool.

This example uses a tiny duck-typed fake (``name`` + ``invoke()``) so it
runs without ``langchain-core`` installed. Anything that quacks like a
LangChain ``BaseTool`` can be wrapped the same way.

Run::

    python examples/08_langchain_adapter.py
"""

from __future__ import annotations

from diplomat_gate import Blocked, Gate
from diplomat_gate.adapters.langchain import gated_tool


class SendEmailTool:
    name = "send_email"
    description = "Send an email to a recipient."

    def invoke(self, tool_input: dict) -> dict:
        # In real life: actually send the email. Here we just echo.
        return {"sent": True, "to": tool_input["to"]}


def main() -> None:
    gate = Gate.from_dict({"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]})
    tool = gated_tool(SendEmailTool(), gate)

    print(tool.invoke({"to": "ok@example.com"}))
    try:
        tool.invoke({"to": "boom@evil.com"})
    except Blocked as exc:
        print(f"blocked: {[v.policy_id for v in exc.verdict.violations]}")


if __name__ == "__main__":
    main()
