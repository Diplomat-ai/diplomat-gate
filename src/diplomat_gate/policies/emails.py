"""Email policies — domain blocklist, rate limit, business hours, content scan."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..models import PolicyResult, ToolCall
from ..state import StateStore
from .base import Policy


def _parse_window(window: str) -> float:
    window = window.strip().lower()
    if window.endswith("h"):
        return float(window[:-1]) * 3600
    if window.endswith("m"):
        return float(window[:-1]) * 60
    if window.endswith("s"):
        return float(window[:-1])
    if window.endswith("d"):
        return float(window[:-1]) * 86400
    return float(window)


def _extract_domain(email: str) -> str:
    if "@" in email:
        return email.split("@", 1)[1].lower().strip()
    return email.lower().strip()


def _get_recipients(tool_call: ToolCall) -> list[str]:
    to = tool_call.params.get("to", "")
    if isinstance(to, list):
        return [str(r) for r in to if r]
    return [str(to)] if to else []


def _domain_matches(domain: str, pattern: str) -> bool:
    """Match domain against a glob pattern.

    Allows '*.foo-*.bar' to match 'foo-something.bar' (zero-width prefix).
    """
    p = pattern.lower()
    if fnmatch.fnmatch(domain, p):
        return True
    # Strip leading '*.' so that e.g. '*.gouv.fr' also matches 'gouv.fr'
    return p.startswith("*.") and fnmatch.fnmatch(domain, p[2:])


@dataclass
class DomainBlocklistPolicy(Policy):
    blocked: list[str] = field(default_factory=list)

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        for recipient in _get_recipients(tool_call):
            domain = _extract_domain(recipient)
            for pattern in self.blocked:
                if "@" in pattern:
                    check = recipient.lower()
                    if fnmatch.fnmatch(check, pattern.lower()):
                        return PolicyResult.FAIL
                else:
                    if _domain_matches(domain, pattern):
                        return PolicyResult.FAIL
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        recipients = _get_recipients(tool_call)
        domain = _extract_domain(recipients[0]) if recipients else "unknown"
        return f"Domain '{domain}' is on the blocklist"


@dataclass
class EmailRateLimitPolicy(Policy):
    max: int = 50
    window: str = "1h"

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        window_s = _parse_window(self.window)
        scope = tool_call.agent_id or "_global"
        count = state.count_events(self.policy_id, scope, window_s)
        if count >= self.max:
            return PolicyResult.FAIL
        state.record_event(self.policy_id, scope)
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return f"Email rate limit exceeded: max {self.max} per {self.window}"


@dataclass
class BusinessHoursPolicy(Policy):
    start: int = 9
    end: int = 18
    tz: str = "UTC"
    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        try:
            tz = ZoneInfo(self.tz)
        except KeyError:
            tz = timezone.utc
        now = datetime.now(tz)
        if now.weekday() not in self.days:
            return PolicyResult.FAIL
        if not (self.start <= now.hour < self.end):
            return PolicyResult.FAIL
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return (
            f"Outside business hours ({self.start}:00\u2013{self.end}:00 {self.tz}, Mon\u2013Fri)"
        )


_BUILTIN_PATTERNS: dict[str, re.Pattern] = {
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "api_key": re.compile(
        r"(?:sk[_-](?:live|test|ant)[_-][a-zA-Z0-9]{20,})"
        r"|(?:AKIA[0-9A-Z]{16})"
        r"|(?:ghp_[a-zA-Z0-9]{36})"
        r"|(?:xoxb-[a-zA-Z0-9-]+)",
        re.IGNORECASE,
    ),
    "password": re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


@dataclass
class ContentScanPolicy(Policy):
    patterns: list[str] = field(default_factory=lambda: ["credit_card", "ssn", "api_key"])

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        text = f"{tool_call.params.get('subject', '')} {tool_call.params.get('body', '')}"
        if not text.strip():
            return PolicyResult.PASS
        for name in self.patterns:
            regex = _BUILTIN_PATTERNS.get(name)
            if regex and regex.search(text):
                return PolicyResult.FAIL
        return PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        text = f"{tool_call.params.get('subject', '')} {tool_call.params.get('body', '')}"
        matched = [n for n in self.patterns if (r := _BUILTIN_PATTERNS.get(n)) and r.search(text)]
        return f"Sensitive data detected: {', '.join(matched)}"
