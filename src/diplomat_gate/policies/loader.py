"""Load policies from YAML files or Python dicts."""

from __future__ import annotations

from typing import Any

from .base import Policy
from .emails import (
    BusinessHoursPolicy,
    ContentScanPolicy,
    DomainBlocklistPolicy,
    EmailRateLimitPolicy,
)
from .payments import (
    AmountLimitPolicy,
    DailyLimitPolicy,
    DuplicateDetectionPolicy,
    RecipientBlocklistPolicy,
    VelocityPolicy,
)

_POLICY_MAP: dict[str, type[Policy]] = {
    "payment.amount_limit": AmountLimitPolicy,
    "payment.velocity": VelocityPolicy,
    "payment.daily_limit": DailyLimitPolicy,
    "payment.duplicate_detection": DuplicateDetectionPolicy,
    "payment.recipient_blocklist": RecipientBlocklistPolicy,
    "email.domain_blocklist": DomainBlocklistPolicy,
    "email.rate_limit": EmailRateLimitPolicy,
    "email.business_hours": BusinessHoursPolicy,
    "email.content_scan": ContentScanPolicy,
}


def _build_policy(entry: dict[str, Any]) -> Policy:
    policy_id = entry.get("id", "")
    cls = _POLICY_MAP.get(policy_id)
    if cls is None:
        raise ValueError(f"Unknown policy: {policy_id!r}. Available: {list(_POLICY_MAP)}")

    domain = policy_id.split(".")[0] if "." in policy_id else "any"
    common = {"id", "name", "domain", "severity", "on_fail", "enabled"}

    kwargs: dict[str, Any] = {
        "policy_id": policy_id,
        "name": entry.get("name", policy_id.replace(".", " ").replace("_", " ").title()),
        "domain": domain,
        "severity": entry.get("severity", "high"),
        "on_fail": entry.get("on_fail", "STOP"),
        "enabled": entry.get("enabled", True),
    }
    for k, v in entry.items():
        if k not in common:
            kwargs[k] = v

    return cls(**kwargs)


def load_from_dict(config: dict[str, Any]) -> list[Policy]:
    policies: list[Policy] = []
    if "policies" in config:
        for entry in config["policies"]:
            policies.append(_build_policy(entry))
        return policies
    for domain in ("payment", "email"):
        if domain in config:
            for entry in config[domain]:
                policies.append(_build_policy(entry))
    return policies


def load_from_yaml(path: str) -> list[Policy]:
    try:
        import yaml
    except ImportError as err:
        raise ImportError(
            "PyYAML required for YAML files. Install: pip install diplomat-gate[yaml]"
        ) from err
    with open(path) as f:
        config = yaml.safe_load(f)
    return load_from_dict(config)


def iter_registered_policies() -> dict[str, type[Policy]]:
    """Return a copy of the policy registry.

    Read-only — mutations on the returned dict have no effect on the
    internal registry. Used by ``diplomat_gate.validation``.
    """
    return dict(_POLICY_MAP)
