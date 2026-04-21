"""Command-line interface for diplomat-gate.

Currently exposes ``audit`` and ``review`` subcommands:

* ``diplomat-gate audit verify --db <path>``
* ``diplomat-gate audit rebuild-chain --db <path>``
* ``diplomat-gate review list --db <path> [--status pending] [--limit 50]``
* ``diplomat-gate review show --db <path> --id <item_id>``
* ``diplomat-gate review approve --db <path> --id <item_id> --reviewer <name> [--note ...]``
* ``diplomat-gate review reject --db <path> --id <item_id> --reviewer <name> [--note ...]``

Exit codes:
    0 — operation succeeded
    1 — chain is invalid (audit verify only) or item not found (review)
    2 — usage / IO error
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .audit import rebuild_chain, verify_chain
from .review import ReviewQueue, ReviewQueueError


def _format_verify(result, *, use_color: bool) -> str:
    if use_color:
        green = "\x1b[32m"
        red = "\x1b[31m"
        reset = "\x1b[0m"
    else:
        green = red = reset = ""
    if result.valid:
        return f"{green}OK{reset}: chain valid ({result.records_checked} record(s) checked)"
    return (
        f"{red}INVALID{reset}: {result.error} "
        f"(first invalid sequence: {result.first_invalid_sequence}, "
        f"checked {result.records_checked} record(s) before failure)"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diplomat-gate",
        description="diplomat-gate CLI — runtime action firewall for AI agents.",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable ANSI colors in the output."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    audit = sub.add_parser("audit", help="Audit log operations.")
    audit_sub = audit.add_subparsers(dest="audit_cmd", required=True)

    verify = audit_sub.add_parser("verify", help="Verify the hash chain.")
    verify.add_argument("--db", required=True, help="Path to the SQLite audit database.")

    rebuild = audit_sub.add_parser(
        "rebuild-chain",
        help="Recompute sequence/previous_hash/record_hash for every row.",
    )
    rebuild.add_argument("--db", required=True, help="Path to the SQLite audit database.")

    review = sub.add_parser("review", help="Review queue operations.")
    review_sub = review.add_subparsers(dest="review_cmd", required=True)

    rl = review_sub.add_parser("list", help="List review items.")
    rl.add_argument("--db", required=True, help="Path to the SQLite review queue database.")
    rl.add_argument(
        "--status",
        default="pending",
        choices=["pending", "approved", "rejected", "expired", "all"],
        help="Filter by status (default: pending). Use 'all' to list every status.",
    )
    rl.add_argument("--limit", type=int, default=50)
    rl.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of text."
    )

    rs = review_sub.add_parser("show", help="Show a single review item.")
    rs.add_argument("--db", required=True)
    rs.add_argument("--id", required=True, dest="item_id")

    ra = review_sub.add_parser("approve", help="Approve a pending review item.")
    ra.add_argument("--db", required=True)
    ra.add_argument("--id", required=True, dest="item_id")
    ra.add_argument("--reviewer", required=True)
    ra.add_argument("--note", default="")

    rr = review_sub.add_parser("reject", help="Reject a pending review item.")
    rr.add_argument("--db", required=True)
    rr.add_argument("--id", required=True, dest="item_id")
    rr.add_argument("--reviewer", required=True)
    rr.add_argument("--note", default="")

    return parser


def _format_item_text(item) -> str:
    lines = [
        f"id:         {item.item_id}",
        f"verdict:    {item.verdict_id}",
        f"status:     {item.status}",
        f"created_at: {item.created_at}",
        f"agent_id:   {item.agent_id or '-'}",
        f"action:     {item.action}",
        f"params:     {json.dumps(item.params, sort_keys=True)}",
        f"violations: {json.dumps(item.violations, sort_keys=True)}",
    ]
    if item.decided_at:
        lines.append(f"decided_at: {item.decided_at}")
        lines.append(f"decided_by: {item.decided_by}")
        if item.decision_note:
            lines.append(f"note:       {item.decision_note}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    use_color = sys.stdout.isatty() and not args.no_color

    if args.cmd == "audit" and args.audit_cmd == "verify":
        try:
            result = verify_chain(args.db)
        except Exception as exc:  # noqa: BLE001 - CLI surface
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(_format_verify(result, use_color=use_color))
        return 0 if result.valid else 1

    if args.cmd == "audit" and args.audit_cmd == "rebuild-chain":
        try:
            n = rebuild_chain(args.db)
        except Exception as exc:  # noqa: BLE001 - CLI surface
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"rebuilt chain: {n} record(s) rewritten")
        return 0

    if args.cmd == "review":
        try:
            queue = ReviewQueue(args.db)
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 2
        try:
            return _handle_review(args, queue)
        finally:
            queue.close()

    parser.print_help(sys.stderr)
    return 2


def _handle_review(args, queue: ReviewQueue) -> int:
    if args.review_cmd == "list":
        status = None if args.status == "all" else args.status
        items = queue.list(status=status, limit=args.limit)
        if args.json:
            print(json.dumps([i.to_dict() for i in items], default=str))
            return 0
        if not items:
            print("(no items)")
            return 0
        for item in items:
            print(
                f"{item.item_id}  {item.status:<9}  {item.created_at}  "
                f"{item.action}  agent={item.agent_id or '-'}"
            )
        return 0

    if args.review_cmd == "show":
        item = queue.get(args.item_id)
        if item is None:
            print(f"item not found: {args.item_id}", file=sys.stderr)
            return 1
        print(_format_item_text(item))
        return 0

    if args.review_cmd in ("approve", "reject"):
        action = queue.approve if args.review_cmd == "approve" else queue.reject
        try:
            item = action(args.item_id, args.reviewer, note=args.note)
        except ReviewQueueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"{args.review_cmd}d {item.item_id} (status={item.status})")
        return 0

    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
