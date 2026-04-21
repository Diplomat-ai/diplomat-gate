# Contributing to diplomat-gate

## Quick start

```bash
git clone https://github.com/Diplomat-ai/diplomat-gate.git
cd diplomat-gate
pip install -e ".[dev]"
python -m pytest
```

The full unit-test suite should pass. You're ready to contribute.

## How to contribute

### Report a bug in a policy

If a policy returns the wrong verdict (e.g. `CONTINUE` when it should `STOP`), open a **Bug Report** issue with:
- The policy id (e.g. `payment.amount_limit`)
- The input dict you passed to `gate.evaluate()`
- The expected verdict vs. the actual verdict

### Suggest a new policy

If you think diplomat-gate should cover a new risk (e.g. currency validation, attachment scanning), open a **Feature Request** issue describing the use case.

### Add a policy

Policies live in `src/diplomat_gate/policies/`. Each policy:

1. Inherits from `Policy` in `src/diplomat_gate/policies/base.py`.
2. Implements `evaluate(tool_call: ToolCall, state: StateStore) -> PolicyResult`
   (returns `PolicyResult.PASS`, `PolicyResult.FAIL`, or `PolicyResult.WARN`).
3. Implements `violation_message(tool_call: ToolCall) -> str`.
4. Is registered in `_POLICY_MAP` inside `src/diplomat_gate/policies/loader.py`.
5. Has matching tests in `tests/`.

Look at `src/diplomat_gate/policies/payments.py` for examples. The
verdict (`Decision.CONTINUE` / `Decision.REVIEW` / `Decision.STOP`) is
computed by the engine from the combined `PolicyResult`s and each policy's
`on_fail` action.

## Code style

* No external dependencies in core (stdlib only)
* `rich`, `pyyaml`, `langchain-core`, `openai`, `anthropic` are optional extras
* Run `python -m pytest` before submitting
* Run `ruff check .` and `ruff format --check .` to lint

## Running examples

All example scripts must run from the repository root. Each example
resolves its own paths via `pathlib.Path(__file__).parent`:

```bash
python examples/01_basic_gate.py
```

## Running benchmarks

Reproducible benchmarks live under `benchmarks/`:

```bash
make bench
# or
python benchmarks/run.py
```

The script prints a Markdown table of mean / p50 / p95 / p99 / max
latencies for several configurations and workloads.

## Running the audit CLI

After installation the `diplomat-gate` CLI is on `$PATH`:

```bash
diplomat-gate audit verify
diplomat-gate audit stats
diplomat-gate audit tail -n 20
```

The CLI exits `0` on a valid hash chain, `1` on a chain inconsistency,
and `2` on a usage error.

## Pull request process

1. Fork and create a branch from `main`.
2. Add tests for any new or changed policy.
3. Ensure `pytest`, `ruff check .`, and `ruff format --check .` all pass.
4. Open a PR with a clear description and reference the relevant phase
   of the 0.2.0 plan if applicable.
