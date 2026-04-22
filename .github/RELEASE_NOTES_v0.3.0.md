# Release Notes — diplomat-gate v0.3.0

**Release date**: 2026-04-22  
**Install**: `pip install diplomat-gate==0.3.0`  
**Tag**: `v0.3.0`  
**Branch**: `v0.3.0`

---

## What is diplomat-gate?

diplomat-gate is an enforcement layer for AI agent tool calls. Before an
agent can execute `send_email`, `initiate_payment`, `write_file`, or any
other tool, the Gate evaluates the call against a policy set and returns
one of three verdicts:

- `CONTINUE` — allow the action
- `REVIEW` — hold for human approval
- `STOP` — block the action, return a violation message to the agent

No LLM in the enforcement path. No mandatory external dependencies.
~20 µs per evaluation for a single policy. Works with OpenAI, Anthropic,
and LangChain out of the box.

---

## What's new in 0.3.0

### Honest performance numbers

The README Performance table has been updated with values actually measured
on current hardware:

| Scenario | mean | p95 | ops/s |
|---|---|---|---|
| `simple_allow` (1 policy) | ~18 µs | ~31 µs | 54,000 |
| `simple_block` (1 policy) | ~19 µs | ~33 µs | 52,000 |
| `multi_policy_5` (5 policies) | ~496 µs | ~958 µs | 2,000 |
| `with_audit_sqlite` | ~558 µs | ~625 µs | 1,800 |

The `with_audit_sqlite` p99 reaches ~1925 µs due to fsync-induced long tails.
Reproducible: `python benchmarks/run.py`.

### Expanded Limitations section

The README now includes an explicit "when NOT to use" block documenting:

- diplomat-gate is syntactic — it cannot catch semantic policy evasion
  ("send to ally-of-blocklist.com instead of blocklist.com")
- `rebuild_chain` is intentional — the audit trail is tamper-*detectable*
  locally, not tamper-*resistant* against a local attacker with DB write
  access; ship to S3 Object Lock / GCS Retention for hard guarantees
- Rate limiting is process-local — in multi-worker deployments, use the
  Redis backend (in roadmap, see Issue 1)

### Visual assets

Two SVGs now live in `docs/images/`:

- `before-after-comparison.svg` — agent tool-call path before and after
  diplomat-gate is inserted
- `multi-framework-compatibility.svg` — OpenAI / Anthropic / LangChain
  converging through one Gate

Both are embedded in the README. Regenerate with the included Python scripts.

### Community infrastructure

Ready for open-source contributors:

- **CONTRIBUTING.md**: issue-first workflow, full venv setup, coding
  constraints (no new deps, type hints, determinism), 5-step policy checklist
- **SECURITY.md**: supported versions, scope, out-of-scope, responsible
  disclosure terms
- **GitHub issue templates**: structured bug report (with component dropdown),
  feature request (with YAML config placeholder), config.yml (disables blank
  issues, links to security advisories)
- **PR template**: testing and contribution checklist

### 5 good-first-issues ready to post

See `.github/ISSUES_TO_CREATE.md` for ready-to-post drafts:

1. Redis-backed rate limiter (multi-worker correctness)
2. SemanticPolicy base class (optional LLM judge)
3. S3 write-once audit backend (strong tamper-evidence)
4. Fix Windows PYTHONUTF8 in test subprocess calls
5. SARIF export for audit trail (GitHub Code Scanning)

---

## Migration

No API changes from 0.2.x. Audit databases created with 0.2.x are
compatible. No migration needed.

---

## Full validation

All 11 checks pass on `validate_release.py`:

```
[1/11]  ruff check .                  PASS
[2/11]  ruff format --check .         PASS
[3/11]  pytest (unit + integration)   PASS  (146 tests)
[4/11]  benchmarks/run.py             PASS
[5/11]  python -m build               PASS
[6/11]  twine check dist/*            PASS
[7/11]  smoke install (venv)          PASS
[8/11]  smoke import                  PASS
[9/11]  smoke CLI                     PASS
[10/11] smoke examples                PASS
[11/11] smoke demo                    PASS
```

---

## Acknowledgments

diplomat-gate is built and maintained by [Josselin Guarnelli](https://diplomat.run).

If you use it, a GitHub star is appreciated. If you find a security issue,
email josselin@diplomat.run — do not open a public issue.
