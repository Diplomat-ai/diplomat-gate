"""02 — load policies from a YAML file.

Requires the ``yaml`` extra::

    pip install -e ".[yaml]"

Run::

    python examples/02_yaml_config.py
"""

from __future__ import annotations

from pathlib import Path

from diplomat_gate import Gate

CONFIG = Path(__file__).resolve().parent / "configs" / "gate.yaml"


def main() -> None:
    gate = Gate.from_yaml(str(CONFIG))
    print(f"loaded {len(gate.policies)} policy(ies) from {CONFIG.name}")

    samples = [
        {"action": "charge_card", "amount": 500},
        {"action": "charge_card", "amount": 5000},
        {"action": "send_email", "to": "user@evil.com"},
        {"action": "send_email", "to": "user@ok.com"},
    ]
    for call in samples:
        verdict = gate.evaluate(call)
        print(f"{call} -> {verdict.decision.value}")


if __name__ == "__main__":
    main()
