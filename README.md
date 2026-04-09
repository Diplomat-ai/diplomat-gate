# diplomat-gate

Approval gates for the two most dangerous things your AI agent can do:
**send money** and **send email**.

Your agent can `stripe.charges.create()` with no amount limit.
Your agent can `smtp.sendmail()` to anyone, anytime.
diplomat-gate intercepts these calls and returns **CONTINUE**, **REVIEW**, or **STOP**
before execution — in under 1ms.

```
pip install diplomat-gate
```

## 30-second setup

```yaml
# gate.yaml
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

verdict = gate.evaluate({"action": "charge_card", "amount": 15000})
# verdict.decision  → STOP
# verdict.violations → [{"policy": "amount_limit", "message": "Amount 15000 exceeds limit of 10000"}]
# verdict.latency_ms → 0.2

verdict = gate.evaluate({"action": "send_email", "to": "cfo@banque-marseille.fr"})
# verdict.decision  → STOP
# verdict.violations → [{"policy": "domain_blocklist", "message": "Domain 'banque-marseille.fr' is on the blocklist"}]
```

## How it works

```
Agent wants to act  →  diplomat-gate evaluates  →  Verdict  →  Execute or block

┌──────────┐     ┌───────────────┐     ┌───────────┐
│  AI Agent │────▶│ diplomat-gate │────▶│  Verdict   │
│ (any fw)  │     │    < 1ms      │     │ C / R / S  │
└──────────┘     └───────────────┘     └───────────┘
```

No LLM calls. No network requests. Pure deterministic policy evaluation.
Every verdict generates a receipt with a SHA-256 hash of the evaluated tool call.

## Why this exists

We scanned [16 open-source agent repos](https://github.com/Diplomat-ai/diplomat-agent). **76% of tool calls had zero checks.**
No approval gate. No amount limit. No domain restriction.

We then surveyed 90+ governance projects. The finding:

- **No open-source fiat payment safety middleware exists.** Stripe Agent Toolkit has 1,200 stars and zero safety controls.
- **No production-quality email safety for agents exists.** Business hours enforcement is absent from every project scanned.
- General-purpose policy engines (Microsoft AGT, OPA, Cedar) require building domain-specific rules from scratch.

diplomat-gate fills the gap with **9 payment policies** and **4 email policies** that work out of the box.

## Payment policies

| Policy | What it checks | Config |
|---|---|---|
| `payment.amount_limit` | Single transaction cap | `max_amount: 10000` |
| `payment.daily_limit` | Cumulative daily spend | `max_daily: 50000` |
| `payment.velocity` | Max transactions per window | `max_txn: 20, window: 1h` |
| `payment.duplicate_detection` | Same amount + recipient within window | `window: 5m` |
| `payment.recipient_blocklist` | Block specific recipients (glob patterns) | `blocked: ["evil_*"]` |

## Email policies

| Policy | What it checks | Config |
|---|---|---|
| `email.domain_blocklist` | Block sends to restricted domains | `blocked: ["*.banque-*.fr"]` |
| `email.rate_limit` | Max emails per window | `max: 50, window: 1h` |
| `email.business_hours` | Block sends outside work hours | `start: 9, end: 18, tz: Europe/Paris` |
| `email.content_scan` | Detect credit cards, SSNs, API keys, private keys in body | `patterns: [credit_card, ssn, api_key]` |

Every policy takes a `severity` (critical / high / medium / low) and an `on_fail` action (STOP or REVIEW).

## Decorator API

```python
from diplomat_gate import Gate, gate, configure, Blocked, NeedsReview

configure(Gate.from_yaml("gate.yaml"))

@gate(action="charge_card")
def charge(amount: int, currency: str, customer_id: str):
    return stripe.charges.create(amount=amount, currency=currency, customer=customer_id)

charge(amount=500, currency="usd", customer_id="cus_123")     # executes normally
charge(amount=50000, currency="usd", customer_id="cus_123")   # raises Blocked(verdict)
```

On **CONTINUE**: function executes, returns its normal value.
On **STOP**: raises `Blocked` with the full verdict attached.
On **REVIEW**: raises `NeedsReview` — route to a human.

## Audit trail

Every verdict is recorded in a local SQLite database:

```yaml
# gate.yaml
audit:
  enabled: true
  path: "./diplomat-audit.db"
```

```python
gate = Gate.from_yaml("gate.yaml")
gate.evaluate({"action": "charge_card", "amount": 500})
gate.evaluate({"action": "charge_card", "amount": 50000})

gate.audit.count()              # → 2
gate.audit.count("STOP")        # → 1
gate.audit.query(decision="STOP")
# → [{"verdict_id": "...", "action": "charge_card", "decision": "STOP", ...}]
```

No PII is stored — only action names, parameter hashes, decisions, and latencies.

## Works with any framework

diplomat-gate evaluates plain Python dicts. No framework adapter needed.

```python
# LangGraph
verdict = gate.evaluate({"action": tool_call.name, **tool_call.args})

# CrewAI
verdict = gate.evaluate({"action": tool.name, **tool.arguments})

# OpenAI Agents SDK
verdict = gate.evaluate({"action": function_name, **json.loads(arguments)})

# Raw Python
verdict = gate.evaluate({"action": "send_email", "to": recipient, "body": content})
```

## Zero dependencies

diplomat-gate uses only the Python standard library. No mandatory external packages.

Optional extras:
- `pip install diplomat-gate[yaml]` — load policies from YAML files (requires PyYAML)
- `pip install diplomat-gate[rich]` — colored terminal output

Without PyYAML, use `Gate.from_dict()` with a Python dictionary instead.

## Performance

Benchmarked with all 9 policies loaded, 100 evaluations each:

| Domain | Avg latency | p50 | p99 |
|---|---|---|---|
| Payment (5 policies) | 0.57ms | 0.26ms | < 1ms |
| Email (4 policies) | 0.07ms | 0.05ms | < 1ms |

## Use with diplomat-agent

[diplomat-agent](https://github.com/Diplomat-ai/diplomat-agent) scans your codebase
and finds every tool call with real-world side effects. diplomat-gate protects them.

```bash
# Step 1: Find what your agent can do
pip install diplomat-agent
diplomat-agent scan .
# → 12 unguarded tool calls (8 payments, 4 emails)

# Step 2: Protect them
pip install diplomat-gate
# → Write gate.yaml, wrap your tools

# Step 3: Need centralized audit trail, dashboard, multi-tenant?
# → diplomat.run
```

## Need more?

diplomat-gate is local-first and free. For teams that need centralized governance:

[**diplomat.run**](https://diplomat.run) — the hosted control plane with
immutable hash-chained audit trail, real-time dashboard, multi-tenant isolation,
compliance export (EU AI Act Article 12), and managed approval routing.

## Requirements

- Python 3.10+
- Zero mandatory dependencies (stdlib only)
- Optional: PyYAML for YAML policy files

## License

Apache 2.0 
