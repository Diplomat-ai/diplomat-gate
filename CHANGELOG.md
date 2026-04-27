# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- `diplomat-gate validate <gate.yaml>` CLI subcommand — validates a gate.yaml
  file without instantiating a Gate or executing any policies. Reports errors
  (unknown policy ids, type mismatches, bad severity/on_fail values) and
  warnings (unknown fields with difflib suggestions, empty domains, default
  critical fields). Exit 0 if valid, 1 if errors, 2 if I/O error.
- `src/diplomat_gate/validation.py` — pure validation module with stable JSON
  output schema (`format_version: "1"`). Types: `Issue`, `ValidationReport`.
  Public API: `validate_config()`, `report_to_dict()`, `format_report_text()`.
- `iter_registered_policies()` in `diplomat_gate.policies.loader` — returns a
  copy of the internal policy registry for read-only inspection.
- `tests/test_validation.py` — unit tests for the validation module.
- `tests/test_cli_validate.py` — integration tests (`@pytest.mark.integration`)
  for the `diplomat-gate validate` CLI command.
- `tests/fixtures/validation/` — 13 YAML fixtures covering valid configs,
  error cases, and warning cases.
- `examples/09_validate_in_ci.py` — demonstrates programmatic use of
  `validate_config()` in a CI script.
- `docs/cli.md` — full CLI reference for `validate`, `audit`, and `review`.
- `scripts/validate_release.py` updated: added steps 10bis (validate --help)
  and 10ter (validate gate.yaml.example); renumbered all steps to X/13.

## [0.3.0] — 2026-04-22

Public launch release. Everything needed for a credible open-source project:
HN-ready README, visual assets, honest performance claims, community health
files, and a full release validation pipeline.

### Added

- `docs/images/before-after-comparison.svg` — hero "before/after" diagram
  showing the agent call path with and without diplomat-gate.
- `docs/images/multi-framework-compatibility.svg` — framework convergence
  diagram (OpenAI, Anthropic, LangChain all evaluated through one Gate).
- `docs/images/generate_before_after.py`, `generate_multi_framework.py` —
  reproducible SVG generators; `docs/images/README.md` explains regeneration.
- Two Mermaid diagrams in `README.md`: enforcement flow (how the Gate
  evaluates a tool call end-to-end) and audit hash-chain visualization.
- `scripts/validate_release.py` — 11-step release gate (ruff, pytest,
  benchmarks, build, twine, smoke install, CLI, demo). Exits 0 on full pass.
- `tests/test_release_readiness.py` — release readiness test suite.
- `.github/workflows/smoke.yml` — 12-combination OS × Python matrix.
- `.github/workflows/ci.yml` — lint + test matrix with 80% coverage gate.
- `.github/ISSUE_TEMPLATE/bug_report.yml` — structured bug report form with
  component dropdown, version fields, minimal reproduction placeholder.
- `.github/ISSUE_TEMPLATE/feature_request.yml` — feature request form with
  domain dropdown, YAML config placeholder, "willing to PR?" field.
- `.github/ISSUE_TEMPLATE/config.yml` — disables blank issues, links to
  security advisory flow, docs, and discussions.
- `.github/PULL_REQUEST_TEMPLATE.md` — PR checklist (pytest, ruff, examples,
  benchmarks, CHANGELOG, security considerations).
- `.github/ISSUES_TO_CREATE.md` — 5 good-first-issue drafts for post-launch:
  Redis rate limiter, SemanticPolicy, S3 audit backend, Windows PYTHONUTF8
  test fix, SARIF export.
- `demos/openclaw/` — 60-second self-contained demo reproducing the
  OpenClaw/Lemonade Insurance incident pattern. No API key, no Docker.
- `docs/conversion-checklist.md` — human conversion test protocol.

### Changed

- README: Limitations section expanded with explicit "diplomat-gate does well",
  "diplomat-gate does NOT do", and "when NOT to use" subsections covering
  syntactic-only evaluation, `rebuild_chain` threat model, and rate-limit
  concurrency in multi-process deployments.
- README: Performance table updated with values measured on current hardware
  (`simple_allow` mean ~18 µs p95 ~31 µs; `multi_policy_5` mean ~496 µs
  p95 ~958 µs; `with_audit_sqlite` mean ~558 µs p99 ~1925 µs with fsync
  long-tail documented).
- README: inline performance claim corrected to `~20 µs` / `~500 µs` to
  match measured benchmarks.
- `CONTRIBUTING.md` rewritten: before-contributing gate (issue-first workflow),
  full venv setup instructions, ruff + validate_release steps, coding-style
  constraints (no new deps, type hints, determinism), policy-writing checklist.
- `SECURITY.md` rewritten: supported-versions table, expanded scope (incorrect
  verdict, info disclosure), documented out-of-scope items matching README
  Limitations, responsible-disclosure terms.
- `_version.py` / `pyproject.toml` bumped to 0.3.0.

### Fixed

- Import sorting (`ruff I001`) and formatting in `docs/images/` generator
  scripts.
- Performance table benchmark drift (150–677% vs. measured values); table
  now reflects real hardware timings with an fsync-induced p99 note.


## [0.2.0] — 2026-04-21

> **Note**: this version was developed but never released publicly on PyPI or GitHub Releases. All 0.2.0 features are included in 0.3.0.

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
