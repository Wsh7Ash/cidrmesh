# cidrmesh

**Stop maintaining IP plans in a spreadsheet. Check overlaps, see real free
space and allocate the next subnet in one command.**

## Why

Network plans drift: a subnet gets listed twice, a `/25` quietly sits inside a
`/24`, and nobody can say how much of `10.0.0.0/16` is actually free. `cidrmesh`
reads a small JSON (or plain text) plan, reports duplicates, containment and
out-of-parent blocks, and computes the exact unallocated blocks. `allocate`
then carves new subnets first-fit, so the plan and reality stay aligned.

## Features

- Duplicate, containment and outside-parent detection with severities
- Exact free-space calculation via address-range subtraction, summarized back
  into CIDR blocks
- Utilization ratio for a parent prefix, with nested blocks merged so addresses
  are never double-counted
- First-fit subnet allocation (`--need 24:4,26:2`) that never overlaps
- IPv4 and IPv6
- JSON plans or plain `label, cidr` text files; text and JSON output

## Example output

Output for `examples/plan.json` (reproduced in `RESULTS.md`):

```text
cidrmesh plan
==============================================
parent: 10.20.0.0/16
utilization: 768/65536 addresses (1.17%)
conflicts: 1
  [MEDIUM] contained       10.20.3.0/25 is inside 10.20.3.0/24
largest free blocks:
  10.20.128.0/17
  10.20.64.0/18
  10.20.32.0/19
  10.20.16.0/20
  10.20.8.0/21
  10.20.4.0/22
  10.20.0.0/24
```

## Architecture

```text
src/cidrmesh/__init__.py   parsing, conflict rules, free space, allocation
src/cidrmesh/cli.py        check / free / allocate commands
tests/test_cidrmesh.py     conflict, free-space, allocation and CLI coverage
```

Free space is computed on integer address ranges (`int(network_address)`), then
fed through `ipaddress.summarize_address_range` to return legal CIDR blocks.
Allocation repeatedly splits a chosen free block until it reaches the requested
prefix length, returning the unused half to the free list.

## Requirements

- Python 3.10+ (standard library only)
- pytest for tests

## Installation

```shell
git clone https://github.com/Wsh7Ash/cidrmesh.git
cd cidrmesh
python -m pip install -e .
```

## Quick start

```shell
cidrmesh check examples/plan.json
cidrmesh free --parent 10.0.0.0/24 --used examples/plan.json
```

## Usage

```shell
# Validate a plan and fail CI on medium conflicts
cidrmesh check plan.json --fail-on medium

# List the 5 largest free blocks
cidrmesh free --parent 10.0.0.0/16 --used used.txt --limit 5

# Allocate four /24s and two /26s, first fit
cidrmesh allocate --parent 10.0.0.0/16 --used used.txt --need "24:4,26:2"

# Machine-readable output
cidrmesh check plan.json --json
```

Exit codes: `0` ok/below threshold, `1` conflicts at or above `--fail-on`,
`2` bad file, invalid CIDR or impossible allocation.

## Configuration

Flags only. Plan format:

```json
{
  "parent": "10.0.0.0/16",
  "blocks": [
    {"cidr": "10.0.1.0/24", "label": "web"},
    {"cidr": "10.0.2.0/25", "label": "db"}
  ]
}
```

Plain lists accept one `cidr` or `label, cidr` per line, with `#` comments.

## Testing

```shell
python -m pip install -e . pytest
python -m pytest tests -q
```

## Project structure

```text
cidrmesh/
├─ src/cidrmesh/         planner + CLI
├─ tests/                pytest suite
├─ examples/             sample plan
├─ docs/                 architecture, usage, spec
├─ results/              generated reports
└─ .github/workflows/    CI
```

## Limitations

- Allocation is first-fit by address order, not a balanced or reserved design;
  there is no notion of pools, VLANs or regions.
- The plan is a snapshot; the tool does not read live routers or DHCP.
- Containment findings compare every pair, which is O(n²) — fine for hundreds of
  blocks, slow for tens of thousands.
- Only CIDR notation is supported; host ranges must be expressed as prefixes.

## Roadmap

- Named pools per environment
- Alignment and growth-aware allocation strategies
- Diff two plan snapshots to show what changed

## Security notes

No network access, no device connections and no credential handling. Plans may
reveal internal addressing, so review the JSON before publishing a report.

## License

MIT — see `LICENSE`.
