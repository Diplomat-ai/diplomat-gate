#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

PYTHONPATH=src python -m pytest tests/test_ai_act_doc.py -q

BAD_CLAIMS=$(grep -ciE "is compliant|ensures compliance|AI Act compliant|guarantees" docs/ai-act-evidence.md || true)
assert_eq "$BAD_CLAIMS" "0" "la page ne doit contenir aucune affirmation de conformité"

ROWS=$(grep -c "^| " docs/ai-act-evidence.md || true)
[ "$ROWS" -ge 5 ] || { echo "FAIL: table doit avoir >= 5 lignes (en-tête + séparateur + 3 exigences), trouvé $ROWS"; exit 1; }

grep -qi "pending legal review" docs/ai-act-evidence.md || { echo "FAIL: bandeau 'pending legal review' absent"; exit 1; }
