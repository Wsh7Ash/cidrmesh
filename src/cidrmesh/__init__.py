"""cidrmesh - CIDR plans without spreadsheets.

Read a list of network blocks, detect duplicates and containment, compute free
space inside a parent prefix, and allocate new subnets first-fit. Everything is
offline and built on :mod:`ipaddress`.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Sequence

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


class PlanError(ValueError):
    """Raised for malformed plans or impossible allocations."""


@dataclass(frozen=True)
class Block:
    network: Network
    label: str = ""

    @property
    def cidr(self) -> str:
        return str(self.network)


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    detail: str
    a: str = ""
    b: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Analysis:
    parent: str | None
    findings: list[Finding] = field(default_factory=list)
    utilization: float | None = None
    free: list[str] = field(default_factory=list)
    total_addresses: int | None = None
    used_addresses: int | None = None

    def to_dict(self) -> dict:
        return {
            "parent": self.parent,
            "total_addresses": self.total_addresses,
            "used_addresses": self.used_addresses,
            "utilization": self.utilization,
            "findings": [f.to_dict() for f in self.findings],
            "free": list(self.free),
        }


def _network(value: str | Network) -> Network:
    return value if isinstance(value, (ipaddress.IPv4Network, ipaddress.IPv6Network)) else ipaddress.ip_network(value.strip(), strict=False)


def parse_blocks(items: Iterable[dict | str]) -> list[Block]:
    """Parse dictionaries (``cidr``/``label``) or plain CIDR strings."""
    blocks: list[Block] = []
    for item in items:
        if isinstance(item, str):
            blocks.append(Block(_network(item)))
        elif isinstance(item, dict):
            cidr = item.get("cidr") or item.get("block") or item.get("network")
            if not cidr:
                raise PlanError(f"block is missing a cidr field: {item!r}")
            blocks.append(Block(_network(str(cidr)), str(item.get("label") or "")))
        else:
            raise PlanError(f"unsupported block entry: {item!r}")
    return blocks


def parse_plan(data: dict | list) -> tuple[Network | None, list[Block]]:
    if isinstance(data, list):
        return None, parse_blocks(data)
    if not isinstance(data, dict):
        raise PlanError("plan must be a JSON object or array")
    parent = data.get("parent")
    parent_net = _network(parent) if parent else None
    return parent_net, parse_blocks(data.get("blocks") or data.get("used") or [])


def load_blocks_file(path: str) -> list[Block]:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PlanError(f"{path} is not valid JSON: {exc}") from exc
        if isinstance(data, dict):
            return parse_plan(data)[1]
        return parse_blocks(data)
    blocks = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            label, cidr = [part.strip() for part in line.split(",", 1)]
            blocks.append(Block(_network(cidr), label))
        else:
            blocks.append(Block(_network(line)))
    return blocks


def find_conflicts(blocks: Sequence[Block]) -> list[Finding]:
    findings: list[Finding] = []
    for i, left in enumerate(blocks):
        for right in blocks[i + 1:]:
            if left.network.version != right.network.version:
                continue
            if left.network == right.network:
                findings.append(Finding(
                    "duplicate", "low",
                    f"{left.cidr} is listed more than once",
                    left.label or left.cidr, right.label or right.cidr,
                ))
            elif left.network.subnet_of(right.network):
                findings.append(Finding(
                    "contained", "medium",
                    f"{left.cidr} is inside {right.cidr}",
                    left.label or left.cidr, right.label or right.cidr,
                ))
            elif right.network.subnet_of(left.network):
                findings.append(Finding(
                    "contained", "medium",
                    f"{right.cidr} is inside {left.cidr}",
                    right.label or right.cidr, left.label or left.cidr,
                ))
    return findings


def _clipped_ranges(parent: Network, blocks: Iterable[Block]) -> list[tuple[int, int]]:
    start = int(parent.network_address)
    end = int(parent.broadcast_address)
    ranges: list[tuple[int, int]] = []
    for block in blocks:
        if block.network.version != parent.version:
            continue
        lo = max(start, int(block.network.network_address))
        hi = min(end, int(block.network.broadcast_address))
        if lo <= hi:
            ranges.append((lo, hi))
    ranges.sort()
    merged: list[tuple[int, int]] = []
    for lo, hi in ranges:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def free_blocks(parent: Network, used: Iterable[Block]) -> list[Network]:
    """Return every unallocated network inside ``parent``, ascending by address."""
    start = int(parent.network_address)
    end = int(parent.broadcast_address)
    cursor = start
    free: list[Network] = []
    for lo, hi in _clipped_ranges(parent, used):
        if lo > cursor:
            free.extend(ipaddress.summarize_address_range(
                ipaddress.ip_address(cursor), ipaddress.ip_address(lo - 1)
            ))
        cursor = max(cursor, hi + 1)
        if cursor > end:
            break
    if cursor <= end:
        free.extend(ipaddress.summarize_address_range(
            ipaddress.ip_address(cursor), ipaddress.ip_address(end)
        ))
    return free


def utilization(parent: Network, used: Iterable[Block]) -> tuple[int, int, float]:
    total = int(parent.num_addresses)
    used_count = sum(hi - lo + 1 for lo, hi in _clipped_ranges(parent, used))
    return total, used_count, round(used_count / total, 4)


def analyze(parent: Network | None, blocks: Sequence[Block], free_limit: int = 20) -> Analysis:
    findings = find_conflicts(blocks)
    analysis = Analysis(parent=str(parent) if parent else None)

    if parent is not None:
        for block in blocks:
            if block.network.version != parent.version:
                findings.append(Finding("version-mismatch", "medium",
                                        f"{block.cidr} is not the same IP version as {parent}",
                                        block.label or block.cidr, str(parent)))
            elif not block.network.subnet_of(parent):
                findings.append(Finding("outside-parent", "high",
                                        f"{block.cidr} is outside {parent}",
                                        block.label or block.cidr, str(parent)))
        total, used_count, ratio = utilization(parent, blocks)
        analysis.total_addresses = total
        analysis.used_addresses = used_count
        analysis.utilization = ratio
        display = sorted(
            free_blocks(parent, blocks),
            key=lambda net: (-net.num_addresses, int(net.network_address)),
        )
        analysis.free = [str(net) for net in display[:free_limit]]

    analysis.findings = findings
    return analysis


@dataclass(frozen=True)
class Allocation:
    label: str
    cidr: str

    def to_dict(self) -> dict:
        return asdict(self)


def _insert_sorted(blocks: list[Network], block: Network) -> None:
    key = int(block.network_address)
    for index, existing in enumerate(blocks):
        if int(existing.network_address) > key:
            blocks.insert(index, block)
            return
    blocks.append(block)


def _take(free: list[Network], prefixlen: int) -> Network | None:
    for index, block in enumerate(free):
        if block.prefixlen <= prefixlen:
            del free[index]
            while block.prefixlen < prefixlen:
                left, right = block.subnets(1)
                _insert_sorted(free, right)
                block = left
            return block
    return None


def parse_requests(spec: str) -> list[int]:
    """Parse ``24:8,26:4`` or ``24x8`` into an expanded prefix-length list."""
    prefixes: list[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        separator = ":" if ":" in chunk else "x" if "x" in chunk.lower() else None
        if not separator:
            prefixes.append(int(chunk))
            continue
        left, right = chunk.lower().split(separator, 1)
        prefixes.extend([int(left)] * int(right))
    return prefixes


def allocate(parent: Network, used: Iterable[Block], prefixes: Sequence[int]) -> list[Allocation]:
    free = free_blocks(parent, used)
    allocations: list[Allocation] = []
    for prefixlen in prefixes:
        if not parent.prefixlen <= prefixlen <= parent.max_prefixlen:
            raise PlanError(f"prefix /{prefixlen} cannot be cut from {parent}")
        block = _take(free, prefixlen)
        if block is None:
            raise PlanError(f"no free /{prefixlen} remains inside {parent}")
        allocations.append(Allocation(f"net-{len(allocations) + 1}", str(block)))
    return allocations


def render_text(analysis: Analysis) -> str:
    lines = ["cidrmesh plan", "=" * 46]
    lines.append(f"parent: {analysis.parent or '<none>'}")
    if analysis.total_addresses is not None:
        lines.append(
            f"utilization: {analysis.used_addresses}/{analysis.total_addresses} "
            f"addresses ({analysis.utilization:.2%})"
        )
    if not analysis.findings:
        lines.append("conflicts: none")
    else:
        lines.append(f"conflicts: {len(analysis.findings)}")
        for finding in analysis.findings:
            lines.append(f"  [{finding.severity.upper():6}] {finding.kind:15} {finding.detail}")
    if analysis.free:
        lines.append("largest free blocks:")
        lines.extend(f"  {cidr}" for cidr in analysis.free)
    return "\n".join(lines)


def render_json(analysis: Analysis) -> str:
    return json.dumps(analysis.to_dict(), indent=2)


def at_or_above(findings: Sequence[Finding], threshold: str) -> list[Finding]:
    if threshold == "none":
        return []
    limit = SEVERITY_ORDER[threshold]
    return [f for f in findings if SEVERITY_ORDER[f.severity] >= limit]
