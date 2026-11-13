# Contributing

## Setup

```shell
python -m pip install -e . pytest
python -m pytest tests -q
```

## Invariants to preserve

- CIDR blocks are either disjoint or nested; conflict logic must not assume
  partial overlaps.
- Nested blocks must never be double-counted in utilization.
- Allocation must never return a block that touches a used block.

## Adding a finding kind

1. Emit a `Finding(kind, severity, detail, a, b)` where severities come from
   `SEVERITY_ORDER`.
2. Add it to the CLI documentation table in `docs/USAGE.md`.
3. Add a test that triggers it and one that must not.

## Style

- Standard library only (`ipaddress` for all math).
- Keep parsing (`parse_*`) separate from policy (`analyze`, `allocate`).
