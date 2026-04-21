# diplomat-gate

[![PyPI](https://img.shields.io/pypi/v/diplomat-gate)](https://pypi.org/project/diplomat-gate/)
[![Python](https://img.shields.io/pypi/pyversions/diplomat-gate)](https://pypi.org/project/diplomat-gate/)
[![License](https://img.shields.io/pypi/l/diplomat-gate)](https://github.com/Diplomat-ai/diplomat-gate/blob/main/LICENSE)
[![CI](https://github.com/Diplomat-ai/diplomat-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/Diplomat-ai/diplomat-gate/actions/workflows/ci.yml)

**Your AI agent just emailed your insurance company. You didn't ask it to.**

An AI assistant inferred the claims address from a document the user
uploaded and sent a legal rebuttal — autonomously, without confirmation.
Nothing in the framework stopped it.

This is what happens without a runtime guardrail. Here is the fix:

```
pip install diplomat-gate
```

```yaml
# 10 lines of YAML
policies:
  - type: email.domain_blocklist
    blocked: ["*@lemonade.com", "*@*insurance*", "*@*legal*"]
    on_fail: STOP
  - type: email.rate_limit
    max: 2
    window: 1h
    on_fail: REVIEW
audit:
  enabled: true
```

```
$ python demos/openclaw/run.py --ci

SCENARIO 1 — OpenClaw agent, no diplomat-gate
  Emails sent without approval : 1
  Recipient                    : claims@lemonade.com
  🔥 Legal email sent to insurance company without user approval.

SCENARIO 2 — Same agent, behind diplomat-gate
  Verdict: STOP
    - email.domain_blocklist: Domain 'lemonade.com' is on the blocklist
  🛡  Email blocked before reaching the SMTP server.
  Emails actually sent: 0

  to: alice@example.com               Verdict: CONTINUE
  to: bob@example.com                 Verdict: REVIEW  (email.rate_limit)

SCENARIO 3 — Every verdict is hash-chained
  $ diplomat-gate audit verify
  OK: chain valid (3 record(s) checked)
```

_No API key. No Docker. No setup. Run it yourself:_
`python demos/openclaw/run.py`

---

## The problem

AI agents call APIs with real-world side effects — send email, charge a
card, delete files, POST to a webhook — and most orchestration frameworks
treat hard enforcement as the operator's responsibility. In practice that
means there is none.

Running `diplomat-agent scan` on a typical agent codebase:

```
$ diplomat-agent scan ./my_agent

Scanning for tool calls with external side effects...

  email.send            12 call sites    0 / 12 have a runtime guard
  payment.charge         4 call sites    0 /  4 have a runtime guard
  files.delete           3 call sites    0 /  3 have a runtime guard
  webhook.post           2 call sites    0 /  2 have a runtime guard
  browser.navigate       7 call sites    0 /  7 have a runtime guard

  28 call sites with side effects found.
   0 are protected by a runtime guardrail.

Recommended: diplomat-gate
```

`diplomat-gate` is the missing runtime layer. It intercepts calls,
evaluates them against a YAML policy file, and returns
**CONTINUE / REVIEW / STOP** before execution — in under 50 µs for a
small policy set, with no LLM call, no network request.

## Works with every framework

diplomat-gate is framework-agnostic. Any call that can be represented as a
Python `dict` works out of the box. Adapters for popular SDKs are included.

| Framework | Integration | How |
|---|---|---|
| OpenAI (tool calls) | ✓ built-in adapter | `from diplomat_gate.adapters.openai import filter_allowed` |
| Anthropic (tool_use) | ✓ built-in adapter | `from diplomat_gate.adapters.anthropic import filter_allowed` |
| LangChain tools | ✓ built-in adapter | `from diplomat_gate.adapters.langchain import gated_tool` |
| OpenClaw | ✓ dict API | `gate.evaluate({"action": ..., ...})` |
| PythonClaw | ✓ dict API | `gate.evaluate({"action": ..., ...})` |
| CrewAI | ✓ dict API | wrap any tool call with `gate.evaluate(...)` |
| AutoGen | ✓ dict API | wrap any tool call with `gate.evaluate(...)` |
| Any Python agent | ✓ dict API | if it calls an API, it can be gated |

## What's new in 0.3.0

- **Reproducible OpenClaw demo** — `python demos/openclaw/run.py` shows
  the insurance email incident in under 60 seconds, no API key needed.
- **Release validation pipeline** — `scripts/validate_release.py` runs an
  11-step gate: lint → tests → benchmarks → build → install → smoke → demo.

## What's new in 0.2.0

- **Hash-chained audit trail** — every verdict is sealed with a SHA-256
  record hash that links to its predecessor. Tampering with a historical
  row breaks the chain and is detected by `diplomat-gate audit verify`.
- **Review queue** — REVIEW verdicts are auto-enqueued in a separate
  SQLite database. Operators approve or reject from the CLI or
  programmatically. Pending → approved / rejected / expired lifecycle
  is enforced server-side.
- **Adapters** for OpenAI tool calls, Anthropic `tool_use` blocks, and
  LangChain-style tools — duck-typed, no SDK import required.
- **CLI** (`diplomat-gate audit verify | rebuild-chain`,
  `diplomat-gate review list | show | approve | reject`).
- **Sensitive field redaction by default** in audit and review storage
  (`recipient`, `to`, `email`, `domain`, `amount`, `card_last4`, `phone`).
- **8 runnable examples** under `examples/`, **CI matrix** across
  Python 3.10–3.13 × Linux / Windows / macOS, **microbenchmarks** under
  `benchmarks/`.

See the full [`CHANGELOG.md`](CHANGELOG.md).

## 60-second setup

```yaml
# gate.yaml
version: "1"

audit:
  enabled: true
  path: "./diplomat-audit.db"

review_queue:
  enabled: true
  path: "./diplomat-review.db"

payment:
  - id: payment.amount_limit
    max_amount: 10000
    on_fail: STOP

email:
  - id: email.domain_blocklist
    blocked: ["*.banque-*.fr", "*.gouv.fr"]
    on_fail: STOP
```

```python
from diplomat_gate import Gate

gate = Gate.from_yaml("gate.yaml")

verdict = gate.evaluate({"action": "charge_card", "amount": 15_000})
# verdict.decision  -> Decision.STOP
# verdict.violations -> [Violation(policy_id="payment.amount_limit", ...)]
# verdict.latency_ms -> ~0.05
```

## How it works

```
Agent wants to act  ->  diplomat-gate evaluates  ->  Verdict  ->  Execute, queue, or block

  +-----------+      +-----------------+      +-----------------+
  | AI agent  | ---> |  diplomat-gate  | ---> | CONTINUE        |
  | (any fw)  |      |  - policies     |      | / REVIEW        |
  +-----------+      |  - audit log    |      | / STOP          |
                     |  - review queue |      +-----------------+
                     +-----------------+
```

No LLM calls. No network requests. Pure deterministic evaluation. Each
verdict produces a `Receipt` with a SHA-256 hash of the canonical tool
call.

## Decorator API

```python
from diplomat_gate import Blocked, Gate, NeedsReview, configure, gate

configure(Gate.from_yaml("gate.yaml"))

@gate(action="charge_card")
def charge(amount: int, customer_id: str) -> dict:
    return stripe.charges.create(amount=amount, customer=customer_id)

charge(amount=500, customer_id="cus_123")          # CONTINUE -> normal return
charge(amount=50_000, customer_id="cus_123")       # STOP    -> raises Blocked
```

- **CONTINUE**: function executes, returns its normal value.
- **STOP**: raises `Blocked` with the full `Verdict` attached.
- **REVIEW**: raises `NeedsReview`; if `review_queue` is enabled, the
  call is also persisted for an operator to approve/reject.

## Audit trail

Every verdict is recorded in an append-only SQLite log with a SHA-256
hash chain.

```
diplomat-gate audit verify        --db ./diplomat-audit.db
diplomat-gate audit rebuild-chain --db ./diplomat-audit.db   # one-shot recovery
```

Sensitive parameters in violation contexts (`recipient`, `to`, `email`,
`domain`, `amount`, `card_last4`, `phone`) are redacted to
`h:<sha256-prefix>` before persistence. See [`docs/audit-trail.md`](docs/audit-trail.md)
for schema, threat model, and migration from 0.1.x.

## Review queue (human-in-the-loop)

A REVIEW verdict is enqueued automatically in a separate SQLite database
when `review_queue.enabled` is true.

```
diplomat-gate review list    --db ./diplomat-review.db
diplomat-gate review show    --db ./diplomat-review.db --id <item_id>
diplomat-gate review approve --db ./diplomat-review.db --id <item_id> --reviewer alice
diplomat-gate review reject  --db ./diplomat-review.db --id <item_id> --reviewer alice --note "..."
```

See [`docs/review-queue.md`](docs/review-queue.md).

## Adapters

Bring-your-own LLM SDK. Adapters are duck-typed — installing the SDK is
not required to use them.

```python
from diplomat_gate.adapters.openai    import filter_allowed as openai_filter
from diplomat_gate.adapters.anthropic import filter_allowed as anthropic_filter
from diplomat_gate.adapters.langchain import gated_tool

# OpenAI
allowed, review, blocked = openai_filter(gate, response.choices[0].message.tool_calls)

# Anthropic
allowed, review, blocked = anthropic_filter(gate, response.content)

# LangChain
safe_tool = gated_tool(my_langchain_tool, gate)
```

See [`docs/adapters.md`](docs/adapters.md).

## Payment policies

| Policy | What it checks | Config |
|---|---|---|
| `payment.amount_limit` | Single transaction cap | `max_amount: 10000` |
| `payment.daily_limit` | Cumulative daily spend | `max_daily: 50000` |
| `payment.velocity` | Max transactions per window | `max_txn: 20, window: 1h` |
| `payment.duplicate_detection` | Same amount + recipient within window | `window: 5m` |
| `payment.recipient_blocklist` | Block specific recipients (glob) | `blocked: ["evil_*"]` |

## Email policies

| Policy | What it checks | Config |
|---|---|---|
| `email.domain_blocklist` | Restricted recipient domains | `blocked: ["*.banque-*.fr"]` |
| `email.rate_limit` | Max emails per window | `max: 50, window: 1h` |
| `email.business_hours` | Sends outside work hours | `start: 9, end: 18, tz: Europe/Paris` |
| `email.content_scan` | Credit cards, SSNs, API keys, private keys in body | `patterns: [credit_card, ssn]` |

Every policy takes a `severity` (critical / high / medium / low) and an
`on_fail` action (`STOP` or `REVIEW`).

Custom policies: see [`docs/writing-policies.md`](docs/writing-policies.md).

## Performance

Microbenchmarks (`python benchmarks/run.py`, dev laptop, 5 000 iters):

| Scenario              | mean   | p95    | p99    | ops/s   |
| --------------------- | ------ | ------ | ------ | ------- |
| `simple_allow`        | ~8 µs  | ~10 µs | ~12 µs | 130 000 |
| `simple_block`        | ~10 µs | ~12 µs | ~40 µs | 100 000 |
| `multi_policy` (5)    | ~55 µs | ~95 µs | ~110 µs | 17 000 |
| `with_audit_sqlite`   | ~200 µs | ~300 µs | ~1.3 ms | 5 000 |

Audit numbers are dominated by `fsync`. Re-run on your hardware before
quoting publicly.

## Zero mandatory dependencies

`diplomat-gate` ships pure-stdlib. Optional extras:

| Extra        | Brings in            | Used for                              |
| ------------ | -------------------- | ------------------------------------- |
| `[yaml]`     | `pyyaml`             | `Gate.from_yaml(...)`                 |
| `[rich]`     | `rich`               | colored CLI output                    |
| `[openai]`   | `openai>=1.0`        | optional, for typed adapter usage     |
| `[anthropic]`| `anthropic>=0.20`    | optional, for typed adapter usage     |
| `[langchain]`| `langchain-core>=0.1`| optional, for typed adapter usage     |
| `[all]`      | all of the above     | one-shot install                      |

```
pip install diplomat-gate          # core only
pip install "diplomat-gate[yaml]"  # for YAML policy files
pip install "diplomat-gate[all]"   # everything
```

## Examples

Eight runnable examples — each works from the repo root **and** from
inside `examples/`. None of them require an SDK install.

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

See [`examples/README.md`](examples/README.md).

## Use with diplomat-agent

[`diplomat-agent`](https://github.com/Diplomat-ai/diplomat-agent) scans
your codebase and reports every tool call with real-world side effects.
`diplomat-gate` protects them.

## Need centralized governance?

`diplomat-gate` is local-first and free. For teams that need a hosted
control plane:

[**diplomat.run**](https://diplomat.run) — immutable cross-tenant audit
trail, real-time dashboard, managed approval routing, compliance export
(EU AI Act Article 12).

## Requirements

- Python 3.10+
- Zero mandatory dependencies (stdlib only)
- Optional extras as listed above

## License

Apache 2.0
