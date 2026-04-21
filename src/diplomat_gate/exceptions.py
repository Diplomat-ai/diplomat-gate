"""Exceptions raised by diplomat-gate when a tool call is blocked or needs review."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Verdict


class GateDecision(Exception):
    """Base exception for gate decisions that prevent execution."""

    def __init__(self, verdict: Verdict):
        self.verdict = verdict
        super().__init__(str(verdict.decision.value))


class Blocked(GateDecision):
    """Raised when a tool call is STOPPED by policy."""

    pass


class NeedsReview(GateDecision):
    """Raised when a tool call requires human REVIEW before execution."""

    pass
