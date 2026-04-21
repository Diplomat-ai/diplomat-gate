# Storyboard — "10 lines of YAML" (60 s)

Target: 60 seconds.  Format: terminal screencast (asciinema → GIF / MP4).

---

## Shot 1 — The problem  [0 – 12 s]

**Screen**: plain terminal, white on black.

```
$ python demos/openclaw/run.py --ci
```

Only Scenario 1 output is visible — pause after each line for readability:

```
SCENARIO 1 — OpenClaw agent, no diplomat-gate
  Emails sent without approval : 1
  Recipient                    : claims@lemonade.com
  🔥 Legal email sent to insurance company without user approval.
```

**Narration (optional overlay text)**: "Your AI agent just emailed your
insurance company. You didn't ask it to."

**Wait**: 3 s on the fire emoji line.

---

## Shot 2 — The fix  [12 – 22 s]

**Screen**: editor pane (or `cat`) showing `policies.yaml`, typed or revealed
line by line.

```yaml
policies:
  - type: email.domain_blocklist
    blocked: ["*@lemonade.com", "*@*insurance*"]
    on_fail: STOP
  - type: email.rate_limit
    max: 2
    window: 1h
    on_fail: REVIEW
audit:
  enabled: true
```

**Overlay text**: "10 lines of YAML."

**Wait**: 2 s on the final line.

---

## Shot 3 — diplomat-gate blocks it  [22 – 40 s]

**Screen**: same terminal session, Scenario 2 output scrolling in.

```
SCENARIO 2 — Same agent, behind diplomat-gate
  Verdict: STOP
    - email.domain_blocklist: Domain 'lemonade.com' is on the blocklist
  🛡  Email blocked before reaching the SMTP server.
  Emails actually sent: 0

  to: alice@example.com               Verdict: CONTINUE
  to: bob@example.com                 Verdict: REVIEW  (email.rate_limit)
```

**Pause points**:
- 1 s after `Verdict: STOP`
- 1 s after `🛡  Email blocked`
- 1 s after the CONTINUE / REVIEW pair

---

## Shot 4 — Tamper-evident audit  [40 – 52 s]

**Screen**: Scenario 3 output.

```
SCENARIO 3 — Every verdict is hash-chained
  $ diplomat-gate audit verify
  OK: chain valid (3 record(s) checked)
```

**Overlay text**: "Every decision is hash-chained and verifiable."

**Wait**: 3 s on the `OK: chain valid` line.

---

## Shot 5 — Call to action  [52 – 60 s]

**Screen**: fade to black, two lines appear.

```
pip install diplomat-gate

github.com/Diplomat-ai/diplomat-gate
```

**Wait**: 8 s (hold for the viewer to read).

---

## Timing summary

| Shot | Start | End | Duration |
|---|---|---|---|
| 1 — The problem | 0 s | 12 s | 12 s |
| 2 — The fix (YAML) | 12 s | 22 s | 10 s |
| 3 — Gate blocks | 22 s | 40 s | 18 s |
| 4 — Audit chain | 40 s | 52 s | 12 s |
| 5 — CTA | 52 s | 60 s | 8 s |

---

## Production notes

- Font: JetBrains Mono, 14 pt, white on `#0d1117` (GitHub dark).
- Terminal width: 88 columns (fits the longest output line without wrapping).
- Emoji rendering: verify `🔥` and `🛡` display correctly before recording.
- GIF frame rate: 10 fps for upload to GitHub README.
- MP4 variant: 30 fps, H.264, for HN / LinkedIn embed.
