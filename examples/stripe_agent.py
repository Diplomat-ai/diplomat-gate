"""Protecting Stripe charges with diplomat-gate."""

from diplomat_gate import Gate

gate = Gate.from_yaml("gate.yaml")

verdict = gate.evaluate({
    "action": "charge_card",
    "amount": 15000,
    "currency": "usd",
    "customer_id": "cus_abc123",
    "agent_id": "sales-agent-1",
})

if verdict.allowed:
    print("\u2713 CONTINUE \u2014 executing charge")
    # stripe.charges.create(amount=15000, currency="usd", customer="cus_abc123")
elif verdict.needs_review:
    print(f"\u26a0 REVIEW \u2014 {len(verdict.violations)} issue(s)")
    for v in verdict.violations:
        print(f"  \u2192 {v.policy_name}: {v.message}")
else:
    print(f"\u2717 STOP \u2014 {len(verdict.violations)} violation(s)")
    for v in verdict.violations:
        print(f"  \u2192 [{v.severity}] {v.policy_name}: {v.message}")

print(f"\nReceipt: {verdict.receipt.verdict_id}")
print(f"Latency: {verdict.latency_ms}ms")
