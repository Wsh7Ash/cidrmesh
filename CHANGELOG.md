# Changelog

## [1.0.0] - 2026-11-13

### Added

- `check` for duplicate, containment, outside-parent and version findings.
- Exact free-space calculation and utilization for a parent prefix.
- `free` command listing largest unallocated blocks.
- `allocate` command with first-fit splitting and `24:4,26:2` request syntax.
- JSON plans, plain `label, cidr` files, IPv4 and IPv6 support.
- pytest suite covering conflicts, free space, allocation and CLI behaviour.
