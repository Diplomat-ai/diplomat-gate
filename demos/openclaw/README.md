# OpenClaw demo

This demo shows how **diplomat-gate** sits in front of an AI agent built with
the [OpenClaw](https://github.com/openclaw/openclaw) agentic framework and
silently blocks or queues sensitive actions before they reach any external
service.

## The incident it illustrates

A user noticed their AI assistant had sent an unsolicited email to their
insurance company's claims department — without ever asking for confirmation.
The agent had inferred the address from a document the user uploaded and
fired off the message autonomously.

Adding 10 lines of YAML was enough to prevent the same thing from happening
again.

## Policies used

| Policy | Effect | Why |
|---|---|---|
| `email.domain_blocklist` | STOP | Blocks `*@lemonade.com`, `*@*insurance*`, `*@*legal*`, `*@*lawyer*`. No send, no error, just a verdict. |
| `email.rate_limit` (max 2 / 1 h) | REVIEW | The third outbound email in an hour is held for human review. |

> **Note — spec vs implementation**: The original spec used `parameter_match`
> / `parameter_check` policy types that don't exist in the current
> diplomat-gate registry. The substitution above is semantically equivalent
> and uses only built-in policy types. See `policies.yaml` for the actual
> configuration.

## Files

```
demos/openclaw/
├── README.md              ← you are here
├── run.py                 ← entry point
├── policies.yaml          ← diplomat-gate policy file, ≤ 10 lines
├── transcript.md          ← expected word-for-word output
├── storyboard.md          ← 60-second video script
├── assets/
│   └── recording_script.sh   ← asciinema-reproducible demo
└── vendored/
    ├── README.md          ← provenance & substitution notes
    └── email_send.py      ← functional reproduction of OpenClaw email-send
```

## How to run

```bash
# One-shot (creates demo-audit.db in this directory)
python demos/openclaw/run.py

# CI mode — same output, suppresses colour codes
python demos/openclaw/run.py --ci

# Record with asciinema
bash demos/openclaw/assets/recording_script.sh
```

Requirements: `diplomat-gate` installed (the project root package is
enough — no extra dependencies).
