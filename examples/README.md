# diplomat-gate examples

Each script in this directory is self-contained and runnable. They use
``__file__``-relative paths for any on-disk artefact (audit databases,
YAML configs), so they behave identically whether you launch them from
the repo root or from ``examples/`` itself.

## Prerequisites

```
pip install -e ".[all]"
```

The ``[all]`` extra pulls in PyYAML; the third-party SDK extras
(``openai``, ``anthropic``, ``langchain``) are **not** required — every
adapter example uses fake tool-call payloads to keep the run offline
and deterministic.

## Run them

```
python examples/01_basic_gate.py
python examples/02_yaml_config.py
python examples/03_decorator.py
python examples/04_audit_trail.py
python examples/05_review_queue.py
python examples/06_openai_adapter.py
python examples/07_anthropic_adapter.py
python examples/08_langchain_adapter.py
```

## What each example shows

| File                            | Topic                                                            |
| ------------------------------- | ---------------------------------------------------------------- |
| `01_basic_gate.py`              | Build a `Gate` from a dict, evaluate a tool call, read a verdict |
| `02_yaml_config.py`             | Load policies from `configs/gate.yaml`                           |
| `03_decorator.py`               | Wrap a function with `@gate()`; catch `Blocked` / `NeedsReview`  |
| `04_audit_trail.py`             | Persist verdicts to SQLite and verify the hash chain             |
| `05_review_queue.py`            | Auto-enqueue REVIEW verdicts and approve/reject from code        |
| `06_openai_adapter.py`          | Filter an OpenAI `tool_calls` array through the gate             |
| `07_anthropic_adapter.py`       | Filter Anthropic `tool_use` blocks through the gate              |
| `08_langchain_adapter.py`       | Wrap a LangChain-style tool with `GatedTool`                     |

## Cleaning up

The audit / review examples write SQLite files into a per-run temp
directory (see `pathlib.Path(tempfile.gettempdir())`). They are safe to
re-run and never touch your home directory.
