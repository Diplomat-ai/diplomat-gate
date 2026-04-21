# Quickstart

Five-minute tour of `diplomat-gate` from `pip install` to a working
gate with audit log and review queue.

## 1. Install

```
pip install "diplomat-gate[yaml]"
```

Drop `[yaml]` if you intend to configure your gate from a Python dict
instead of a YAML file.

## 2. Write a policy file

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
    max_amount: 1000
    severity: critical
    on_fail: STOP

  - id: payment.duplicate_detection
    window: 5m
    severity: high
    on_fail: REVIEW

email:
  - id: email.domain_blocklist
    blocked: ["*.evil.com"]
    severity: critical
    on_fail: STOP
```

## 3. Wire it into your code

### Direct evaluation

```python
from diplomat_gate import Gate

gate = Gate.from_yaml("gate.yaml")

verdict = gate.evaluate({
    "action": "charge_card",
    "amount": 200,
    "agent_id": "checkout-bot",
})
if verdict.decision.value == "STOP":
    raise RuntimeError("blocked: " + ", ".join(v.policy_id for v in verdict.violations))
```

### Decorator

```python
from diplomat_gate import Gate, configure, gate, Blocked, NeedsReview

configure(Gate.from_yaml("gate.yaml"))

@gate(action="charge_card")
def charge(amount: int, customer_id: str) -> dict:
    return stripe.charges.create(amount=amount, customer=customer_id)

try:
    charge(amount=5000, customer_id="cus_x")
except Blocked as e:
    handle_block(e.verdict)
except NeedsReview as e:
    handle_review(e.verdict)        # already enqueued in diplomat-review.db
```

### LLM SDK adapter

```python
from diplomat_gate.adapters.openai import filter_allowed

resp = client.chat.completions.create(...)
allowed, review, blocked = filter_allowed(gate, resp.choices[0].message.tool_calls)

for raw in allowed:
    execute_openai_tool(raw)
```

## 4. Operate the audit log and review queue

```
# Verify the hash chain whenever you want.
diplomat-gate audit verify --db ./diplomat-audit.db

# List pending items, then approve or reject.
diplomat-gate review list    --db ./diplomat-review.db
diplomat-gate review approve --db ./diplomat-review.db --id <item_id> --reviewer alice
diplomat-gate review reject  --db ./diplomat-review.db --id <item_id> --reviewer alice --note "vendor not whitelisted"
```

## 5. Where to go next

- [`docs/audit-trail.md`](audit-trail.md) — schema, threat model, hash
  computation, migration from 0.1.x.
- [`docs/review-queue.md`](review-queue.md) — lifecycle, redaction, TTL.
- [`docs/adapters.md`](adapters.md) — OpenAI, Anthropic, LangChain.
- [`docs/writing-policies.md`](writing-policies.md) — custom policies.
- [`examples/`](../examples/) — eight runnable scripts covering each of
  the above paths.
