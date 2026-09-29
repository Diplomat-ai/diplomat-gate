# Receipt format — specification v1

`receipt_format_version: "1"`

This document specifies the **audit receipt chain** written by
diplomat-gate (`diplomat_gate.audit.AuditLog`) and how to verify it
without installing diplomat-gate. It is written for an external
auditor: no Python knowledge is required to re-implement the check.

- Human-oriented overview and migration notes: [audit-trail.md](audit-trail.md)
- SARIF/JSONL export (`diplomat-gate audit export`) is a **derived view** of
  the receipts documented here, for tooling (GitHub Code Scanning, a SIEM) —
  it is not a redefinition of the format; see [audit-trail.md](audit-trail.md)
  for its output shapes and flags.
- Reference verifier (single file, Python standard library only):
  [`tools/verify_receipts.py`](../tools/verify_receipts.py)
- Library implementation: `src/diplomat_gate/audit.py`
  (`compute_record_hash`, `verify_chain`)

## 1. What a receipt is

Every verdict produced by `Gate.evaluate()` is stored as one row of the
SQLite table `verdicts`. Each row ends with a `record_hash`: the SHA-256
of the row's contents **and of the previous row's `record_hash`**. The
rows therefore form a hash chain: changing any past row invalidates its
own hash and every link after it.

## 2. Hashed fields

Twelve fields are covered by the hash, and none other. `created_at` and
any other column are **not** hashed.

| field                | SQLite type | JSON type in the hashed payload | notes |
| -------------------- | ----------- | ------------------------------- | ----- |
| `verdict_id`         | TEXT        | string                          | UUIDv4 |
| `sequence`           | INTEGER     | number (integer)                | strictly increasing, starts at 1 |
| `timestamp`          | TEXT        | string                          | ISO-8601 UTC, hashed exactly as stored |
| `agent_id`           | TEXT        | string                          | may be the empty string |
| `action`             | TEXT        | string                          | tool-call action |
| `params_hash`        | TEXT        | string                          | SHA-256 hex of the canonical tool-call parameters |
| `decision`           | TEXT        | string                          | `CONTINUE`, `REVIEW` or `STOP` |
| `policies_evaluated` | INTEGER     | number (integer)                | |
| `policies_failed`    | INTEGER     | number (integer)                | |
| `violations`         | TEXT        | **string**                      | a JSON document stored as text; hashed as that text, not re-parsed |
| `latency_ms`         | REAL        | number (float)                  | see section 3, rule 4 |
| `previous_hash`      | TEXT        | string                          | `record_hash` of the previous row, or the genesis value |

The table lists the fields in the order they are declared in the reference
implementation. **That is not the serialization order**: keys are sorted
alphabetically before hashing (section 3, rule 1). A verifier that follows
the table order will never match.

The stored `record_hash` (64 lowercase hex characters) is the result,
not an input.

## 3. Canonical encoding

The hashed payload is a JSON object with exactly the twelve keys above.
It is serialized as follows, byte for byte:

1. **Keys sorted alphabetically** (code-point order; `sort_keys=True` in
   the reference implementation): `action`,
   `agent_id`, `decision`, `latency_ms`, `params_hash`,
   `policies_evaluated`, `policies_failed`, `previous_hash`, `sequence`,
   `timestamp`, `verdict_id`, `violations`. The order in which the
   fields appear in the table of section 2 is **not** the serialization
   order.
2. **Compact separators**: `,` between members and `:` between key and
   value, with no whitespace anywhere.
3. **ASCII output**: every non-ASCII character in a string is escaped as
   `\uXXXX` (lowercase hex, surrogate pairs for characters above U+FFFF);
   `"` and `\` are escaped as `\"` and `\\`; control characters use the
   short escapes `\n`, `\r`, `\t`, `\b`, `\f` or `\u00XX`. This is the
   default behaviour of Python's `json.dumps` with `ensure_ascii=True`.
4. **Numbers**: integers are written in decimal with no sign for
   positives and no fraction. `latency_ms` is written as the shortest
   decimal digit string that round-trips to the same IEEE-754 double
   (the format of Python's `repr(float)`), as follows:
   - **Fixed notation** when `0.0001 <= |x| < 1e16`, and for `0`. It
     always contains a decimal point: `0.25`, `1.5`, `2.0`, `0.0`,
     `0.0001`, `1000000000000000.0` — never `2` or `0`.
   - **Scientific notation** otherwise (`|x| < 0.0001` or `|x| >= 1e16`):
     the mantissa digits (with a `.` only if there is more than one
     digit), then a lowercase `e`, then a **mandatory sign** (`+` or `-`),
     then the exponent with **at least two digits**: `5e-05`, `1.5e-05`,
     `9.999e-05`, `1e+16`, `1.2345678901234568e+17` — never `5e-5`,
     `5E-05` or `1e16`.

   A re-implementation in a language whose default float formatting
   differs must reproduce these rules; float formatting is the most common
   source of false `INVALID` results. Record 3 in section 6 exercises the
   scientific notation.
5. **Encoding and digest**: the resulting text is encoded as UTF-8 and
   hashed with SHA-256. `record_hash` is the 64-character lowercase
   hexadecimal digest.

Reference (Python):

```python
payload = {name: record[name] for name in FIELDS if name != "previous_hash"}
payload["previous_hash"] = previous_hash
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
record_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

## 4. Chaining

- The first record (`sequence = 1`) has
  `previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"`
  (64 zeros, the *genesis* value).
- Every later record has `previous_hash` equal to the `record_hash` of
  the record with `sequence - 1`.

## 5. Verification algorithm

Read all rows ordered by `sequence` ascending. Start with
`expected_sequence = 1` and `expected_previous = genesis`. For each row:

1. If `sequence != expected_sequence`: **INVALID** (gap or reordering).
2. If `previous_hash != expected_previous`: **INVALID**.
3. Recompute the hash from section 3 using the row's own
   `previous_hash`. If it differs from the stored `record_hash`:
   **INVALID**.
4. Set `expected_sequence += 1` and `expected_previous = record_hash`.

If every row passes, the chain is **valid**. The first failing row is
reported as the *first invalid sequence*. The verification is read-only:
the database file is never modified (SQLite may create a `-shm` side file
when reading a database in WAL mode).

`tools/verify_receipts.py` implements exactly this and exits with
`0` (valid), `1` (invalid) or `2` (usage error, or the database cannot be
opened or lacks the `verdicts` table).

## 6. Test vectors

Use these to validate an independent implementation. They were computed
from sections 2 to 4 by writing the canonical string by hand and hashing
it with `sha256sum`, **not** by running diplomat-gate.

**Record 1** — `params_hash` is `ab` repeated 32 times; `violations` is
the 38-character text `[{"policy_id":"payment.amount_limit"}]`.

Canonical string:

```
{"action":"charge_card","agent_id":"demo-agent","decision":"STOP","latency_ms":0.25,"params_hash":"abababababababababababababababababababababababababababababababab","policies_evaluated":1,"policies_failed":1,"previous_hash":"0000000000000000000000000000000000000000000000000000000000000000","sequence":1,"timestamp":"2026-01-01T00:00:00+00:00","verdict_id":"00000000-0000-4000-8000-000000000001","violations":"[{\"policy_id\":\"payment.amount_limit\"}]"}
```

`record_hash` =
`3b759ae20fa503e3289d43cac2e51a024b922457916c5c890b5c3d30f80bb41c`

**Record 2** — chained on record 1; `params_hash` is `cd` repeated 32
times; `agent_id` is empty; `violations` is `[]`.

Canonical string:

```
{"action":"send_email","agent_id":"","decision":"CONTINUE","latency_ms":1.5,"params_hash":"cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd","policies_evaluated":2,"policies_failed":0,"previous_hash":"3b759ae20fa503e3289d43cac2e51a024b922457916c5c890b5c3d30f80bb41c","sequence":2,"timestamp":"2026-01-01T00:00:01+00:00","verdict_id":"00000000-0000-4000-8000-000000000002","violations":"[]"}
```

`record_hash` =
`15e71cea9a920104a316e4b63cb578ffb42cd1f48808ce8de6772d64093bdb23`

**Record 3** — chained on record 2; exercises scientific notation for
`latency_ms` (`5e-05`) and ASCII escaping (`agent_id` is `agent-é`, hashed
as the six-character escape `\u00e9`); `params_hash` is `ef` repeated 32
times; `violations` is `[]`.

Canonical string:

```
{"action":"charge_card","agent_id":"agent-\u00e9","decision":"REVIEW","latency_ms":5e-05,"params_hash":"efefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefef","policies_evaluated":1,"policies_failed":0,"previous_hash":"15e71cea9a920104a316e4b63cb578ffb42cd1f48808ce8de6772d64093bdb23","sequence":3,"timestamp":"2026-01-01T00:00:02+00:00","verdict_id":"00000000-0000-4000-8000-000000000003","violations":"[]"}
```

`record_hash` =
`c7c90bbbdc5c52273f851ee86f36970760b0b9a757b1d7842dd85d5b39969051`

## 7. What verification proves — and what it does not

The chain protects against **tampering with historical rows by an
attacker who has write access to the SQLite file but not to a trusted
external copy of any earlier `record_hash`**.

Detected:

- Modifying any hashed field of a past row — the recomputed
  `record_hash` no longer matches the stored one.
- Changing a stored `previous_hash` — the chain check fails.
- Reordering rows — sequence gaps are flagged.
- Deleting rows in the middle of the chain — sequence gaps are flagged.

**Not** detected:

- An attacker with write access who **rewrites the entire chain from the
  tampered row forward** (recomputing every subsequent `record_hash`).
  The local database alone cannot prove the chain has not been entirely
  re-forged. Detecting this requires publishing or archiving
  `record_hash` values to an external location (an append-only log, a
  notary service, a remote SIEM, a Git commit, …) and comparing.
- **Truncation of the tail**: deleting the last N rows leaves a shorter
  but internally valid chain. Only an externally archived copy of the
  latest `record_hash` reveals it.
- Modification of columns that are not hashed (`created_at`).
- Loss of records that were never written (process crash before
  `record()` returns; SQLite WAL guarantees apply).
- The correctness of the decisions themselves: a valid chain proves the
  records were not altered after being written, not that the policies
  were right.

The receipt chain is **defense in depth, not a notary**. It carries no
signature and no trusted timestamp.

## 8. Versioning and compatibility

`receipt_format_version: "1"` is the format described here. The set of
hashed fields, their canonical encoding and the genesis value are part of
the format: changing any of them is a **breaking change** and requires a
new format version. Additive changes that leave the hashed payload
untouched (for example new unhashed columns) do not.

Version 1 is a **firm** commitment: the hashing algorithm has been
unchanged since it was introduced (0.2.0 development cycle) and has been
published since diplomat-gate 0.3.0. Any future change to the set of
hashed fields, to the JSON encoding rules of section 3, or to the genesis
value will be published as format version 2 and never applied silently to
version 1 data.
