# Conversion checklist — human test protocol

**When to run**: before any public post (HN, Reddit, LinkedIn, Twitter/X,
PyPI announcement). One human tester, ~20 minutes cold.

**Pass bar**: every item in sections 1–4 must be green. Section 5 is
advisory.

---

## Section 1 — Cold install (5 min)

The tester has never used diplomat-gate before. No context from the author.

- [ ] **1.1** Open the GitHub repo page in a browser. Read the README above
  the fold (no scrolling). Can you explain in one sentence what the project
  does?

- [ ] **1.2** Copy the install command from the README. Run it in a fresh
  virtual environment. Does it complete without error?

  ```bash
  python -m venv /tmp/dg-test && source /tmp/dg-test/bin/activate
  pip install diplomat-gate
  diplomat-gate --help
  ```

  Expected: `diplomat-gate --help` exits 0 and shows top-level commands.

- [ ] **1.3** Run the demo exactly as shown in the README:

  ```bash
  pip install "diplomat-gate[yaml]"
  git clone https://github.com/Diplomat-ai/diplomat-gate /tmp/dg-repo
  cd /tmp/dg-repo
  python demos/openclaw/run.py
  ```

  Expected: all 3 scenarios complete, no Python traceback.

- [ ] **1.4** In scenario 2, does the output show `Verdict: STOP` and
  `Emails actually sent: 0` for the insurance email?

- [ ] **1.5** In scenario 3, does the output show `OK: chain valid`?

---

## Section 2 — README comprehension (5 min)

- [ ] **2.1** After reading "The problem" section: can the tester name at
  least two categories of unprotected tool calls from the scanner example?

- [ ] **2.2** Policy table in "Email policies": can the tester identify which
  policy blocks a specific domain, and which one rate-limits sends?
  (`email.domain_blocklist` / `email.rate_limit`)

- [ ] **2.3** The "Works with every framework" table: can the tester find
  the integration method for their own agent framework (or the closest one)?

- [ ] **2.4** After the `60-second setup` code block: can the tester modify
  the YAML to add a second blocked domain without looking at docs?

- [ ] **2.5** Is there any section where the tester says "I don't understand
  what this is for"? Record verbatim.

---

## Section 3 — First gate integration (10 min)

The tester writes a minimal script from scratch (no copy-paste from README).

- [ ] **3.1** Create `gate.yaml` with one policy (their choice). Does
  `Gate.from_yaml("gate.yaml")` load without error?

- [ ] **3.2** Call `gate.evaluate({"action": "send_email", "to": "test@example.com"})`.
  Does the verdict have a `.decision` attribute?

- [ ] **3.3** Add `audit: enabled: true` to the YAML. Re-run. Does
  `diplomat-gate audit verify --db ./diplomat-audit.db` return exit code 0?

- [ ] **3.4** Intentionally trigger a STOP verdict. Confirm `.blocked` is
  `True` on the returned verdict.

- [ ] **3.5** At no point did the tester need to read source code or open an
  issue to complete the above?

---

## Section 4 — Failure modes (2 min)

- [ ] **4.1** Missing YAML key: `Gate.from_yaml` raises a clear exception
  (not a raw `KeyError`) when a required policy field is absent.

- [ ] **4.2** Invalid `on_fail` value: the loader raises a descriptive error
  (not a silent fallback).

- [ ] **4.3** `diplomat-gate audit verify --db /nonexistent.db` exits non-zero
  and prints a human-readable error.

---

## Section 5 — Advisory (no pass/fail)

Record observations only. Use to improve UX in a future release.

- [ ] **5.1** What was the first thing the tester tried that did NOT work as
  expected? (Note verbatim.)

- [ ] **5.2** Did the tester scroll past the framework table without reading
  it? (Eye-tracking proxy: ask after the session.)

- [ ] **5.3** After completing section 3, does the tester say they would use
  this in a project? Why / why not?

- [ ] **5.4** Benchmark numbers in the README: did the tester notice them?
  Did the numbers affect their perception of the project?

- [ ] **5.5** Time to first working `gate.evaluate()` call (from cold repo
  clone). Target: under 5 minutes. Actual: ___

---

## Scoring

| Section | Items | Green | Result |
|---|---|---|---|
| 1 — Cold install | 5 | ≥ 5 | |
| 2 — README comprehension | 5 | ≥ 4 | |
| 3 — First integration | 5 | ≥ 4 | |
| 4 — Failure modes | 3 | ≥ 3 | |

**Overall**: post if sections 1–4 all pass. Defer if any section fails.

---

## How to run a session

1. Find a tester who writes Python but has not seen diplomat-gate before.
2. Share only the GitHub URL. No verbal explanation.
3. Sit quietly. Do not help. Take notes on hesitations and questions.
4. Use the checklist above in order.
5. At the end, ask: "What would stop you from using this in production?"
6. File a GitHub issue for each item that blocked the tester.
