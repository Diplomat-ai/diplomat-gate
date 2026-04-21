"""diplomat-gate — Approval gates for AI agent payments and emails.

from diplomat_gate import Gate
gate = Gate.from_yaml("gate.yaml")
verdict = gate.evaluate({"action": "charge_card", "amount": 15000})
"""

from ._version import __version__
from .decorator import configure, gate
from .engine import Gate
from .exceptions import Blocked, NeedsReview
from .models import Decision, Receipt, ToolCall, Verdict, Violation
from .review import ReviewItem, ReviewQueue, ReviewQueueError

__all__ = [
    "__version__",
    "Gate",
    "Decision",
    "ToolCall",
    "Verdict",
    "Violation",
    "Receipt",
    "gate",
    "configure",
    "Blocked",
    "NeedsReview",
    "ReviewQueue",
    "ReviewItem",
    "ReviewQueueError",
]
