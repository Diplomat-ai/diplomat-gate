"""Protecting AI-generated emails with diplomat-gate."""

from diplomat_gate import Gate

gate = Gate.from_yaml("gate.yaml")

verdict = gate.evaluate({
    "action": "send_email",
    "to": "cfo@banque-marseille.fr",
    "subject": "Partnership proposal",
    "body": "Dear CFO, I'd like to discuss...",
    "agent_id": "sdr-agent",
})

print(f"Decision: {verdict.decision.value} ({verdict.latency_ms}ms)")
if not verdict.allowed:
    for v in verdict.violations:
        print(f"  [{v.severity}] {v.policy_name}: {v.message}")
