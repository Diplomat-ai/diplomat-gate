# diplomat-gate

Approval gates for AI agent payments and emails. Evaluate tool calls against policies — **CONTINUE / REVIEW / STOP** — before execution.

## Install

```bash
pip install diplomat-gate
pip install "diplomat-gate[yaml]"   # for YAML config
pip install "diplomat-gate[all]"    # all extras
```

## Quick start

```python
from diplomat_gate import Gate

gate = Gate.from_yaml("gate.yaml")

verdict = gate.evaluate({
    "action": "charge_card",
    "amount": 15000,
    "currency": "usd",
    "customer_id": "cus_abc123",
})

if verdict.allowed:
    # proceed
    pass
elif verdict.needs_review:
    # route to human
    pass
else:
    # verdict.blocked — abort
    pass
```

## License

Apache-2.0
