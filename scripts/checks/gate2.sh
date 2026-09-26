#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

DB=$(python3 -c "import tempfile; from pathlib import Path; print(Path(tempfile.gettempdir()) / 'diplomat-gate-example-04.db')")
rm -f "$DB"
python examples/04_audit_trail.py

N1=$(python tools/verify_receipts.py "$DB" | grep -oE '[0-9]+' | head -1)
diplomat-gate audit verify --db "$DB" > /tmp/cli_out.txt
N2=$(grep -oE '[0-9]+' /tmp/cli_out.txt | head -1)
assert_eq "$N1" "$N2" "vérificateur autonome et CLI doivent compter le même N"

sqlite3 "$DB" "UPDATE verdicts SET decision='CONTINUE' WHERE sequence=3;"
RC=0
python tools/verify_receipts.py "$DB" || RC=$?
assert_eq "$RC" "1" "doit détecter l'altération de sequence=3 (STOP falsifié en CONTINUE)"

IMPORTS=$(grep -E "^import|^from" tools/verify_receipts.py | grep -v "__future__" | sort -u | tr '\n' ',')
EXPECTED="import argparse,import hashlib,import json,import sqlite3,import sys,"
assert_eq "$IMPORTS" "$EXPECTED" "imports du vérificateur autonome doivent rester stdlib seule"

PYTHONPATH=src python -m pytest tests/test_receipt_format.py -q
