# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] — 2026-04-21

Demo sprint: OpenClaw reproducible demo, rewritten HN-optimized README,
multi-framework gallery, human conversion test protocol, and release
validation pipeline.

### Added

- `demos/openclaw/` — 60-second self-contained demo reproducing the
  publicly documented OpenClaw/Lemonade Insurance incident pattern.
  `python demos/openclaw/run.py` — no API key, no Docker, no setup.
- `scripts/validate_release.py` — 11-step release gate (ruff, pytest,
  benchmarks, build, twine, smoke install, CLI, demo).
- `tests/test_release_readiness.py` — release readiness test suite.
- `.github/workflows/smoke.yml` — 12-combination OS × Python matrix.
- `docs/conversion-checklist.md` — human conversion test protocol.

### Changed

- README rewritten for HN audience: demo above the fold, "The problem"
  with aggregate scanner data, multi-framework compatibility table.
- `_version.py` / `pyproject.toml` bumped to 0.3.0.

## [0.2.0] — 2026-04-21

Major hardening release. Core API is backward compatible with 0.1.x;
audit log databases are auto-migrated on first open (a `UserWarning` is
emitted). New optional features (review queue, adapters, CLI) are opt-in.

### Highlights

- **Hash-chained audit trail** with `diplomat-gate audit verify` /
  `audit rebuild-chain` and an explicit threat model.
- **Review queue** (separate SQLite DB) with full lifecycle, TTL,
  redaction, and four CLI subcommands.
- **Adapters** for OpenAI, Anthropic, LangChain (duck-typed, no SDK
  imports at module load).
- **CLI** entry point `diplomat-gate` with `audit` and `review`
  subcommand groups.
- **Sensitive field redaction by default** in audit and review
  storage (`recipient`, `to`, `email`, `domain`, `amount`,
  `card_last4`, `phone` — see `models.SENSITIVE_FIELDS`).
- **Eight runnable examples**, **CI matrix** (Python 3.10–3.13 ×
  Linux / Windows / macOS) with 80% coverage gate, **microbenchmarks**.
- Full doc set: [`docs/quickstart.md`](docs/quickstart.md),
  [`docs/audit-trail.md`](docs/audit-trail.md),
  [`docs/review-queue.md`](docs/review-queue.md),
  [`docs/adapters.md`](docs/adapters.md),
  [`docs/writing-policies.md`](docs/writing-policies.md).

### Added — engine and storage

- `StateStore.record_value` / `StateStore.sum_values`: thread-safe
  windowed numeric accumulator backed by `(timestamp, value)` tuples.
- `models.SENSITIVE_FIELDS` constant (mutable at runtime). Each
  serialized violation now carries a `context` dict with the subset of
  `tool_call.params` whose keys are in `SENSITIVE_FIELDS`.
- `AuditLog(redact_violations=True)` (default): SHA-256-truncated
  hashing of sensitive `context` values before SQLite insertion.
- `audit.GENESIS_HASH = "0" * 64`,
  `audit.compute_record_hash(record, previous_hash)` (pure function,
  canonical JSON, deterministic),
  `audit.verify_chain(db_path) -> ChainVerificationResult` (read-only),
  `audit.rebuild_chain(db_path) -> int`.
- Audit log writes run inside `BEGIN IMMEDIATE` with retry on
  `SQLITE_BUSY` (5 attempts, exponential backoff). WAL +
  `synchronous=NORMAL` + autocommit.

### Added — review queue

- `diplomat_gate.review` module with `ReviewQueue`, `ReviewItem`,
  `ReviewQueueError` (publicly exported from `diplomat_gate`).
- `Gate(review_queue_path=...)` and YAML/dict configuration block
  `review_queue: {enabled, path}`. When configured, every `REVIEW`
  verdict is auto-enqueued; `Gate.close()` also closes the queue.
- Lifecycle `pending` → `approved` / `rejected` / `expired` enforced
  inside `BEGIN IMMEDIATE`; double decisions raise `ReviewQueueError`.
- Optional TTL: `ReviewQueue(ttl_seconds=...)` and per-call
  `enqueue(..., ttl_seconds=)`. `expire_due()` flips overdue items.
- Redaction on by default for both persisted `params` and per-violation
  `context`; opt out with `ReviewQueue(redact_params=False)`.

### Added — adapters

- `diplomat_gate.adapters` package, all duck-typed:
  - `adapters.base.GatedCall`, `dispatch()`, `partition()`.
  - `adapters.openai`: `to_tool_call()`, `gate_tool_calls()`,
    `filter_allowed()`. Tolerates malformed JSON `function.arguments`.
  - `adapters.anthropic`: `to_tool_call()`,
    `gate_tool_use_blocks()`, `filter_allowed()`,
    `is_tool_use_block()`. Non-`tool_use` content blocks are skipped.
  - `adapters.langchain`: `GatedTool` + `gated_tool()` /
    `gated_callable()`. Configurable `on_block` / `on_review`
    (`"raise"` or `"return"`). Falls back to `.run()` /
    `__call__` if `.invoke()` is missing.
- New extras: `[openai]`, `[anthropic]`, `[langchain]`. The `[all]`
  extra now bundles them with `[yaml]` and `[rich]`.

### Added — CLI

- `[project.scripts] diplomat-gate = "diplomat_gate.cli:main"`.
- Global flag `--no-color`; ANSI auto-detected via `isatty()`.
- Subcommands:
  - `audit verify --db <path>`
  - `audit rebuild-chain --db <path>`
  - `review list --db <path> [--status pending|approved|rejected|expired|all] [--limit N] [--json]`
  - `review show --db <path> --id <item_id>`
  - `review approve --db <path> --id <item_id> --reviewer <name> [--note ...]`
  - `review reject --db <path> --id <item_id> --reviewer <name> [--note ...]`
- Exit codes: `0` success, `1` chain invalid / item not found /
  transition refused, `2` usage or IO error.

### Added — examples, benchmarks, CI

- Eight runnable examples under `examples/` (`01_basic_gate.py` →
  `08_langchain_adapter.py`) plus `examples/configs/gate.yaml` and
  `examples/README.md`. All resolve paths via `Path(__file__)` and
  run identically from the repo root or from `examples/`.
- `benchmarks/run.py` + `benchmarks/README.md` — microbench harness
  reporting mean / median / p95 / p99 / ops/s for `simple_allow`,
  `simple_block`, `multi_policy_5`, `with_audit_sqlite`.
- `Makefile` with `install`, `test`, `cov`, `lint`, `format`,
  `bench`, `clean`.
- `.github/workflows/ci.yml`: lint (`ruff check` + `ruff format
  --check`), test matrix (3.10 / 3.11 / 3.12 / 3.13 × Linux / Windows /
  macOS) with `--cov-fail-under=80`, build (`python -m build` +
  `twine check dist/*`).
- `[tool.coverage.run]` branch coverage on; `[tool.coverage.report]`
  excludes `pragma: no cover`, `if __name__ == "__main__":`,
  `if TYPE_CHECKING:`, `raise NotImplementedError`.
- Test count: 64 → 146 (+82). Coverage: ~87% branch on this revision.

### Changed

- `DailyLimitPolicy.evaluate` rewritten to use
  `state.record_value` / `state.sum_values` instead of recording one
  event per integer unit. Fixes incorrect behavior on floats and large
  amounts.
- `CONTRIBUTING.md` rewritten against the real API (`Policy`,
  `PolicyResult`, `evaluate(tool_call, state)`).
- Audit-log SQLite connection now uses `isolation_level=None` and
  `synchronous=NORMAL`.
- Repository auto-formatted with `ruff format` (one-shot, no semantic
  changes); CI now enforces `ruff format --check`.
- `README.md` rewritten for 0.2.0 with the "Runtime action firewall for
  AI agents" positioning, a "What's new" section, and links to the
  five doc pages and eight examples.
- Project classifier moved from `Development Status :: 3 - Alpha` to
  `Development Status :: 4 - Beta`.

### Removed

- Pre-0.2.0 `examples/email_agent.py`, `examples/stripe_agent.py`,
  `examples/gate.yaml` (broken when launched from the repo root).
  `gate.yaml.example` at the repo root remains the canonical reference.

### Migration from 0.1.x

- **Audit databases**: opening a 0.1.x DB with the 0.2.0 `AuditLog`
  triggers an automatic schema migration (`ALTER TABLE ADD COLUMN`)
  and emits a `UserWarning`. Run `diplomat-gate audit rebuild-chain
  --db <path>` once afterwards to populate the new `sequence`,
  `previous_hash`, and `record_hash` columns. See
  [`docs/audit-trail.md`](docs/audit-trail.md#migration-from-01x).
- **Review queue**: opt-in. Set `review_queue: {enabled: true}` in
  YAML or pass `Gate(review_queue_path=...)` to start using it.
- **Adapters**: opt-in. Existing direct `Gate.evaluate(dict)`
  call sites are unaffected.
- **CLI**: new entry point. After `pip install diplomat-gate`, the
  `diplomat-gate` command is on `$PATH`.



## [0.1.0] - 2024-04-09

### Added
- Initial release
- Payment policies: `payment.amount_limit`, `payment.velocity`, `payment.daily_limit`, `payment.duplicate_detection`, `payment.recipient_blocklist`
- Email policies: `email.domain_blocklist`, `email.rate_limit`, `email.business_hours`, `email.content_scan`
- YAML policy loader
- SQLite audit trail
- `@gate()` decorator
- Three-verdict system: CONTINUE / REVIEW / STOP
