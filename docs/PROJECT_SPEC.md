# PROJECT_SPEC — cidrmesh

- **Name:** cidrmesh
- **Category:** networking
- **Target user:** sysadmins and network engineers keeping an IP plan in a
  spreadsheet or wiki
- **Problem:** duplicates, nested blocks and unknown free space make the plan
  unreliable, and choosing the next subnet is manual.
- **Solution:** offline CLI that validates plans, computes exact free CIDR
  blocks and allocates new subnets first-fit.
- **Core workflow:** plan → `check` conflicts/utilization → `free` space →
  `allocate` → update plan.
- **Must-have features:** duplicate/containment detection, outside-parent
  warnings, free-space subtraction, utilization, allocation, IPv4/IPv6, JSON.
- **Nice-to-have features:** pools, snapshot diffing, growth-aware allocation.
- **Stack:** Python 3.10+ `ipaddress`.
- **Test strategy:** nested/disjoint/duplicate blocks, free-space gaps,
  allocation splits and failures, IPv6, CLI exit codes, plain-text loading.
- **Demo/result strategy:** `examples/plan.json` plus `results/` reports.
- **Safety considerations:** offline, no device access, no credentials; plans
  may contain internal addressing so reports are reviewed before sharing.
- **Definition of done:** tests pass, install works, demo recorded, docs match
  behaviour, no secrets.
