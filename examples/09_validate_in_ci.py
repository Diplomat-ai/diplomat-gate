"""09 — validate gate.yaml programmatically (CI usage).

Demonstrates using ``validate_config()`` directly in a script to fail fast
when a gate.yaml has errors, before any runtime evaluation occurs.

Run::

    python examples/09_validate_in_ci.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from diplomat_gate.validation import format_report_text, validate_config

# Locate gate.yaml.example relative to this file, whether the script is run
# from the repo root or from inside the examples/ directory.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent if (_HERE.parent / "gate.yaml.example").exists() else _HERE
GATE_YAML = _REPO / "gate.yaml.example"


def main() -> int:
    print(f"Validating: {GATE_YAML}")

    try:
        report = validate_config(str(GATE_YAML))
    except FileNotFoundError:
        print(f"ERROR: file not found: {GATE_YAML}", file=sys.stderr)
        return 2
    except (ValueError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(format_report_text(report, use_color=False))

    if report.ok:
        print(f"\nPolicies loaded: {', '.join(report.policies_loaded)}")
        return 0

    print(
        f"\n{len(report.errors)} error(s) found — fix gate.yaml before deploying.", file=sys.stderr
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
