# SPDX-License-Identifier: MIT
"""Example flows must satisfy the published JSON Schema *and* the interpreter.

schema/eflow-flow.schema.json is the agent-facing contract
(validate-before-run): agents generating flows validate against it before
emitting. This test pins the repo's own example flows to both layers:

1. structural — the schema's shape rules, checked without a jsonschema
   dependency (CI installs only pytest);
2. semantic — eflow.interpreter.load(), which additionally enforces known
   node types, port directions, type compatibility, and acyclicity.
"""

import json
import re
from pathlib import Path

import pytest

from eflow.interpreter import FLOW_VERSION, FlowError, load

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "eflow-flow.schema.json"
FLOWS_DIR = Path(__file__).resolve().parent.parent / "eflow" / "flows"

TYPE_RE = re.compile(r"^[a-z]+\.[a-z0-9_]+$")
PORT_RE = re.compile(r"^[^:]+:[^:]+$")


def example_flows():
    return sorted(FLOWS_DIR.glob("*.json"))


def check_structure(flow, path):
    """The schema's structural rules, dependency-free."""
    assert isinstance(flow, dict), f"{path}: flow must be an object"
    for key in ("flow", "version", "nodes", "edges"):
        assert key in flow, f"{path}: missing required key {key!r}"
    assert isinstance(flow["flow"], str) and flow["flow"], f"{path}: flow name"
    assert flow["version"] == FLOW_VERSION, f"{path}: version must be {FLOW_VERSION}"
    assert isinstance(flow["nodes"], list) and flow["nodes"], f"{path}: nodes"
    seen = set()
    for n in flow["nodes"]:
        assert isinstance(n, dict), f"{path}: node must be an object"
        assert isinstance(n.get("id"), str) and n["id"], f"{path}: node id"
        assert n["id"] not in seen, f"{path}: duplicate node id {n['id']!r}"
        seen.add(n["id"])
        assert TYPE_RE.match(n.get("type", "")), f"{path}: bad node type {n.get('type')!r}"
        assert isinstance(n.get("params", {}), dict), f"{path}: params"
    assert isinstance(flow["edges"], list), f"{path}: edges"
    for e in flow["edges"]:
        assert isinstance(e, dict), f"{path}: edge must be an object"
        assert PORT_RE.match(e.get("from", "")), f"{path}: bad edge from {e.get('from')!r}"
        assert PORT_RE.match(e.get("to", "")), f"{path}: bad edge to {e.get('to')!r}"


def test_schema_file_is_valid_json():
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["title"] == "eFlow dataflow definition"
    assert schema["properties"]["version"]["const"] == FLOW_VERSION


def test_example_flows_exist():
    assert example_flows(), "no example flows found"


@pytest.mark.parametrize("path", [str(p) for p in example_flows()])
def test_example_flow_matches_schema_structure(path):
    flow = json.loads(Path(path).read_text())
    check_structure(flow, path)


@pytest.mark.parametrize("path", [str(p) for p in example_flows()])
def test_example_flow_loads_in_interpreter(path):
    flow = json.loads(Path(path).read_text())
    nodes, edges, order = load(flow)  # must not raise FlowError
    assert nodes and order


def test_schema_rejects_garbage():
    with pytest.raises(AssertionError):
        check_structure({"flow": "x"}, "test")
    with pytest.raises(AssertionError):
        check_structure(
            {"flow": "x", "version": 1, "nodes": [{"id": "a", "type": "bogus type!"}], "edges": []},
            "test",
        )
    with pytest.raises(FlowError):
        # filter.moving_avg has an input port with no incoming edge
        load(
            {
                "flow": "x",
                "version": 1,
                "nodes": [{"id": "s", "type": "filter.moving_avg"}],
                "edges": [],
            }
        )
