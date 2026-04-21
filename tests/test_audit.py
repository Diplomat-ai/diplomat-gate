from diplomat_gate import Gate


class TestAudit:
    def test_recorded(self, tmp_path):
        db = str(tmp_path / "test.db")
        g = Gate.from_dict(
            {"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]}, audit_path=db
        )
        g.evaluate({"action": "charge_card", "amount": 500})
        g.evaluate({"action": "charge_card", "amount": 5000})
        assert g.audit.count() == 2
        assert g.audit.count("CONTINUE") == 1
        assert g.audit.count("STOP") == 1
        g.close()

    def test_query(self, tmp_path):
        db = str(tmp_path / "test.db")
        g = Gate.from_dict(
            {"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]}, audit_path=db
        )
        g.evaluate({"action": "charge_card", "amount": 500})
        rows = g.audit.query()
        assert len(rows) == 1 and rows[0]["decision"] == "CONTINUE"
        g.close()


class TestRedaction:
    def test_redaction_on_by_default_hashes_sensitive_context(self, tmp_path):
        import json

        db = str(tmp_path / "test.db")
        g = Gate.from_dict(
            {"email": [{"id": "email.domain_blocklist", "blocked": ["*.evil.com"]}]},
            audit_path=db,
        )
        g.evaluate({"action": "send_email", "to": "user@evil.com"})
        rows = g.audit.query()
        violations = json.loads(rows[0]["violations"])
        assert violations[0]["context"]["to"].startswith("h:")
        assert "user@evil.com" not in rows[0]["violations"]
        g.close()

    def test_redaction_off_keeps_raw_context(self, tmp_path):
        import json

        from diplomat_gate.audit import AuditLog
        from diplomat_gate.models import (
            Decision,
            ToolCall,
            Verdict,
            Violation,
            _make_receipt,
        )

        db = str(tmp_path / "test.db")
        audit = AuditLog(db, redact_violations=False)
        tc = ToolCall(action="send_email", params={"to": "user@evil.com"})
        violations = [
            Violation(
                policy_id="email.domain_blocklist",
                policy_name="Email Domain Blocklist",
                severity="critical",
                message="blocked",
            )
        ]
        receipt = _make_receipt(tc, Decision.STOP, violations, 1)
        verdict = Verdict(
            decision=Decision.STOP,
            violations=violations,
            receipt=receipt,
            latency_ms=0.1,
            tool_call=tc,
        )
        audit.record(verdict)
        rows = audit.query()
        recorded = json.loads(rows[0]["violations"])
        assert recorded[0]["context"]["to"] == "user@evil.com"
        audit.close()


# ---------------------------------------------------------------------------
# Hash chain (Phase 2)
# ---------------------------------------------------------------------------


def _make_gate(db: str):
    return Gate.from_dict(
        {"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]},
        audit_path=db,
    )


class TestHashChain:
    def test_insert_first_uses_genesis(self, tmp_path):
        import sqlite3

        from diplomat_gate.audit import GENESIS_HASH

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.close()
        conn = sqlite3.connect(db)
        try:
            seq, prev, rec = conn.execute(
                "SELECT sequence, previous_hash, record_hash FROM verdicts"
            ).fetchone()
        finally:
            conn.close()
        assert seq == 1
        assert prev == GENESIS_HASH
        assert len(rec) == 64
        assert rec != GENESIS_HASH

    def test_sequence_monotonic(self, tmp_path):
        import sqlite3

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        for i in range(5):
            g.evaluate({"action": "charge_card", "amount": 100 + i})
        g.close()
        conn = sqlite3.connect(db)
        try:
            sequences = [
                row[0]
                for row in conn.execute("SELECT sequence FROM verdicts ORDER BY sequence ASC")
            ]
        finally:
            conn.close()
        assert sequences == [1, 2, 3, 4, 5]

    def test_record_hash_deterministic(self):
        from diplomat_gate.audit import compute_record_hash

        record = {
            "verdict_id": "abc",
            "sequence": 1,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "agent_id": "agent-1",
            "action": "charge",
            "params_hash": "deadbeef",
            "decision": "CONTINUE",
            "policies_evaluated": 2,
            "policies_failed": 0,
            "violations": "[]",
            "latency_ms": 0.5,
        }
        h1 = compute_record_hash(record, "0" * 64)
        h2 = compute_record_hash(dict(record), "0" * 64)
        assert h1 == h2
        # changing any field changes the digest
        mutated = dict(record, decision="STOP")
        assert compute_record_hash(mutated, "0" * 64) != h1
        # changing previous_hash changes the digest
        assert compute_record_hash(record, "1" * 64) != h1

    def test_chain_valid_after_inserts(self, tmp_path):
        from diplomat_gate.audit import verify_chain

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        for amt in (100, 500, 5000, 800):
            g.evaluate({"action": "charge_card", "amount": amt})
        g.close()
        result = verify_chain(db)
        assert result.valid is True
        assert result.records_checked == 4
        assert result.first_invalid_sequence is None

    def test_tamper_violations_detected(self, tmp_path):
        import sqlite3

        from diplomat_gate.audit import verify_chain

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.evaluate({"action": "charge_card", "amount": 5000})
        g.close()
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "UPDATE verdicts SET violations = ? WHERE sequence = 2",
                ("[]",),
            )
            conn.commit()
        finally:
            conn.close()
        result = verify_chain(db)
        assert result.valid is False
        assert result.first_invalid_sequence == 2
        assert "record_hash" in (result.error or "")

    def test_tamper_previous_hash_detected(self, tmp_path):
        import sqlite3

        from diplomat_gate.audit import verify_chain

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.evaluate({"action": "charge_card", "amount": 200})
        g.close()
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "UPDATE verdicts SET previous_hash = ? WHERE sequence = 2",
                ("f" * 64,),
            )
            conn.commit()
        finally:
            conn.close()
        result = verify_chain(db)
        assert result.valid is False
        assert result.first_invalid_sequence == 2
        assert "previous_hash" in (result.error or "")

    def test_chain_survives_restart(self, tmp_path):
        from diplomat_gate.audit import verify_chain

        db = str(tmp_path / "chain.db")
        g1 = _make_gate(db)
        g1.evaluate({"action": "charge_card", "amount": 100})
        g1.evaluate({"action": "charge_card", "amount": 200})
        g1.close()
        # Re-open the database with a fresh AuditLog instance and append.
        g2 = _make_gate(db)
        g2.evaluate({"action": "charge_card", "amount": 300})
        g2.close()
        result = verify_chain(db)
        assert result.valid is True
        assert result.records_checked == 3

    def test_verify_chain_does_not_mutate_db(self, tmp_path):
        import hashlib

        from diplomat_gate.audit import verify_chain

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.evaluate({"action": "charge_card", "amount": 5000})
        g.close()

        def file_digest(path: str) -> str:
            with open(path, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()

        before = file_digest(db)
        verify_chain(db)  # valid case
        # tamper, then verify again
        import sqlite3

        conn = sqlite3.connect(db)
        try:
            conn.execute("UPDATE verdicts SET decision = 'STOP' WHERE sequence = 1")
            conn.commit()
        finally:
            conn.close()
        between = file_digest(db)
        verify_chain(db)
        after = file_digest(db)
        # verify_chain ran twice and changed nothing on either side
        assert before != between  # tamper changed the file
        assert between == after  # verify did NOT change the file


class TestMigration:
    def test_migration_from_legacy_schema(self, tmp_path):
        import sqlite3
        import warnings as _warnings

        from diplomat_gate.audit import AuditLog, rebuild_chain, verify_chain

        db = str(tmp_path / "legacy.db")
        # Materialize a 0.1.x-style schema with one row.
        conn = sqlite3.connect(db)
        try:
            conn.executescript(
                """
                CREATE TABLE verdicts (
                    verdict_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    agent_id TEXT DEFAULT '',
                    action TEXT NOT NULL,
                    params_hash TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    policies_evaluated INTEGER NOT NULL,
                    policies_failed INTEGER NOT NULL,
                    violations TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                """
            )
            conn.execute(
                "INSERT INTO verdicts (verdict_id, timestamp, action, params_hash, "
                "decision, policies_evaluated, policies_failed, violations, latency_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "legacy-1",
                    "2026-01-01T00:00:00+00:00",
                    "charge_card",
                    "deadbeef",
                    "CONTINUE",
                    1,
                    0,
                    "[]",
                    0.1,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # Opening the AuditLog should migrate the schema and emit a warning.
        with _warnings.catch_warnings(record=True) as captured:
            _warnings.simplefilter("always")
            audit = AuditLog(db)
            audit.close()
        assert any("legacy audit schema" in str(w.message) for w in captured)

        # Legacy row is un-chained: verify_chain should report invalid.
        result = verify_chain(db)
        assert result.valid is False

        # rebuild_chain re-numbers and re-hashes everything.
        n = rebuild_chain(db)
        assert n == 1
        result = verify_chain(db)
        assert result.valid is True
        assert result.records_checked == 1

        # Subsequent inserts continue the chain at sequence=2.
        audit = AuditLog(db)
        try:
            from diplomat_gate.models import (
                Decision,
                ToolCall,
                Verdict,
                _make_receipt,
            )

            tc = ToolCall(action="charge_card", params={"amount": 50})
            receipt = _make_receipt(tc, Decision.CONTINUE, [], 1)
            verdict = Verdict(
                decision=Decision.CONTINUE,
                violations=[],
                receipt=receipt,
                latency_ms=0.1,
                tool_call=tc,
            )
            audit.record(verdict)
        finally:
            audit.close()
        result = verify_chain(db)
        assert result.valid is True
        assert result.records_checked == 2


class TestCLI:
    def test_verify_ok(self, tmp_path, capsys):
        from diplomat_gate.cli import main

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.close()
        rc = main(["--no-color", "audit", "verify", "--db", db])
        out = capsys.readouterr().out
        assert rc == 0
        assert "OK" in out

    def test_verify_invalid(self, tmp_path, capsys):
        import sqlite3

        from diplomat_gate.cli import main

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.close()
        conn = sqlite3.connect(db)
        try:
            conn.execute("UPDATE verdicts SET decision = 'STOP' WHERE sequence = 1")
            conn.commit()
        finally:
            conn.close()
        rc = main(["--no-color", "audit", "verify", "--db", db])
        out = capsys.readouterr().out
        assert rc == 1
        assert "INVALID" in out

    def test_rebuild_chain(self, tmp_path, capsys):
        from diplomat_gate.cli import main

        db = str(tmp_path / "chain.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.evaluate({"action": "charge_card", "amount": 200})
        g.close()
        rc = main(["--no-color", "audit", "rebuild-chain", "--db", db])
        out = capsys.readouterr().out
        assert rc == 0
        assert "2" in out

    def test_verify_missing_file(self, tmp_path, capsys):
        from diplomat_gate.cli import main

        db = str(tmp_path / "does_not_exist.db")
        rc = main(["--no-color", "audit", "verify", "--db", db])
        # sqlite3.connect creates an empty file; verify reports invalid (no table)
        # → exit code 1 (invalid), or 2 if connect itself fails.
        assert rc in (1, 2)
        capsys.readouterr()
