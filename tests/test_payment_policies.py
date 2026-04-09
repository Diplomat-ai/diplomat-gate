from diplomat_gate import Gate


def _g(p):
    return Gate.from_dict({"payment": p})


class TestAmountLimit:
    def test_under(self):
        assert _g([{"id": "payment.amount_limit", "max_amount": 1000}]).evaluate(
            {"action": "charge_card", "amount": 999}).allowed

    def test_at(self):
        assert _g([{"id": "payment.amount_limit", "max_amount": 1000}]).evaluate(
            {"action": "charge_card", "amount": 1000}).allowed

    def test_over(self):
        assert _g([{"id": "payment.amount_limit", "max_amount": 1000}]).evaluate(
            {"action": "charge_card", "amount": 1001}).blocked

    def test_string_amount(self):
        assert _g([{"id": "payment.amount_limit", "max_amount": 1000}]).evaluate(
            {"action": "charge_card", "amount": "5000"}).blocked

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
        assert _g([{"id": "payment.duplicate_detection", "window": "5m"}]).evaluate(
            {"action": "payment", "amount": 100, "customer_id": "c1"}).allowed

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
        assert _g([{"id": "payment.recipient_blocklist", "blocked": ["evil_*"]}]).evaluate(
            {"action": "payment", "customer_id": "cus_good"}).allowed

    def test_blocked(self):
        assert _g([{"id": "payment.recipient_blocklist", "blocked": ["evil_*"]}]).evaluate(
            {"action": "payment", "customer_id": "evil_corp"}).blocked
