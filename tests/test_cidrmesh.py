import ipaddress
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from cidrmesh import (
    PlanError,
    allocate,
    analyze,
    at_or_above,
    find_conflicts,
    free_blocks,
    load_blocks_file,
    parse_blocks,
    parse_plan,
    parse_requests,
    render_json,
    render_text,
    utilization,
)
from cidrmesh.cli import main

PARENT = ipaddress.ip_network("10.0.0.0/24")


def nets(*cidrs):
    return parse_blocks(list(cidrs))


def test_parse_blocks_and_plan():
    blocks = parse_blocks([{"cidr": "10.0.0.0/24", "label": "web"}, "10.0.1.0/24"])
    assert blocks[0].label == "web" and blocks[1].cidr == "10.0.1.0/24"
    parent, from_plan = parse_plan({"parent": "10.0.0.0/16", "blocks": [{"cidr": "10.0.0.0/24"}]})
    assert str(parent) == "10.0.0.0/16" and len(from_plan) == 1
    with pytest.raises(PlanError):
        parse_blocks([{"label": "no cidr"}])


def test_conflicts_duplicate_and_containment():
    findings = find_conflicts(nets("10.0.0.0/24", "10.0.0.0/24", "10.0.0.128/25"))
    kinds = [f.kind for f in findings]
    assert kinds.count("duplicate") == 1
    assert kinds.count("contained") == 2  # /25 inside each /24
    assert all(f.severity in {"low", "medium"} for f in findings)


def test_disjoint_blocks_have_no_conflicts():
    assert find_conflicts(nets("10.0.0.0/25", "10.0.0.128/25")) == []


def test_free_blocks_and_utilization():
    used = nets("10.0.0.0/26")
    free = [str(n) for n in free_blocks(PARENT, used)]
    assert free == ["10.0.0.64/26", "10.0.0.128/25"]
    total, used_count, ratio = utilization(PARENT, used)
    assert total == 256 and used_count == 64 and ratio == 0.25


def test_free_blocks_ignore_outside_and_overlaps():
    used = nets("10.0.0.0/26", "10.0.0.32/27", "192.168.0.0/24")
    free = [str(n) for n in free_blocks(PARENT, used)]
    assert free == ["10.0.0.64/26", "10.0.0.128/25"]


def test_analyze_reports_outside_parent_and_utilization():
    analysis = analyze(PARENT, nets("10.0.0.0/25", "10.9.9.0/24"))
    kinds = {f.kind for f in analysis.findings}
    assert "outside-parent" in kinds
    outside = next(f for f in analysis.findings if f.kind == "outside-parent")
    assert outside.severity == "high"
    assert analysis.utilization == 0.5
    assert analysis.total_addresses == 256
    assert "largest free blocks" in render_text(analysis)


def test_allocate_first_fit():
    used = nets("10.0.0.0/26")
    allocations = allocate(PARENT, used, parse_requests("26:2"))
    assert [a.cidr for a in allocations] == ["10.0.0.64/26", "10.0.0.128/26"]
    assert allocations[0].label == "net-1"


def test_allocate_failure_and_invalid_prefix():
    with pytest.raises(PlanError):
        allocate(PARENT, [], parse_requests("23:1"))
    with pytest.raises(PlanError):
        allocate(PARENT, nets("10.0.0.0/24"), parse_requests("26:1"))


def test_parse_requests_formats():
    assert parse_requests("24:3,26x2,28") == [24, 24, 24, 26, 26, 28]


def test_ipv6_supported():
    parent = ipaddress.ip_network("2001:db8::/120")
    used = parse_blocks(["2001:db8::/121"])
    free = [str(n) for n in free_blocks(parent, used)]
    assert free == ["2001:db8::80/121"]


def test_cli_check_free_allocate(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({
        "parent": "10.0.0.0/24",
        "blocks": [{"cidr": "10.0.0.0/25", "label": "web"}, {"cidr": "10.0.0.0/25", "label": "web2"}],
    }), encoding="utf-8")
    assert main(["check", str(plan), "--fail-on", "low"]) == 1
    assert main(["check", str(plan)]) == 0  # duplicate is low, default fail-on medium
    assert main(["check", str(plan), "--json"]) == 0

    assert main(["free", "--parent", "10.0.0.0/24", "--used", str(plan)]) == 0
    assert main(["free", "--parent", "10.0.0.0/24", "--used", str(plan), "--json"]) == 0
    assert main(["allocate", "--parent", "10.0.0.0/24", "--used", str(plan), "--need", "26:2"]) == 0
    assert main(["allocate", "--parent", "10.0.0.0/24", "--need", "23:1"]) == 2

    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert main(["check", str(bad)]) == 2


def test_load_blocks_file_plain_lines(tmp_path):
    path = tmp_path / "used.txt"
    path.write_text("# comment\nweb, 10.0.0.0/26\n10.0.0.128/25\n", encoding="utf-8")
    blocks = load_blocks_file(str(path))
    assert len(blocks) == 2
    assert blocks[0].label == "web"
