"""Tests for the human-in-the-loop review queue."""

from __future__ import annotations

import time

import pytest

from diplomat_gate import Gate, ReviewQueue, ReviewQueueError
from diplomat_gate.review import APPROVED, EXPIRED, PENDING, REJECTED


def _review_gate(db_audit: str | None = None, db_review: str | None = None) -> Gate:
    """A gate whose ``email.domain_blocklist`` triggers REVIEW (not STOP)."""
    return Gate.from_dict(
        {
            "email": [
                {
                    "id": "email.domain_blocklist",
                    "blocked": ["*.review.com"],
                    "on_fail": "REVIEW",
                }
            ]
        },
        audit_path=db_audit,
        review_queue_path=db_review,
    )


class TestReviewQueueBasics:
    def test_enqueue_returns_id_and_persists(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        verdict = gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        assert verdict.needs_review
        assert gate.review_queue.pending_count() == 1
        items = gate.review_queue.list()
        assert len(items) == 1
        assert items[0].pending and items[0].action == "send_email"
        gate.close()

    def test_continue_does_not_enqueue(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@ok.com"})
        assert gate.review_queue.pending_count() == 0
        gate.close()

    def test_stop_does_not_enqueue(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = Gate.from_dict(
            {"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]},
            review_queue_path=db,
        )
        gate.evaluate({"action": "send_email", "to": "u@evil.com"})
        # STOP, not REVIEW → queue stays empty.
        assert gate.review_queue.pending_count() == 0
        gate.close()

    def test_redaction_on_by_default(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "secret@hold.review.com"})
        item = gate.review_queue.list()[0]
        # 'to' is in SENSITIVE_FIELDS, so both params and violation context are hashed.
        assert item.params["to"].startswith("h:")
        assert item.violations[0]["context"]["to"].startswith("h:")
        gate.close()

    def test_redaction_off_keeps_raw(self, tmp_path):
        from diplomat_gate.models import (
            Decision,
            ToolCall,
            Verdict,
            Violation,
            _make_receipt,
        )

        db = str(tmp_path / "review.db")
        queue = ReviewQueue(db, redact_params=False)
        tc = ToolCall(action="send_email", params={"to": "secret@hold.review.com"})
        violations = [
            Violation(
                policy_id="email.domain_blocklist",
                policy_name="Email Domain Blocklist",
                severity="high",
                message="m",
            )
        ]
        receipt = _make_receipt(tc, Decision.REVIEW, violations, 1)
        verdict = Verdict(
            decision=Decision.REVIEW,
            violations=violations,
            receipt=receipt,
            latency_ms=0.1,
            tool_call=tc,
        )
        queue.enqueue(verdict)
        item = queue.list()[0]
        assert item.params["to"] == "secret@hold.review.com"
        queue.close()


class TestReviewQueueDecisions:
    def test_approve_flow(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        item = gate.review_queue.list()[0]
        decided = gate.review_queue.approve(item.item_id, reviewer="alice", note="ok")
        assert decided.status == APPROVED
        assert decided.decided_by == "alice"
        assert decided.decision_note == "ok"
        assert gate.review_queue.pending_count() == 0
        assert gate.review_queue.count(APPROVED) == 1
        gate.close()

    def test_reject_flow(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        item = gate.review_queue.list()[0]
        decided = gate.review_queue.reject(item.item_id, reviewer="bob")
        assert decided.status == REJECTED
        assert gate.review_queue.count(REJECTED) == 1
        gate.close()

    def test_double_decision_rejected(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        item = gate.review_queue.list()[0]
        gate.review_queue.approve(item.item_id, reviewer="alice")
        with pytest.raises(ReviewQueueError):
            gate.review_queue.reject(item.item_id, reviewer="bob")
        gate.close()

    def test_unknown_id(self, tmp_path):
        db = str(tmp_path / "review.db")
        queue = ReviewQueue(db)
        with pytest.raises(ReviewQueueError):
            queue.approve("does-not-exist", reviewer="alice")
        queue.close()

    def test_get_returns_none_for_missing(self, tmp_path):
        db = str(tmp_path / "review.db")
        queue = ReviewQueue(db)
        assert queue.get("missing") is None
        queue.close()

    def test_list_invalid_status(self, tmp_path):
        db = str(tmp_path / "review.db")
        queue = ReviewQueue(db)
        with pytest.raises(ValueError):
            queue.list(status="weird")
        queue.close()


class TestReviewQueueExpiry:
    def test_expire_due(self, tmp_path):
        db = str(tmp_path / "review.db")
        gate = Gate.from_dict(
            {
                "email": [
                    {
                        "id": "email.domain_blocklist",
                        "blocked": ["*.review.com"],
                        "on_fail": "REVIEW",
                    }
                ]
            },
            review_queue_path=db,
        )
        gate.review_queue._ttl = 0.01
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        time.sleep(0.05)
        n = gate.review_queue.expire_due()
        assert n == 1
        assert gate.review_queue.count(EXPIRED) == 1
        # Expired items can no longer be approved.
        item = gate.review_queue.list(status=EXPIRED)[0]
        with pytest.raises(ReviewQueueError):
            gate.review_queue.approve(item.item_id, reviewer="alice")
        gate.close()


class TestReviewCLI:
    def test_list_pending_text(self, tmp_path, capsys):
        from diplomat_gate.cli import main

        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        gate.close()
        rc = main(["--no-color", "review", "list", "--db", db])
        out = capsys.readouterr().out
        assert rc == 0
        assert "send_email" in out and PENDING in out

    def test_list_json(self, tmp_path, capsys):
        import json

        from diplomat_gate.cli import main

        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        gate.close()
        rc = main(["--no-color", "review", "list", "--db", db, "--json"])
        out = capsys.readouterr().out
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, list) and len(data) == 1

    def test_show_missing(self, tmp_path, capsys):
        from diplomat_gate.cli import main

        db = str(tmp_path / "review.db")
        ReviewQueue(db).close()  # initialise empty schema
        rc = main(["--no-color", "review", "show", "--db", db, "--id", "nope"])
        capsys.readouterr()
        assert rc == 1

    def test_approve_then_reject_fails(self, tmp_path, capsys):
        from diplomat_gate.cli import main

        db = str(tmp_path / "review.db")
        gate = _review_gate(db_review=db)
        gate.evaluate({"action": "send_email", "to": "u@hold.review.com"})
        item_id = gate.review_queue.list()[0].item_id
        gate.close()

        rc = main(
            [
                "--no-color",
                "review",
                "approve",
                "--db",
                db,
                "--id",
                item_id,
                "--reviewer",
                "alice",
                "--note",
                "ok",
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0 and "approved" in out

        rc2 = main(
            [
                "--no-color",
                "review",
                "reject",
                "--db",
                db,
                "--id",
                item_id,
                "--reviewer",
                "bob",
            ]
        )
        capsys.readouterr()
        assert rc2 == 1
