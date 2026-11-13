# Architecture

## Layers

```text
plan JSON / text ──► parse_blocks / parse_plan ──► [Block(network, label)]
                                                        │
                         ┌──────────────────────────────┼──────────────────────┐
                         ▼                              ▼                      ▼
                 find_conflicts()              free_blocks()             allocate()
                 duplicate / contained         range subtraction          first-fit split
                         │                              │                      │
                         └──────────────► analyze() ◄───┘                      │
                                              │                                 ▼
                                    render_text / render_json          [Allocation]
```

## CIDR invariants

Two CIDR blocks either do not intersect, or one fully contains the other.
Therefore conflict detection needs only equality and `subnet_of`; there is no
"partial overlap" case to model. Findings are: `duplicate` (low), `contained`
(medium), `outside-parent` and `version-mismatch` (high/medium) when a parent is
declared.

## Free space

Used blocks are converted to integer ranges, clipped to the parent, sorted and
merged (adjacent or overlapping ranges collapse). Walking the gaps yields
integer ranges that `ipaddress.summarize_address_range` converts back into the
smallest set of CIDR blocks. Merging before subtraction is what prevents nested
blocks from being counted twice in utilization.

## Allocation

`_take` finds the first free block whose prefix is short enough, removes it, and
repeatedly splits (`subnets(1)`) until the requested prefix is reached, pushing
the unused half into the free list in address order. First-fit keeps the
algorithm predictable and O(blocks × splits) for small plans.

## Error model

Everything user-facing raises `PlanError`: malformed JSON, missing `cidr`,
invalid prefix, or an allocation that cannot fit. The CLI maps it to exit code 2
and prints a single diagnostic line.

## Rendering

Text output is for humans reading a plan review; JSON is stable for pipelines.
Free blocks are sorted largest-first for display, while allocation consumes
them in ascending address order.
