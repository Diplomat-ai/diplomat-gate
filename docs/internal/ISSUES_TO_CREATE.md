# Good-first-issues to create on GitHub

Create these 5 issues after pushing v0.3.0. Use the Feature Request template
for enhancements, Bug Report for issue 4.

---

## Issue 1 — Redis-backed rate limiter for the review queue

**Title**: `feat: Redis rate limiter backend for review queue`
**Labels**: `enhancement`, `good first issue`
**Domain**: Review queue backend

### Body

**Problem statement**

The current rate limiter (`StateStore` / in-memory dict) is process-local.
In a multi-worker deployment (gunicorn, Ray, multiple microservices sharing
one diplomat-gate config), every worker keeps its own counter, so the limit
`max_calls_per_minute: 10` effectively becomes `10 × n_workers`.

**Proposed solution**

Add an optional `RedisStateStore` backend in
`src/diplomat_gate/state.py` (behind a `[redis]` extra):

```python
# gate.yaml
state_backend: redis
redis_url: redis://localhost:6379/0
```

The store should use `INCR` + `EXPIRE` on a per-policy key with a 60-second
TTL. No Lua scripts required for the first iteration.

**Acceptance criteria**
- [ ] `RedisStateStore` implements the same interface as `StateStore`
- [ ] Activated via `state_backend: redis` in YAML or `Gate(state=RedisStateStore(...))`
- [ ] `redis` package in `[redis]` optional extra in `pyproject.toml`
- [ ] Unit tests use `fakeredis` (add to `[dev]` extras)
- [ ] `docs/adapters.md` section added

---

## Issue 2 — LLM-powered semantic policy base class

**Title**: `feat: SemanticPolicy base class for LLM-evaluated rules`
**Labels**: `enhancement`, `good first issue`
**Domain**: New policy (other domain)

### Body

**Problem statement**

diplomat-gate's built-in policies are syntactic (regex, glob, threshold).
Some use-cases need judgments that can't be expressed as rules: e.g. "is
this email body professional?" or "does this SQL query read only, or does
it modify data?". Today users have to wire in their own LLM call outside
the gate.

**Proposed solution**

Add `SemanticPolicy` to `src/diplomat_gate/policies/base.py`:

```python
class SemanticPolicy(Policy):
    """Policy that delegates evaluation to an LLM judge."""
    prompt_template: str   # {tool_call} placeholder
    model: str = "gpt-4o-mini"
    verdict_true: Decision = Decision.CONTINUE
    verdict_false: Decision = Decision.STOP
```

Lives in a new `[semantic]` optional extra. Must not be in the
default evaluation path.

**Acceptance criteria**
- [ ] Works with OpenAI and Anthropic (via existing adapters)
- [ ] `prompt_template` configurable via YAML
- [ ] Latency budget clearly documented (semantic policies are ~10-100×
      slower than syntactic ones)
- [ ] At least one example in `examples/`

---

## Issue 3 — Write-once S3 audit backend

**Title**: `feat: S3/object-store write-once audit backend`
**Labels**: `enhancement`, `good first issue`
**Domain**: Audit trail backend

### Body

**Problem statement**

The SQLite audit backend stores records locally. A local attacker with
write access to the DB file can run `rebuild_chain()` to produce a valid
chain on tampered records (this is documented in Limitations). For
production deployments where tamper-evidence is a hard requirement, records
should be shipped to a write-once object store (S3 with Object Lock, GCS
with retention policy, etc.).

**Proposed solution**

Add `S3AuditBackend` in `src/diplomat_gate/audit.py` (behind a `[s3]` extra):

```yaml
# gate.yaml
audit:
  backend: s3
  bucket: my-audit-logs
  prefix: diplomat-gate/
  region: us-east-1
```

Each record is a JSONL line uploaded as an individual object with a
content-addressed key (`sha256(record_json)`). Batch upload via
`multipart_upload` for high-throughput deployments.

**Acceptance criteria**
- [ ] `S3AuditBackend` implements `AuditBackend` protocol
- [ ] `boto3` in `[s3]` optional extra
- [ ] `moto` used for unit tests
- [ ] Performance impact documented (async upload recommended)

---

## Issue 4 — Fix Windows Unicode output in test suite

**Title**: `fix: Windows PYTHONUTF8 subprocess encoding in test_examples`
**Labels**: `bug`, `good first issue`
**Domain**: CLI / tooling

### Body

**Problem statement**

On Windows (default cp1252 console), example scripts that print emoji
(`✓`, `✗`, `→`) fail with `UnicodeEncodeError` when run as subprocess
in the test suite:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'
```

The `validate_release.py` script already sets `PYTHONUTF8=1` in the CI
environment, but `tests/test_examples.py` (and similar) run subprocess
without forcing UTF-8.

**Proposed fix**

In every `subprocess.run()` / `subprocess.Popen()` call inside the test
suite that runs example scripts:

```python
import os
subprocess.run(
    cmd,
    env={**os.environ, "PYTHONUTF8": "1"},
    ...
)
```

**Acceptance criteria**
- [ ] `pytest` passes on Windows without `PYTHONUTF8=1` set externally
- [ ] No change to example script source (fix is in test harness only)
- [ ] CI workflow updated if needed

---

## Issue 5 — SARIF export for audit trail

**Title**: `feat: SARIF export for audit trail (GitHub Code Scanning integration)`
**Labels**: `enhancement`, `good first issue`
**Domain**: CLI / tooling

### Body

**Problem statement**

Security teams using GitHub Advanced Security can ingest SARIF files into
Code Scanning. diplomat-gate audit records map naturally to SARIF results
(`STOP` verdicts → `error`, `REVIEW` → `warning`). Exporting the audit
trail as SARIF would let teams surface policy violations in the GitHub
Security tab alongside static analysis findings.

**Proposed solution**

Add a `diplomat-gate audit export --format sarif` subcommand that emits
a SARIF 2.1.0 JSON document:

```bash
diplomat-gate audit export --format sarif --since 2024-01-01 > results.sarif
```

Each `STOP` record becomes a SARIF `result` with:
- `ruleId`: the policy id (e.g. `payment.amount_limit`)
- `message.text`: the violation message
- `level`: `"error"` for STOP, `"warning"` for REVIEW

**Acceptance criteria**
- [ ] Output validates against SARIF 2.1.0 JSON schema
- [ ] `diplomat-gate audit export --format json` (plain JSONL) also added
- [ ] `--since` / `--until` ISO-8601 date filters supported
- [ ] No new mandatory dependencies (stdlib `json` only)
- [ ] Documented in `docs/audit-trail.md`
