# Review queue

The review queue is the human-in-the-loop counterpart to the audit
trail. When a verdict's decision is `REVIEW`, `diplomat-gate` enqueues
the call into a separate SQLite database; an operator then approves or
rejects it via the CLI or the Python API.

The queue lives in its **own** SQLite file, distinct from the audit
log. Operator decisions never mutate the immutable hash chain.

## Enabling the queue

### From YAML

```yaml
review_queue:
  enabled: true
  path: "./diplomat-review.db"   # default if enabled and path omitted
```

### From code

```python
from diplomat_gate import Gate

gate = Gate.from_dict(
    {"email": [{"id": "email.business_hours", "on_fail": "REVIEW"}]},
    review_queue_path="./diplomat-review.db",
)
```

When `review_queue_path` is set, `gate.evaluate(...)` automatically
calls `gate.review_queue.enqueue(verdict)` on every `REVIEW` verdict.

## Item lifecycle

```
   pending  --approve-->  approved
      |
      |--reject------->  rejected
      |
      +--ttl elapsed-->  expired   (via expire_due())
```

Transitions are guarded inside a `BEGIN IMMEDIATE` transaction. Any
attempt to decide a non-pending item raises `ReviewQueueError`.

## CLI

```
diplomat-gate review list    --db ./diplomat-review.db [--status pending|approved|rejected|expired|all] [--limit N] [--json]
diplomat-gate review show    --db ./diplomat-review.db --id <item_id>
diplomat-gate review approve --db ./diplomat-review.db --id <item_id> --reviewer <name> [--note "..."]
diplomat-gate review reject  --db ./diplomat-review.db --id <item_id> --reviewer <name> [--note "..."]
```

Exit codes:

- `0` — success.
- `1` — item not found, or transition refused (already decided).
- `2` — usage / IO error.

Add `--no-color` (global flag, before the subcommand) to disable ANSI.

## Programmatic API

```python
from diplomat_gate import ReviewQueue, ReviewQueueError

q = ReviewQueue("./diplomat-review.db")

for item in q.list(status="pending", limit=50):
    print(item.item_id, item.action, item.params)

q.approve("01ab...", reviewer="alice", note="ok, vendor whitelisted")
try:
    q.reject("01ab...", reviewer="alice")
except ReviewQueueError as e:
    print(e)   # already approved -> cannot transition

q.expire_due()       # flips pending items past expires_at to "expired"
q.pending_count()    # int
q.close()
```

## Redaction

By default sensitive fields (`recipient`, `to`, `email`, `domain`,
`amount`, `card_last4`, `phone` — see `diplomat_gate.models.SENSITIVE_FIELDS`)
are hashed to `"h:" + sha256(value)[:16]` **before** being persisted to
the queue, in both `params` and the per-violation `context`. Opt out
explicitly:

```python
ReviewQueue("./review.db", redact_params=False)   # raw values stored
```

`SENSITIVE_FIELDS` is mutable at runtime if you need to add domain-
specific keys. Mutate it once at startup, before any `Gate` evaluates.

## TTL / auto-expiry

```python
q = ReviewQueue("./review.db", ttl_seconds=3600)        # default for all enqueues
q.enqueue(verdict, ttl_seconds=600)                     # per-item override

# In a periodic job:
expired = q.expire_due()    # returns the number of rows flipped
```

`expire_due()` only inspects items still in `pending`. Already-decided
items are never altered.

## Storage layout

Single table `review_items` with indexes on `status` and `created_at`:

| column          | type    | notes                                       |
| --------------- | ------- | ------------------------------------------- |
| `item_id`       | TEXT PK | UUIDv4                                       |
| `verdict_id`    | TEXT    | links back to the audit log if enabled      |
| `created_at`    | TEXT    | ISO-8601 UTC                                |
| `expires_at`    | REAL    | epoch seconds, nullable                     |
| `status`        | TEXT    | `pending` / `approved` / `rejected` / `expired` |
| `agent_id`      | TEXT    |                                              |
| `action`        | TEXT    |                                              |
| `params`        | TEXT    | JSON (redacted by default)                  |
| `violations`    | TEXT    | JSON (per-violation `context` redacted)     |
| `decided_at`    | TEXT    | ISO-8601 UTC, nullable                      |
| `decided_by`    | TEXT    | reviewer name, nullable                     |
| `decision_note` | TEXT    | nullable                                    |

WAL mode + `synchronous=NORMAL` + autocommit; writes are wrapped in
`BEGIN IMMEDIATE` and retry on `SQLITE_BUSY`.

## What this queue does **not** do

- No notifications (Slack, webhook, email). Wrap `enqueue` or poll
  `pending_count()` from your own scheduler.
- No multi-process leader election beyond what SQLite WAL provides.
  For multi-host setups, run a single decider process or front the
  queue with your own service.
- No re-evaluation on approval. After an operator approves an item, the
  agent is expected to re-issue the call; the gate will re-check it,
  and stateful policies (`velocity`, `daily_limit`) still apply.

## Testing tips

- The queue is happy with `:memory:` databases — useful for unit tests.
- `ReviewQueue(redact_params=False)` lets tests assert on raw param
  values without having to recompute redaction hashes.
- `ttl_seconds=0.001` + `expire_due()` is the canonical way to test the
  expiry path deterministically.
