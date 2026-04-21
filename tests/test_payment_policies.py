from diplomat_gate import Gate


def _g(p):
    return Gate.from_dict({"payment": p})


class TestAmountLimit:
    def test_under(self):
        assert (
            _g([{"id": "payment.amount_limit", "max_amount": 1000}])
            .evaluate({"action": "charge_card", "amount": 999})
            .allowed
        )

    def test_at(self):
        assert (
            _g([{"id": "payment.amount_limit", "max_amount": 1000}])
            .evaluate({"action": "charge_card", "amount": 1000})
            .allowed
        )

    def test_over(self):
        assert (
            _g([{"id": "payment.amount_limit", "max_amount": 1000}])
            .evaluate({"action": "charge_card", "amount": 1001})
            .blocked
        )

    def test_string_amount(self):
        assert (
            _g([{"id": "payment.amount_limit", "max_amount": 1000}])
            .evaluate({"action": "charge_card", "amount": "5000"})
            .blocked
        )

    def test_currency_filter(self):
        g = _g([{"id": "payment.amount_limit", "max_amount": 1000, "currency": "usd"}])
        assert g.evaluate({"action": "charge_card", "amount": 5000, "currency": "eur"}).allowed
        assert g.evaluate({"action": "charge_card", "amount": 5000, "currency": "usd"}).blocked


class TestVelocity:
    def test_under_limit(self):
        g = _g([{"id": "payment.velocity", "max_txn": 3, "window": "1h"}])
        for _ in range(3):
            assert g.evaluate({"action": "payment", "amount": 10}).allowed

    def test_over_limit(self):
        g = _g([{"id": "payment.velocity", "max_txn": 3, "window": "1h"}])
        for _ in range(3):
            g.evaluate({"action": "payment", "amount": 10})
        assert g.evaluate({"action": "payment", "amount": 10}).blocked


class TestDuplicate:
    def test_first_passes(self):
        assert (
            _g([{"id": "payment.duplicate_detection", "window": "5m"}])
            .evaluate({"action": "payment", "amount": 100, "customer_id": "c1"})
            .allowed
        )

    def test_same_blocked(self):
        g = _g([{"id": "payment.duplicate_detection", "window": "5m"}])
        g.evaluate({"action": "payment", "amount": 100, "customer_id": "c1"})
        assert g.evaluate({"action": "payment", "amount": 100, "customer_id": "c1"}).blocked

    def test_diff_amount_passes(self):
        g = _g([{"id": "payment.duplicate_detection", "window": "5m"}])
        g.evaluate({"action": "payment", "amount": 100, "customer_id": "c1"})
        assert g.evaluate({"action": "payment", "amount": 200, "customer_id": "c1"}).allowed


class TestBlocklist:
    def test_clean(self):
        assert (
            _g([{"id": "payment.recipient_blocklist", "blocked": ["evil_*"]}])
            .evaluate({"action": "payment", "customer_id": "cus_good"})
            .allowed
        )

    def test_blocked(self):
        assert (
            _g([{"id": "payment.recipient_blocklist", "blocked": ["evil_*"]}])
            .evaluate({"action": "payment", "customer_id": "evil_corp"})
            .blocked
        )


class TestDailyLimit:
    def test_under_limit_two_calls(self):
        g = _g([{"id": "payment.daily_limit", "max_daily": 1000}])
        assert g.evaluate({"action": "payment", "amount": 500}).allowed
        assert g.evaluate({"action": "payment", "amount": 400}).allowed

    def test_at_threshold_allowed(self):
        g = _g([{"id": "payment.daily_limit", "max_daily": 1000}])
        assert g.evaluate({"action": "payment", "amount": 1000}).allowed

    def test_floats_summed_exact_threshold(self):
        # Pre-0.2.0 bug: ``int(amount)`` truncated 0.5 to 0 events, making
        # fractional charges invisible to the daily limit. Now 10 * 0.5 must
        # actually sum to 5.0 and saturate a max_daily=5 limit.
        g = _g([{"id": "payment.daily_limit", "max_daily": 5}])
        for _ in range(10):
            assert g.evaluate({"action": "payment", "amount": 0.5}).allowed
        # Any further positive amount tips the sum over the limit.
        assert g.evaluate({"action": "payment", "amount": 1}).blocked

    def test_large_amounts_summed(self):
        g = _g([{"id": "payment.daily_limit", "max_daily": 5_000_000}])
        assert g.evaluate({"action": "payment", "amount": 1_000_000, "agent_id": "a1"}).allowed
        assert g.evaluate({"action": "payment", "amount": 4_000_000, "agent_id": "a1"}).allowed
        assert g.evaluate({"action": "payment", "amount": 1, "agent_id": "a1"}).blocked

    def test_isolation_by_agent(self):
        g = _g([{"id": "payment.daily_limit", "max_daily": 1000}])
        g.evaluate({"action": "payment", "amount": 1000, "agent_id": "a1"})
        # a2 should still be at zero spent
        assert g.evaluate({"action": "payment", "amount": 1000, "agent_id": "a2"}).allowed

    def test_window_purges_old_values(self):
        import time

        from diplomat_gate.models import PolicyResult, ToolCall
        from diplomat_gate.policies.payments import DailyLimitPolicy
        from diplomat_gate.state import StateStore

        store = StateStore()
        policy = DailyLimitPolicy(
            policy_id="payment.daily_limit",
            name="Daily Limit",
            domain="payment",
            max_daily=1000,
        )
        # Inject an expired big value (> 24h ago); it must not count.
        store.record_value(
            "payment.daily_limit",
            "_global:daily_sum",
            999.0,
            timestamp=time.time() - 86400.0 - 3600,
        )
        tc = ToolCall(action="payment", params={"amount": 999.0})
        assert policy.evaluate(tc, store) == PolicyResult.PASS
