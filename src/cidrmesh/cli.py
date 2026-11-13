"""Command line interface for cidrmesh."""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys

from . import (
    PlanError,
    allocate,
    analyze,
    at_or_above,
    free_blocks,
    load_blocks_file,
    parse_plan,
    parse_requests,
    render_json,
    render_text,
)


def _load_plan(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanError(f"{path} is not valid JSON: {exc}") from exc
    return parse_plan(data)


def _network(value: str):
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise PlanError(f"invalid network '{value}': {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cidrmesh",
        description="Check CIDR plans for conflicts, find free space and allocate subnets.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate a JSON plan")
    check.add_argument("plan", help="plan JSON with 'parent' and 'blocks'")
    check.add_argument("--json", action="store_true")
    check.add_argument("--free-limit", type=int, default=20)
    check.add_argument("--fail-on", choices=["none", "low", "medium", "high"], default="medium")

    free = sub.add_parser("free", help="list unallocated blocks inside a parent")
    free.add_argument("--parent", required=True, help="parent CIDR, e.g. 10.0.0.0/16")
    free.add_argument("--used", help="JSON plan or newline-separated CIDR file")
    free.add_argument("--limit", type=int, default=20)
    free.add_argument("--json", action="store_true")

    alloc = sub.add_parser("allocate", help="first-fit allocate subnets inside a parent")
    alloc.add_argument("--parent", required=True)
    alloc.add_argument("--need", required=True, help="prefix requests, e.g. '24:4,26:2'")
    alloc.add_argument("--used", help="JSON plan or newline-separated CIDR file")
    alloc.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "check":
            parent, blocks = _load_plan(args.plan)
            analysis = analyze(parent, blocks, args.free_limit)
            print(render_json(analysis) if args.json else render_text(analysis))
            if args.fail_on != "none" and at_or_above(analysis.findings, args.fail_on):
                return 1
            return 0

        parent = _network(args.parent)
        used = load_blocks_file(args.used) if args.used else []

        if args.command == "free":
            nets = sorted(
                free_blocks(parent, used),
                key=lambda net: (-net.num_addresses, int(net.network_address)),
            )
            shown = nets[: args.limit]
            if args.json:
                print(json.dumps({"parent": str(parent), "free": [str(n) for n in shown],
                                  "total_free_blocks": len(nets)}, indent=2))
            else:
                print(f"free blocks inside {parent} ({len(nets)} total, showing {len(shown)}):")
                for net in shown:
                    print(f"  {net}")
            return 0

        prefixes = parse_requests(args.need)
        allocations = allocate(parent, used, prefixes)
    except (OSError, PlanError, ValueError) as exc:
        print(f"cidrmesh: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"parent": str(parent), "allocations": [a.to_dict() for a in allocations]}, indent=2))
    else:
        print(f"allocated {len(allocations)} block(s) inside {parent}:")
        for allocation in allocations:
            print(f"  {allocation.label:8} {allocation.cidr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
