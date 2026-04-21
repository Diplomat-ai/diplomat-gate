"""Microbenchmarks for diplomat-gate.

Run with::

    python benchmarks/run.py
    python benchmarks/run.py --json results.json
    make bench

Reports per-call latency for the most common gate paths. Numbers are
deterministic enough to be meaningful in CI but should be re-run on the
target hardware before being quoted publicly.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from diplomat_gate import Gate


@dataclass
class BenchResult:
    name: str
    iterations: int
    total_seconds: float
    mean_us: float
    median_us: float
    p95_us: float
    p99_us: float
    ops_per_second: float


def _measure(name: str, fn: Callable[[], None], iterations: int) -> BenchResult:
    # Warm-up.
    for _ in range(min(100, iterations)):
        fn()
    samples_ns: list[int] = []
    t0 = time.perf_counter()
    for _ in range(iterations):
        s = time.perf_counter_ns()
        fn()
        samples_ns.append(time.perf_counter_ns() - s)
    total = time.perf_counter() - t0
    samples_us = [n / 1_000 for n in samples_ns]
    samples_us.sort()
    return BenchResult(
        name=name,
        iterations=iterations,
        total_seconds=total,
        mean_us=statistics.fmean(samples_us),
        median_us=samples_us[len(samples_us) // 2],
        p95_us=samples_us[int(len(samples_us) * 0.95)],
        p99_us=samples_us[int(len(samples_us) * 0.99)],
        ops_per_second=iterations / total if total > 0 else float("inf"),
    )


def bench_simple_allow(iterations: int) -> BenchResult:
    gate = Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 10_000}]})
    call = {"action": "charge_card", "amount": 100}
    return _measure("simple_allow", lambda: gate.evaluate(call), iterations)


def bench_simple_block(iterations: int) -> BenchResult:
    gate = Gate.from_dict({"payment": [{"id": "payment.amount_limit", "max_amount": 100}]})
    call = {"action": "charge_card", "amount": 5_000}
    return _measure("simple_block", lambda: gate.evaluate(call), iterations)


def bench_multi_policy(iterations: int) -> BenchResult:
    gate = Gate.from_dict(
        {
            "payment": [
                {"id": "payment.amount_limit", "max_amount": 10_000},
                {"id": "payment.velocity", "max_txn": 1_000_000, "window": "1h"},
                {"id": "payment.daily_limit", "max_daily": 1_000_000},
            ],
            "email": [
                {"id": "email.domain_blocklist", "blocked": ["*.evil.com"]},
                {"id": "email.rate_limit", "max": 1_000_000, "window": "1h"},
            ],
        }
    )
    call = {"action": "charge_card", "amount": 100}
    return _measure("multi_policy_5", lambda: gate.evaluate(call), iterations)


def bench_with_audit(iterations: int) -> BenchResult:
    db = Path(tempfile.gettempdir()) / "diplomat-gate-bench-audit.db"
    db.unlink(missing_ok=True)
    gate = Gate.from_dict(
        {"payment": [{"id": "payment.amount_limit", "max_amount": 10_000}]},
        audit_path=str(db),
    )
    call = {"action": "charge_card", "amount": 100}
    try:
        return _measure("with_audit_sqlite", lambda: gate.evaluate(call), iterations)
    finally:
        gate.close()


BENCHMARKS: list[tuple[str, Callable[[int], BenchResult]]] = [
    ("simple_allow", bench_simple_allow),
    ("simple_block", bench_simple_block),
    ("multi_policy", bench_multi_policy),
    ("with_audit", bench_with_audit),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--json", type=Path, default=None, help="Write results to a JSON file")
    parser.add_argument("--only", type=str, default=None, help="Run a single named benchmark")
    args = parser.parse_args()

    results: list[BenchResult] = []
    for name, fn in BENCHMARKS:
        if args.only and name != args.only:
            continue
        results.append(fn(args.iterations))

    fmt = "{:<22} {:>10} {:>10} {:>10} {:>10} {:>10} {:>14}"
    print(fmt.format("name", "iters", "mean_us", "median_us", "p95_us", "p99_us", "ops/s"))
    print("-" * 90)
    for r in results:
        print(
            fmt.format(
                r.name,
                r.iterations,
                f"{r.mean_us:.2f}",
                f"{r.median_us:.2f}",
                f"{r.p95_us:.2f}",
                f"{r.p99_us:.2f}",
                f"{r.ops_per_second:,.0f}",
            )
        )

    if args.json:
        args.json.write_text(json.dumps([asdict(r) for r in results], indent=2))
        print(f"\nresults written to {args.json}")


if __name__ == "__main__":
    main()
