from diplomat_gate import Gate


def _g(p):
    return Gate.from_dict({"email": p})


class TestDomainBlocklist:
    def test_safe(self):
        assert _g([{"id": "email.domain_blocklist", "blocked": ["*.banque-*.fr"]}]).evaluate(
            {"action": "send_email", "to": "hi@startup.com"}).allowed

    def test_blocked(self):
        assert _g([{"id": "email.domain_blocklist", "blocked": ["*.banque-*.fr"]}]).evaluate(
            {"action": "send_email", "to": "cfo@banque-marseille.fr"}).blocked

    def test_multiple(self):
        g = _g([{"id": "email.domain_blocklist", "blocked": ["*.banque-*.fr", "*.gouv.fr"]}])
        assert g.evaluate({"action": "send_email", "to": "x@gouv.fr"}).blocked
        assert g.evaluate({"action": "send_email", "to": "x@safe.com"}).allowed

    def test_list_recipients(self):
        assert _g([{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]).evaluate(
            {"action": "send_email", "to": ["a@good.com", "b@evil.com"]}).blocked


class TestRateLimit:
    def test_under(self):
        g = _g([{"id": "email.rate_limit", "max": 3, "window": "1h"}])
        for _ in range(3):
            assert g.evaluate({"action": "send_email", "to": "a@b.com"}).allowed

    def test_over(self):
        g = _g([{"id": "email.rate_limit", "max": 2, "window": "1h"}])
        g.evaluate({"action": "send_email", "to": "a@b.com"})
        g.evaluate({"action": "send_email", "to": "b@b.com"})
        assert g.evaluate({"action": "send_email", "to": "c@b.com"}).blocked


class TestContentScan:
    def test_clean(self):
        assert _g([{"id": "email.content_scan", "patterns": ["credit_card"]}]).evaluate(
            {"action": "send_email", "to": "a@b.com", "body": "Hello!"}).allowed

    def test_credit_card(self):
        v = _g([{"id": "email.content_scan", "patterns": ["credit_card"]}]).evaluate(
            {"action": "send_email", "to": "a@b.com", "body": "Card: 4111 1111 1111 1111"})
        assert v.blocked and "credit_card" in v.violations[0].message

    def test_api_key_in_subject(self):
        assert _g([{"id": "email.content_scan", "patterns": ["api_key"]}]).evaluate(
            {"action": "send_email", "to": "a@b.com",
             "subject": "Key: sk_live_abc123def456ghi789jkl"}).blocked

    def test_ssn(self):
        assert _g([{"id": "email.content_scan", "patterns": ["ssn"]}]).evaluate(
            {"action": "send_email", "to": "a@b.com", "body": "SSN: 123-45-6789"}).blocked
