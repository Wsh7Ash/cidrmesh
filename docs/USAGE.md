# Usage

## Where this fits

Typical workflow: export the current plan from whatever wiki or spreadsheet
holds it, convert it to `plan.json`, then run `cidrmesh` before reserving a new
range.

## Validating a plan handed to you

```shell
cidrmesh check examples/plan.json --fail-on low
```

`--fail-on low` surfaces duplicates too. That is useful when the plan is about
to be imported into an IPAM tool and duplicates would create ambiguity.

## Finding room for a new service

```shell
cidrmesh free --parent 10.20.0.0/16 --used plan.json --limit 10
```

Free blocks are listed largest first. Prefer the largest block that still
leaves useful growth room; allocating from the middle of a large block
fragments the space.

## Reserving subnets

```shell
cidrmesh allocate --parent 10.20.0.0/16 --used plan.json --need "24:4,26:2"
```

Output names blocks `net-1..net-N`. Copy them into your plan file and commit it,
so the next run treats them as used.

## Using plain text instead of JSON

```text
# used.txt
web, 10.20.1.0/24
db,  10.20.2.0/25
10.20.3.0/24
```

```shell
cidrmesh free --parent 10.20.0.0/16 --used used.txt
```

Blank lines and `#` comments are ignored; the field before the comma is a label.

## Reading findings

| Kind | Meaning | Action |
|---|---|---|
| `duplicate` | same prefix listed twice | delete one entry |
| `contained` | a block sits inside another | confirm this is intentional delegation |
| `outside-parent` | block not inside the declared parent | fix the parent or the block |
| `version-mismatch` | IPv4 block in an IPv6 plan | separate the plans |

## Library use

```python
import ipaddress
from cidrmesh import allocate, free_blocks, parse_blocks, parse_requests

parent = ipaddress.ip_network("10.0.0.0/24")
used = parse_blocks(["10.0.0.0/26"])
print([str(n) for n in free_blocks(parent, used)])
print([a.cidr for a in allocate(parent, used, parse_requests("26:2"))])
```
