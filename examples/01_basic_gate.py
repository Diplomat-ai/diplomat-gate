"""01 — basic gate built from a dict.

Run::

    python examples/01_basic_gate.py
"""

from __future__ import annotations

from diplomat_gate import Gate


def main() -> None:
    gate = Gate.from_dict(
        {
            "payment": [
                {"id": "payment.amount_limit", "max_amount": 1000, "on_fail": "STOP"},
            ],
        }
    )

    for amount in (500, 1500):
        verdict = gate.evaluate({"action": "charge_card", "amount": amount})
        print(
            f"amount={amount:>5} -> {verdict.decision.value:<8} "
            f"latency={verdict.latency_ms:.3f}ms "
            f"violations={[v.policy_id for v in verdict.violations]}"
        )


if __name__ == "__main__":
    main()
