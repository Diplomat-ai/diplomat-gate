import pytest

from diplomat_gate import Blocked, Gate, NeedsReview, configure, gate


class TestDecorator:
    def test_allowed(self):
        configure(Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]}))

        @gate(action="charge_card")
        def charge(amount: int):
            return {"charged": amount}

        assert charge(amount=500) == {"charged": 500}

    def test_blocked(self):
        configure(Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]}))

        @gate(action="charge_card")
        def charge(amount: int):
            return {"charged": amount}

        with pytest.raises(Blocked):
            charge(amount=5000)

    def test_review(self):
        configure(
            Gate.from_dict(
                {
                    "payment": [
                        {"id": "payment.amount_limit", "max_amount": 1000, "on_fail": "REVIEW"}
                    ]
                }
            )
        )

        @gate(action="charge_card")
        def charge(amount: int):
            return {"charged": amount}

        with pytest.raises(NeedsReview):
            charge(amount=5000)

    def test_no_gate_raises(self):
        from diplomat_gate import decorator

        decorator._default_gate = None

        @gate(action="charge_card")
        def charge(amount: int):
            return amount

        with pytest.raises(RuntimeError, match="No Gate configured"):
            charge(amount=100)
