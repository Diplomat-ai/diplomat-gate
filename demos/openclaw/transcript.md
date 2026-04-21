# Demo transcript — expected output

Run with: `python demos/openclaw/run.py --ci`

```
SCENARIO 1 — OpenClaw agent, no diplomat-gate
  Emails sent without approval : 1
  Recipient                    : claims@lemonade.com
  🔥 Legal email sent to insurance company without user approval.

SCENARIO 2 — Same agent, behind diplomat-gate
  Verdict: STOP
    - email.domain_blocklist: Domain 'lemonade.com' is on the blocklist
  🛡  Email blocked before reaching the SMTP server.
  Emails actually sent: 0

  to: alice@example.com               Verdict: CONTINUE
  to: bob@example.com                 Verdict: REVIEW  (email.rate_limit)

SCENARIO 3 — Every verdict is hash-chained
  $ diplomat-gate audit verify
  OK: chain valid (3 record(s) checked)
```

## CI marker expectations

`test_openclaw_demo_produces_markers` checks for the following strings in
stdout (in any order):

| Marker | Scenario | Confirmed |
|---|---|---|
| `"SCENARIO 1"` + `"without approval"` | 1 | ✓ |
| `"SCENARIO 2"` + `"STOP"` | 2 | ✓ |
| `"SCENARIO 3"` + `"valid"` | 3 | ✓ |
