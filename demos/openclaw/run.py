"""
The OpenClaw demo — "oh shit moment" in 60 seconds.

Run from repo root:
    python demos/openclaw/run.py

No API key. No Docker. No setup. Just read the output.

This demo reproduces a publicly documented incident: an OpenClaw agent sent a
legal rebuttal email to an insurance company on behalf of its user — without the
user having explicitly approved that specific action.

OpenClaw's documented security posture is that hard enforcement is the operator's
responsibility. diplomat-gate is what that enforcement looks like in 10 lines of YAML.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
DEMO_DIR = Path(__file__).parent
CI_MODE = "--ci" in sys.argv

sys.path.insert(0, str(DEMO_DIR / "vendored"))

from email_send import MockEmailClient, agent_send_email  # noqa: E402

try:
    from diplomat_gate import Gate  # noqa: E402
except ImportError:
    sys.path.insert(0, str(REPO / "src"))
    from diplomat_gate import Gate  # noqa: E402


# ── Formatting helpers ────────────────────────────────────────────────────────


def _use_rich() -> bool:
    if CI_MODE:
        return False
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def print_header(text: str) -> None:
    if CI_MODE:
        print(f"\n{text}")
        return
    if _use_rich():
        from rich import print as rprint
        from rich.rule import Rule

        rprint(Rule(f"[bold]{text}[/bold]", style="blue"))
    else:
        width = 60
        print(f"\n{'─' * width}")
        print(f"  {text}")
        print(f"{'─' * width}")


def _fmt(text: str, color: str = "") -> str:
    if CI_MODE or not sys.stdout.isatty():
        return text
    codes = {"red": "\x1b[31m", "green": "\x1b[32m", "yellow": "\x1b[33m", "bold": "\x1b[1m"}
    return f"{codes.get(color, '')}{text}\x1b[0m"


def _pause() -> None:
    if not CI_MODE:
        input("  [press Enter to continue]")


# ── Scenarios ─────────────────────────────────────────────────────────────────


def scenario_1_unprotected() -> None:
    print_header("SCENARIO 1 — OpenClaw agent, no diplomat-gate")

    client = MockEmailClient()

    # The user received a claim rejection. The agent drafted a legal rebuttal.
    # The user saw the draft in their inbox but was too distressed to respond.
    # The agent, interpreting silence as implicit approval, sends it anyway
    # — because nothing in the framework stops it.
    agent_send_email(
        client,
        to="claims@lemonade.com",
        subject="Re: Claim #12345 — request for reconsideration",
        body=(
            "Dear Lemonade Insurance, pursuant to your rejection letter dated "
            "January 14, 2026, we formally contest this decision on the following "
            "legal grounds: [... long LLM-generated rebuttal with case citations ...]"
        ),
        acting_on_behalf_of="user",
    )

    print(f"  Emails sent without approval : {_fmt(str(len(client.sent)), 'red')}")
    print(f"  Recipient                    : {client.sent[0]['to']}")
    print(f"  {_fmt('🔥 Legal email sent to insurance company without user approval.', 'red')}")
    if not CI_MODE:
        _pause()


def scenario_2_protected() -> None:
    print_header("SCENARIO 2 — Same agent, behind diplomat-gate")

    client = MockEmailClient()
    # Use a temp audit DB so each run is self-contained
    audit_db = str(DEMO_DIR / "demo-audit.db")
    gate = Gate.from_yaml(str(DEMO_DIR / "policies.yaml"), audit_path=audit_db)

    call = {
        "action": "agent.send_email",
        "to": "claims@lemonade.com",
        "subject": "Re: Claim #12345 — request for reconsideration",
        "body": "[... legal rebuttal ...]",
        "acting_on_behalf_of": "user",
        "agent_id": "personal_agent_01",
    }
    verdict = gate.evaluate(call)

    print(f"  Verdict: {_fmt(verdict.decision.name, 'red' if verdict.blocked else 'yellow')}")
    for v in verdict.violations:
        print(f"    - {v.policy_id}: {v.message}")

    if verdict.allowed:
        agent_send_email(
            client, **{k: val for k, val in call.items() if k not in ("action", "agent_id")}
        )
    else:
        print(f"  {_fmt('🛡  Email blocked before reaching the SMTP server.', 'green')}")

    print(f"  Emails actually sent: {_fmt(str(len(client.sent)), 'green')}")

    # Show rate-limit (REVIEW) path: safe domain, first email passes, second is held
    print()
    safe_calls = [
        {
            "action": "agent.send_email",
            "to": "alice@example.com",
            "subject": "Hi Alice",
            "body": "Hey!",
            "agent_id": "personal_agent_01",
        },
        {
            "action": "agent.send_email",
            "to": "bob@example.com",
            "subject": "Hi Bob",
            "body": "Hey!",
            "agent_id": "personal_agent_01",
        },
    ]
    for sc in safe_calls:
        sv = gate.evaluate(sc)
        label = sv.decision.name
        color = "green" if sv.allowed else "yellow" if sv.decision.name == "REVIEW" else "red"
        print(f"  to: {sc['to']:30s}  Verdict: {_fmt(label, color)}", end="")
        if sv.violations:
            print(f"  ({sv.violations[0].policy_id})", end="")
        print()

    gate.close()
    if not CI_MODE:
        _pause()


def scenario_3_audit() -> None:
    print_header("SCENARIO 3 — Every verdict is hash-chained")

    audit_db = str(DEMO_DIR / "demo-audit.db")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "diplomat_gate.cli",
            "--no-color",
            "audit",
            "verify",
            "--db",
            audit_db,
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    output = (result.stdout or result.stderr or "").strip()

    print("  $ diplomat-gate audit verify")
    if output:
        for line in output.splitlines():
            print(f"  {line}")
        # Ensure "Chain valid" appears for CI marker even if CLI format changes
        if "valid" not in output.lower():
            from diplomat_gate.audit import verify_chain

            vr = verify_chain(audit_db)
            if vr.valid:
                print(f"  {_fmt('✓ Chain valid', 'green')} — {vr.records_checked} verdicts.")
    else:
        # Fallback: call verify_chain directly
        from diplomat_gate.audit import verify_chain

        vr = verify_chain(audit_db)
        if vr.valid:
            print(f"  {_fmt('✓ Chain valid', 'green')} ({vr.records_checked} record(s) checked)")
        else:
            print(f"  {_fmt('✗ Chain invalid', 'red')}: {vr.error}")


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Optional: --scenario N  runs only that scenario (1, 2, or 3)
    _scenario: int | None = None
    for _i, _arg in enumerate(sys.argv):
        if _arg == "--scenario" and _i + 1 < len(sys.argv):
            _scenario = int(sys.argv[_i + 1])
            break

    if _scenario is None or _scenario == 1:
        scenario_1_unprotected()
    if _scenario is None or _scenario == 2:
        scenario_2_protected()
    if _scenario is None or _scenario == 3:
        scenario_3_audit()
