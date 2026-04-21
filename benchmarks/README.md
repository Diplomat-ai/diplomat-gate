# diplomat-gate microbenchmarks

Tiny harness that times the most common `Gate.evaluate()` paths.

```
python benchmarks/run.py                    # default 5k iters per scenario
python benchmarks/run.py --iterations 50000
python benchmarks/run.py --only simple_allow
python benchmarks/run.py --json out.json    # also write machine-readable output
```

Or via the Makefile:

```
make bench
```

## Scenarios

| name              | description                                                 |
| ----------------- | ----------------------------------------------------------- |
| `simple_allow`    | One amount-limit policy; the call is well below the limit    |
| `simple_block`    | One amount-limit policy; the call is over the limit          |
| `multi_policy`    | Five policies (3 payment + 2 email), all CONTINUE            |
| `with_audit`      | Single policy + SQLite hash-chain audit on every call        |

## Caveats

- Microbench only — designed to detect order-of-magnitude regressions,
  not to be quoted as user-facing throughput numbers.
- Uses `time.perf_counter_ns` for sample timing. Warm-up = `min(100, iters)`.
- The `with_audit` scenario writes to `tempfile.gettempdir()`. Re-runs
  delete the prior file so the chain length stays controlled.
- Numbers vary heavily with disk speed (SSD vs spinning rust vs WSL2
  loopback) for the audit scenario.
