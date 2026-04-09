from diplomat_gate import Gate


class TestAudit:
    def test_recorded(self, tmp_path):
        db = str(tmp_path / "test.db")
        g = Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]},
                           audit_path=db)
        g.evaluate({"action": "charge_card", "amount": 500})
        g.evaluate({"action": "charge_card", "amount": 5000})
        assert g.audit.count() == 2
        assert g.audit.count("CONTINUE") == 1
        assert g.audit.count("STOP") == 1
        g.close()

    def test_query(self, tmp_path):
        db = str(tmp_path / "test.db")
        g = Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 1000}]},
                           audit_path=db)
        g.evaluate({"action": "charge_card", "amount": 500})
        rows = g.audit.query()
        assert len(rows) == 1 and rows[0]["decision"] == "CONTINUE"
        g.close()
