# diplomat-gate

[![PyPI](https://img.shields.io/pypi/v/diplomat-gate)](https://pypi.org/project/diplomat-gate/)
[![Python](https://img.shields.io/pypi/pyversions/diplomat-gate)](https://pypi.org/project/diplomat-gate/)
[![License](https://img.shields.io/pypi/l/diplomat-gate)](https://github.com/Diplomat-ai/diplomat-gate/blob/main/LICENSE)
[![CI](https://github.com/Diplomat-ai/diplomat-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/Diplomat-ai/diplomat-gate/actions/workflows/ci.yml)

**Runtime action firewall for AI agents.** Deterministic, local, no LLM.

Your agent can call `stripe.charges.create()` with no amount limit. Your
agent can call `smtp.sendmail()` to anyone, anytime. `diplomat-gate`
intercepts these calls, runs them through a set of policies, and returns
**CONTINUE / REVIEW / STOP** before execution — typically in under
50 µs for a small policy set.

```
pip install diplomat-gate
```

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
