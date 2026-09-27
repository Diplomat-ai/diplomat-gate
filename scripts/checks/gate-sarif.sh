#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

DB=$(python3 -c "import tempfile; from pathlib import Path; print(Path(tempfile.gettempdir()) / 'diplomat-gate-sarif-check.db')")
rm -f "$DB"

python3 -c "
from diplomat_gate import Gate
gate = Gate.from_dict(
    {'payment': [{'id': 'payment.amount_limit', 'max_amount': 1000}]}, audit_path='$DB'
)
gate.evaluate({'action': 'charge_card', 'amount': 100})
gate.evaluate({'action': 'charge_card', 'amount': 5000})
gate.close()
"

diplomat-gate audit export --db "$DB" --format sarif > /tmp/gate-sarif.json
python3 -c "
import json
sarif = json.load(open('/tmp/gate-sarif.json'))
assert sarif['version'] == '2.1.0'
results = sarif['runs'][0]['results']
assert len(results) == 1, results
assert results[0]['ruleId'] == 'payment.amount_limit'
assert results[0]['level'] == 'error'
print('SARIF OK: 1 result, ruleId=payment.amount_limit, level=error')
"

diplomat-gate audit export --db "$DB" --format json > /tmp/gate-export.jsonl
LINES=$(wc -l < /tmp/gate-export.jsonl | tr -d ' ')
assert_eq "$LINES" "2" "JSONL export doit avoir 2 lignes (2 verdicts enregistrés)"

python3 -m pytest tests/test_audit.py -k "Export" -q
