"""Core engine tests — decision resolution, receipts, latency, domain matching."""

from diplomat_gate import Decision, Gate


def _g(config):
    return Gate.from_dict(config)


class TestContinue:
    def test_under_limit(self):
        v = _g({"payment": [{"id": "payment.amount_limit", "max_amount": 10000}]}).evaluate(
            {"action": "charge_card", "amount": 5000}
        )
        assert v.allowed and len(v.violations) == 0

    def test_safe_domain(self):
        v = _g({"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]}).evaluate(
            {"action": "send_email", "to": "hi@safe.com"}
        )
        assert v.allowed


class TestStop:
    def test_over_limit(self):
        v = _g({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]}).evaluate(
            {"action": "charge_card", "amount": 5000}
        )
        assert v.blocked and "5000" in v.violations[0].message

    def test_blocked_domain(self):
        v = _g(
            {"email": [{"id": "email.domain_blocklist", "blocked": ["*.banque-*.fr"]}]}
        ).evaluate({"action": "send_email", "to": "cfo@banque-marseille.fr"})
        assert v.blocked


class TestReview:
    def test_review_verdict(self):
        v = _g(
            {"payment": [{"id": "payment.amount_limit", "max_amount": 1000, "on_fail": "REVIEW"}]}
        ).evaluate({"action": "charge_card", "amount": 5000})
        assert v.needs_review

    def test_stop_overrides_review(self):
        v = _g(
            {
                "payment": [
                    {"id": "payment.amount_limit", "max_amount": 1000, "on_fail": "REVIEW"},
                    {"id": "payment.recipient_blocklist", "blocked": ["evil_*"], "on_fail": "STOP"},
                ]
            }
        ).evaluate({"action": "charge_card", "amount": 5000, "customer_id": "evil_corp"})
        assert v.decision == Decision.STOP and len(v.violations) == 2


class TestReceipt:
    def test_has_fields(self):
        v = _g({"payment": [{"id": "payment.amount_limit", "max_amount": 10000}]}).evaluate(
            {"action": "charge_card", "amount": 100}
        )
        assert v.receipt.verdict_id and v.receipt.timestamp and v.receipt.tool_call_hash

    def test_hash_deterministic(self):
        g = _g({"payment": [{"id": "payment.amount_limit", "max_amount": 10000}]})
        h1 = g.evaluate({"action": "charge_card", "amount": 100}).receipt.tool_call_hash
        h2 = g.evaluate({"action": "charge_card", "amount": 100}).receipt.tool_call_hash
        assert h1 == h2


class TestLatency:
    def test_under_5ms(self):
        g = _g(
            {
                "payment": [
                    {"id": "payment.amount_limit", "max_amount": 10000},
                    {"id": "payment.velocity", "max_txn": 100, "window": "1h"},
                ],
                "email": [
                    {"id": "email.domain_blocklist", "blocked": ["*.x.com"]},
                    {"id": "email.rate_limit", "max": 100, "window": "1h"},
                ],
            }
        )
        assert g.evaluate({"action": "charge_card", "amount": 100}).latency_ms < 5.0


class TestDomainMatching:
    def test_payment_ignores_email(self):
        v = _g({"payment": [{"id": "payment.amount_limit", "max_amount": 1}]}).evaluate(
            {"action": "send_email", "to": "a@b.com", "amount": 99999}
        )
        assert v.allowed and v.receipt.policies_evaluated == 0

    def test_email_ignores_payment(self):
        v = _g({"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]}).evaluate(
            {"action": "charge_card", "to": "x@evil.com"}
        )
        assert v.allowed and v.receipt.policies_evaluated == 0
