"""
Vendored from openclaw/openclaw @ b2e8b7d4bb2f22eaa16f5c4b07547774e90b65a5
Source: TypeScript codebase — no Python SDK or email-send module exists in the
upstream repo. This file is a FUNCTIONAL REPRODUCTION, not a literal port.

OpenClaw's email capability is distributed across the agent runtime and
provider extensions (e.g. the gmail/SMTP OAuth flow wired into the gateway
via extensions). The behavior that matters for this demo — that an agent can
dispatch an outbound email-like action on the user's behalf with no
deterministic pre-execution approval check by default — is reproduced faithfully.

Verify the upstream codebase at:
  https://github.com/openclaw/openclaw/tree/b2e8b7d4bb2f22eaa16f5c4b07547774e90b65a5

This demo is NOT a claim that OpenClaw is broken. OpenClaw is an excellent
piece of software with a clear security posture:

  "Hard enforcement is the operator's responsibility, not the framework's.
   System prompt guardrails are soft guidance; enforcement comes from tool
   policy, exec approvals, sandboxing, and channel allowlists."

diplomat-gate is one implementation of that operator enforcement layer.

The SMTP/OAuth call is replaced with a local MockEmailClient that records
what *would* have been sent.  Nothing leaves the machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockEmailClient:
    """Stand-in for the real SMTP / OAuth email provider.

    Records sends instead of transmitting. Used only by this demo.
    """

    sent: list[dict[str, Any]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str, **kwargs: Any) -> dict[str, Any]:
        record = {"to": to, "subject": subject, "body_len": len(body), **kwargs}
        self.sent.append(record)
        return {"status": "sent", "id": f"mock_{len(self.sent):06d}"}


def agent_send_email(
    client: MockEmailClient,
    to: str,
    subject: str,
    body: str,
    *,
    acting_on_behalf_of: str = "user",
    **_kwargs: Any,
) -> dict[str, Any]:
    """Functional reproduction of the OpenClaw agent send-email flow.

    The agent decides that dispatching this email is the right action.
    As shipped, the framework executes the send regardless of explicit
    user approval — because approval enforcement is documented as the
    operator's responsibility, not the framework's.

    No deterministic pre-execution check on:
      - whether the user explicitly approved *this specific* email
      - whether the recipient is on a sensitive-correspondence allowlist
      - whether the email contains legal language that warrants human review
      - idempotency (was a similar email already sent?)

    These are all guards the operator is expected to add externally.
    This demo shows what diplomat-gate adds in 10 lines of YAML.
    """
    return client.send(to=to, subject=subject, body=body, acting_on_behalf_of=acting_on_behalf_of)
