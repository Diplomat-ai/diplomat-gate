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


class TestExport:
    def _seed(self, db: str) -> None:
        from diplomat_gate.audit import AuditLog
        from diplomat_gate.models import (
            Decision,
            ToolCall,
            Verdict,
            Violation,
            _make_receipt,
        )

        audit = AuditLog(db, redact_violations=False)
        try:
            tc1 = ToolCall(action="charge_card", params={"amount": 50})
            receipt1 = _make_receipt(tc1, Decision.CONTINUE, [], 1)
            audit.record(
                Verdict(
                    decision=Decision.CONTINUE,
                    violations=[],
                    receipt=receipt1,
                    latency_ms=0.1,
                    tool_call=tc1,
                )
            )

            violation = Violation(
                policy_id="payment.amount_limit",
                policy_name="Payment Amount Limit",
                severity="critical",
                message="amount exceeds limit",
            )
            tc2 = ToolCall(action="charge_card", params={"amount": 5000})
            receipt2 = _make_receipt(tc2, Decision.STOP, [violation], 1)
            audit.record(
                Verdict(
                    decision=Decision.STOP,
                    violations=[violation],
                    receipt=receipt2,
                    latency_ms=0.2,
                    tool_call=tc2,
                )
            )
        finally:
            audit.close()

    def test_export_records_reads_in_sequence_order(self, tmp_path):
        from diplomat_gate.audit import export_records

        db = str(tmp_path / "export.db")
        self._seed(db)
        records = export_records(db)
        assert [r["sequence"] for r in records] == [1, 2]
        assert records[1]["decision"] == "STOP"
        assert records[1]["violations"][0]["policy_id"] == "payment.amount_limit"

    def test_to_sarif_skips_continue_and_maps_stop_to_error(self, tmp_path):
        from diplomat_gate.audit import export_records, to_sarif

        db = str(tmp_path / "export.db")
        self._seed(db)
        sarif = to_sarif(export_records(db))
        assert sarif["version"] == "2.1.0"
        results = sarif["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["ruleId"] == "payment.amount_limit"
        assert results[0]["level"] == "error"
        assert results[0]["message"]["text"] == "amount exceeds limit"
        rule_ids = {rule["id"] for rule in sarif["runs"][0]["tool"]["driver"]["rules"]}
        assert rule_ids == {"payment.amount_limit"}

    def test_to_jsonl_emits_one_record_per_line(self, tmp_path):
        import json

        from diplomat_gate.audit import export_records, to_jsonl

        db = str(tmp_path / "export.db")
        self._seed(db)
        lines = to_jsonl(export_records(db)).splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["sequence"] == 1
        assert json.loads(lines[1])["sequence"] == 2

    def test_export_records_since_until_filters(self, tmp_path):
        from diplomat_gate.audit import export_records

        db = str(tmp_path / "export.db")
        self._seed(db)
        all_records = export_records(db)
        far_future = "9999-01-01T00:00:00"
        assert export_records(db, since=far_future) == []
        far_past = "0001-01-01T00:00:00"
        assert export_records(db, until=far_past) == []
        assert export_records(db, since=far_past, until=far_future) == all_records


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

    def test_export_sarif(self, tmp_path, capsys):
        import json

        from diplomat_gate.cli import main

        db = str(tmp_path / "export.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 5000})
        g.close()
        rc = main(["--no-color", "audit", "export", "--db", db, "--format", "sarif"])
        out = capsys.readouterr().out
        assert rc == 0
        sarif = json.loads(out)
        assert sarif["version"] == "2.1.0"
        assert sarif["runs"][0]["results"][0]["ruleId"] == "payment.amount_limit"

    def test_export_json_defaults_and_since_filter(self, tmp_path, capsys):
        import json

        from diplomat_gate.cli import main

        db = str(tmp_path / "export.db")
        g = _make_gate(db)
        g.evaluate({"action": "charge_card", "amount": 100})
        g.close()
        rc = main(["--no-color", "audit", "export", "--db", db, "--format", "json"])
        out = capsys.readouterr().out
        assert rc == 0
        assert json.loads(out.strip())["sequence"] == 1

        rc = main(
            [
                "--no-color",
                "audit",
                "export",
                "--db",
                db,
                "--format",
                "json",
                "--since",
                "9999-01-01T00:00:00",
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert out.strip() == ""

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
