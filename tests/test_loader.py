"""Tests for YAML/dict loader."""

import pytest

from diplomat_gate.policies import load_from_dict
from diplomat_gate.policies.emails import DomainBlocklistPolicy
from diplomat_gate.policies.payments import AmountLimitPolicy, VelocityPolicy


class TestLoadFromDict:
    def test_payment_section(self):
        policies = load_from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 5000}]})
        assert len(policies) == 1
        assert isinstance(policies[0], AmountLimitPolicy)
        assert policies[0].max_amount == 5000

    def test_email_section(self):
        policies = load_from_dict(
            {"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]}
        )
        assert len(policies) == 1
        assert isinstance(policies[0], DomainBlocklistPolicy)

    def test_policies_key(self):
        policies = load_from_dict(
            {
                "policies": [
                    {"id": "payment.amount_limit", "max_amount": 1000},
                    {"id": "email.domain_blocklist", "blocked": []},
                ]
            }
        )
        assert len(policies) == 2

    def test_unknown_policy_raises(self):
        with pytest.raises(ValueError, match="Unknown policy"):
            load_from_dict({"payment": [{"id": "payment.nonexistent"}]})

    def test_severity_propagated(self):
        policies = load_from_dict(
            {
                "payment": [
                    {"id": "payment.amount_limit", "max_amount": 1000, "severity": "critical"}
                ]
            }
        )
        assert policies[0].severity == "critical"

    def test_on_fail_propagated(self):
        policies = load_from_dict(
            {"payment": [{"id": "payment.amount_limit", "max_amount": 1000, "on_fail": "REVIEW"}]}
        )
        assert policies[0].on_fail == "REVIEW"

    def test_velocity_window(self):
        policies = load_from_dict(
            {"payment": [{"id": "payment.velocity", "max_txn": 5, "window": "30m"}]}
        )
        assert isinstance(policies[0], VelocityPolicy)
        assert policies[0].window == "30m"
        assert policies[0].max_txn == 5
