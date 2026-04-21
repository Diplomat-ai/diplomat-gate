# Adapters

`diplomat-gate` ships three adapters that translate framework-specific
tool-call objects into the plain `ToolCall` shape the engine consumes:

- `diplomat_gate.adapters.openai` — for OpenAI Chat Completions
  `tool_calls` arrays.
- `diplomat_gate.adapters.anthropic` — for Anthropic Messages
  `content` blocks of type `tool_use`.
- `diplomat_gate.adapters.langchain` — for LangChain-style tools
  (`name` + `invoke()` / `run()` / `__call__`).

All adapters are **duck-typed**. They tolerate dicts, dataclass-like
SDK objects, and anything in between. Installing the underlying SDK is
**not** required.

## OpenAI

```python
from diplomat_gate.adapters.openai import (
    to_tool_call,
    gate_tool_calls,
    filter_allowed,
)

response = client.chat.completions.create(...)
tool_calls = response.choices[0].message.tool_calls

# Three lists: dicts/SDK objects safe to forward, REVIEWed wrappers, BLOCKED wrappers.
allowed_raw, review, blocked = filter_allowed(gate, tool_calls)

for raw in allowed_raw:
    dispatch_to_my_executor(raw)

for gc in review:
    enqueue_for_human(gc.tool_call, gc.verdict)

for gc in blocked:
    log_blocked(gc.tool_call, gc.verdict)
```

`to_tool_call(raw, agent_id="")` parses one item. Malformed JSON in
`function.arguments` is preserved under a `_raw_arguments` param rather
than swallowed. `openai_tool_call_id` is added to the verdict context.

## Anthropic

```python
from diplomat_gate.adapters.anthropic import filter_allowed

response = client.messages.create(...)
allowed_blocks, review, blocked = filter_allowed(gate, response.content)
```

The adapter only inspects blocks where `type == "tool_use"`; other
blocks (`text`, `image`, etc.) are returned untouched in the `allowed`
list. `anthropic_tool_use_id` is added to the verdict context.

## LangChain

`GatedTool` wraps any object that has a `name` attribute and one of
`invoke(input)`, `run(input)`, or `__call__(input)`.

```python
from diplomat_gate.adapters.langchain import gated_tool

safe_tool = gated_tool(my_langchain_tool, gate)
result = safe_tool.invoke({"to": "user@example.com", "body": "hi"})
```

By default `safe_tool.invoke(...)`:

- runs the gate first;
- on `STOP`, raises `Blocked(verdict)`;
- on `REVIEW`, raises `NeedsReview(verdict)`;
- on `CONTINUE`, dispatches to the wrapped tool.

To return the verdict instead of raising:

```python
gated_tool(my_tool, gate, on_block="return", on_review="return")
```

`evaluate()` runs only the gate (no tool dispatch) and is useful in
LangGraph nodes that want to fan out themselves.

`gated_callable(fn, gate, action=...)` wraps a plain Python function
the same way.

## Shared base

`diplomat_gate.adapters.base.GatedCall(raw, tool_call, verdict)` is the
common envelope. Convenience properties: `.allowed`, `.blocked`,
`.needs_review`. `partition(calls)` splits a sequence into three lists.

`dispatch(gate, tool_call, *, raw=None, raise_on_block=True)` is the
low-level helper used by every adapter. Passing `raise_on_block=False`
returns the `GatedCall` regardless of decision.

## Testing without SDKs

Every adapter is exercised in [`tests/test_adapters.py`](../tests/test_adapters.py)
using fakes built with `dataclass`. No SDK is installed in CI, so
nothing in `[openai]` / `[anthropic]` / `[langchain]` is required to
develop the adapters themselves. The SDK extras only matter when you
import the SDKs in your own application code.

## Adding a new adapter

The pattern is small and intentional:

1. Write a `to_tool_call(raw, agent_id="") -> ToolCall` function. Use
   `_get(obj, *names)` (in `adapters.base`) for the dict-or-attr access.
2. Write a `gate_tool_calls(gate, raw_calls) -> list[GatedCall]` that
   loops + calls `dispatch(gate, tc, raw=raw, raise_on_block=False)`.
3. Optionally provide a `filter_allowed(gate, raw_calls)` that returns
   the three-tuple `(allowed_raw, review, blocked)`.

Keep the adapter pure-Python and free of SDK imports at module load.
