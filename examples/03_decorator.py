"""03 — wrap a Python function with @gate().

Run::

    python examples/03_decorator.py
"""

from __future__ import annotations

from diplomat_gate import Blocked, Gate, NeedsReview, configure, gate


def main() -> None:
    g = Gate.from_dict(
        {
            "payment": [
                {"id": "payment.amount_limit", "max_amount": 1000, "on_fail": "STOP"},
                {
                    "id": "payment.duplicate_detection",
                    "window": "5m",
                    "on_fail": "REVIEW",
                },
            ]
        }
    )
    configure(g)

    @gate(action="charge_card")
    def charge(amount: int, customer_id: str) -> str:
        return f"charged {amount} for {customer_id}"

    print(charge(500, customer_id="cus_1"))

    try:
        charge(5000, customer_id="cus_2")
    except Blocked as exc:
        print(f"blocked: {[v.policy_id for v in exc.verdict.violations]}")

    # The same call repeated within the duplicate-detection window will trigger REVIEW.
    print(charge(200, customer_id="cus_3"))
    try:
        charge(200, customer_id="cus_3")
    except NeedsReview as exc:
        print(f"needs review: {[v.policy_id for v in exc.verdict.violations]}")


if __name__ == "__main__":
    main()
