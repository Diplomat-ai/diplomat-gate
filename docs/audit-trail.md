# Audit trail — hash-chain integrity

The diplomat-gate audit log is an **append-only, hash-chained SQLite
table**. Every verdict is sealed by a SHA-256 record hash that
incorporates the previous record's hash, so any tampering with a
historical row breaks the chain and is detected by the verifier.

## Schema

Single table `verdicts`:

| column                | type    | notes                                       |
| --------------------- | ------- | ------------------------------------------- |
| `verdict_id`          | TEXT PK | UUIDv4                                       |
| `sequence`            | INTEGER | strictly increasing, starts at 1            |
| `timestamp`           | TEXT    | ISO-8601 UTC                                |
| `agent_id`            | TEXT    | optional caller identifier                  |
| `action`              | TEXT    | tool-call action                            |
| `params_hash`         | TEXT    | SHA-256 of canonical tool-call params       |
| `decision`            | TEXT    | `CONTINUE` / `REVIEW` / `STOP`              |
| `policies_evaluated`  | INTEGER |                                              |
| `policies_failed`     | INTEGER |                                              |
| `violations`          | TEXT    | JSON; sensitive fields hashed by default    |
| `latency_ms`          | REAL    |                                              |
| `previous_hash`       | TEXT    | hex SHA-256 of the previous row, or genesis |
| `record_hash`         | TEXT    | hex SHA-256 of this row's canonical payload |
| `created_at`          | TEXT    | SQLite-side default `datetime('now')`       |

The very first record uses the genesis sentinel
`previous_hash = "0" * 64`.

## Hash computation

`record_hash` is computed by `diplomat_gate.audit.compute_record_hash`.
It is a pure function of the row plus `previous_hash`, defined as:

```python
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
record_hash = sha256(canonical.encode("utf-8")).hexdigest()
```

where `payload` includes, in this order:

```
verdict_id, sequence, timestamp, agent_id, action, params_hash,
decision, policies_evaluated, policies_failed, violations,
latency_ms, previous_hash
```

`violations` is the **same JSON string** that is persisted in the
`violations` column (post-redaction), so the hash matches regardless of
the redaction setting in use at write time.

## Verifying the chain

Library:

```python
from diplomat_gate.audit import verify_chain

result = verify_chain("./diplomat-audit.db")
print(result.valid, result.records_checked, result.first_invalid_sequence)
```

CLI:

```
$ diplomat-gate audit verify --db ./diplomat-audit.db
OK: chain valid (12 record(s) checked)
$ echo $?
0
```

Exit codes:

| code | meaning                                          |
| ---- | ------------------------------------------------ |
| 0    | chain is valid                                   |
| 1    | chain is invalid (tampering or corruption)       |
| 2    | usage error or I/O error opening the database    |

`verify_chain` is **read-only**: it never modifies the database file,
even when the chain is broken.

## Migrating from the legacy 0.1.x schema

Opening an `AuditLog` against a database produced by 0.1.x triggers an
in-place migration that adds the `sequence`, `previous_hash`, and
`record_hash` columns with safe defaults (`0` and `''`). A
`UserWarning` is emitted: existing rows are now stored but **not yet
chained**, and `verify_chain` will report them as invalid.

Run `rebuild-chain` once to renumber and re-hash all historical rows in
`(timestamp, rowid)` order:

```
$ diplomat-gate audit rebuild-chain --db ./diplomat-audit.db
rebuilt chain: 137 record(s) rewritten
$ diplomat-gate audit verify --db ./diplomat-audit.db
OK: chain valid (137 record(s) checked)
```

After `rebuild-chain`, subsequent `record()` calls extend the chain
normally, starting at the next `sequence` value.

## Threat model

The chain protects against **tampering with historical rows by an
attacker who has write access to the SQLite file but not to a
trusted external copy of any earlier `record_hash`**.

Detected:

- Modifying any field of a past row (including `violations`,
  `decision`, `timestamp`, `agent_id`, etc.) — the recomputed
  `record_hash` no longer matches the stored one.
- Changing a stored `previous_hash` — the next row's chain check fails.
- Reordering rows — sequence gaps are flagged.
- Deleting rows — sequence gaps are flagged.

**Not** detected:

- An attacker with write access who **rewrites the entire chain from
  the tampered row forward** (recomputing every subsequent
  `record_hash`). The local database alone cannot prove the chain has
  not been entirely re-forged. To detect this you must publish or
  archive `record_hash` values to an external location (an append-only
  log, a notary service, a remote SIEM, a Git commit, …) and compare.
- Loss of records that have not yet been written (process crash before
  `record()` returns; SQLite WAL flush guarantees apply).
- Side channels (timing, file-system metadata).

The audit log is **defense in depth, not a notary**. Pair it with an
external archival mechanism if you need non-repudiation.
