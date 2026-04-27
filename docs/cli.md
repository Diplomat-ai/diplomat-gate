# diplomat-gate CLI reference

## Global flags

```
diplomat-gate [--no-color] <command> ...
```

| Flag | Description |
|------|-------------|
| `--no-color` | Disable ANSI colour codes in output. Must appear **before** the subcommand. |

---

## `validate` — validate a gate.yaml file

```
diplomat-gate [--no-color] validate <config_path> [--json] [--output FILE] [--quiet]
```

Inspect a `gate.yaml` file without instantiating a Gate or executing any policies.
Returns a structured report listing errors and warnings.

### Arguments

| Argument / Flag | Description |
|-----------------|-------------|
| `config_path` | Path to the `gate.yaml` file to validate. |
| `--json` | Emit machine-readable JSON on stdout instead of human text. |
| `--output FILE` | Write the JSON report to `FILE`. A short summary still goes to stdout unless `--quiet` is set. |
| `--quiet` | Suppress all stdout output. Exit code is preserved. |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | No errors (warnings allowed). |
| `1` | One or more validation errors found. |
| `2` | I/O error (file not found, not readable), YAML parse error, or PyYAML not installed. |

### Examples

```bash
# Basic validation — human-readable output
diplomat-gate validate gate.yaml
# OK: 8 policies loaded, 0 errors, 0 warnings

# With warnings
diplomat-gate validate config-with-typo.yaml
# OK with warnings: 2 policies loaded, 0 errors, 1 warning(s)
#   warning  payment[0].max_amout  unknown_field  Unknown field 'max_amout'. Did you mean 'max_amount'?

# JSON output
diplomat-gate validate gate.yaml --json
# {"ok": true, "format_version": "1", "config_path": "gate.yaml", ...}

# CI integration — write report file, suppress stdout, check exit code
diplomat-gate validate gate.yaml --output report.json --quiet
echo $?  # 0 if valid, 1 if errors, 2 if I/O error

# No colour (e.g. in log files)
diplomat-gate --no-color validate gate.yaml
```

### JSON output schema

```json
{
  "ok": true,
  "format_version": "1",
  "config_path": "gate.yaml",
  "policies_loaded": [
    "email.business_hours",
    "email.content_scan",
    "email.domain_blocklist",
    "email.rate_limit",
    "payment.amount_limit",
    "payment.duplicate_detection",
    "payment.recipient_blocklist",
    "payment.velocity"
  ],
  "errors": [],
  "warnings": []
}
```

Key order is stable across runs (diffable in CI artifacts). `policies_loaded` is sorted
alphabetically. `errors` and `warnings` are sorted by `(path, code)`.

Each issue has the following fields:

```json
{
  "path": "payment[0].max_amount",
  "code": "type_mismatch",
  "message": "Field 'max_amount' expected float, got str ('ten thousand')",
  "severity": "error"
}
```

### Validation rules

**Errors** (exit 1):

| Code | Condition |
|------|-----------|
| `missing_id` | Policy entry has no `id` field, or `id` is not a string. |
| `unknown_policy` | `id` references a policy not registered in the built-in registry. |
| `bad_severity` | `severity` is not one of `critical`, `high`, `medium`, `low`. |
| `bad_on_fail` | `on_fail` is not one of `STOP`, `REVIEW`. |
| `bad_enabled` | `enabled` is not a bool. |
| `type_mismatch` | A policy-specific field has an incompatible type. |
| `audit_bad_type` | `audit.enabled` is not a bool, or `audit.path` is not a string. |
| `review_queue_bad_type` | `review_queue.enabled` is not a bool, or `review_queue.path` is not a string. |
| `bad_top_level_type` | A domain section (`payment`, `email`, `policies`) is not a list. |

**Warnings** (exit 0, but reported):

| Code | Condition |
|------|-----------|
| `unknown_field` | Unrecognised field on a policy entry (typo). Includes a `Did you mean?` suggestion via difflib. |
| `unknown_audit_field` | Unrecognised field in the `audit:` section. |
| `unknown_review_queue_field` | Unrecognised field in the `review_queue:` section. |
| `empty_domain` | `payment: []` or `email: []` — empty list is legal but likely unintentional. |
| `no_policies` | No policies loaded at all. |
| `default_critical_field` | A critical policy field (`max_amount`, `max_daily`, `blocked`) is not set and will use its default value. |

---

## `audit` — audit log operations

### `audit verify`

```
diplomat-gate audit verify --db <path>
```

Verify the SHA-256 hash chain of the audit log database.

| Exit code | Meaning |
|-----------|---------|
| `0` | Chain is valid. |
| `1` | Chain is invalid (tamper detected). |
| `2` | I/O or database error. |

### `audit rebuild-chain`

```
diplomat-gate audit rebuild-chain --db <path>
```

Recompute the sequence, previous hash, and record hash for every row.
Use with caution — this overwrites existing hashes.

---

## `review` — review queue operations

### `review list`

```
diplomat-gate review list --db <path> [--status pending|approved|rejected|expired|all] [--limit N] [--json]
```

List items in the review queue. Default status filter: `pending`.

### `review show`

```
diplomat-gate review show --db <path> --id <item_id>
```

Display full details of a single review item.

### `review approve` / `review reject`

```
diplomat-gate review approve --db <path> --id <item_id> --reviewer <name> [--note ...]
diplomat-gate review reject  --db <path> --id <item_id> --reviewer <name> [--note ...]
```

Approve or reject a pending review item and record the decision.
