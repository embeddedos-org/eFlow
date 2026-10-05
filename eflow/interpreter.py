# SPDX-License-Identifier: MIT
"""Host-side dataflow interpreter (prototype v1).

Implements the graph model from docs/dataflow-design.md:

- ``load(flow)`` validates node ids, node types, ports, edge types, and
  acyclicity, then returns ``(nodes, edges, order)``.
- ``tick(...)`` steps every node once, in topological order.
- ``run_flow(flow, ticks)`` drives a whole simulation and returns the sink log.

Deterministic: the same graph + the same tick count always produce the
same outputs, so EoSim can replay flows tick-for-tick.
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

FLOW_VERSION = 1

# Port types (v1): float, int, bool, string, bytes, any.
_NUMERIC = {"int", "float"}


class FlowError(ValueError):
    """Raised when a flow document is invalid (bad ports, types, or a cycle)."""


@dataclass
class Port:
    name: str
    ptype: str
    direction: str  # "in" | "out"


@dataclass
class NodeSpec:
    """A node type's static shape: its ports."""

    ntype: str
    inputs: Dict[str, str] = field(default_factory=dict)  # port -> ptype
    outputs: Dict[str, str] = field(default_factory=dict)


# Seed registry from docs/dataflow-design.md.
REGISTRY: Dict[str, NodeSpec] = {
    "sensor.tmp117": NodeSpec("sensor.tmp117", {}, {"out": "float"}),
    "filter.moving_avg": NodeSpec(
        "filter.moving_avg", {"in": "float"}, {"out": "float"}),
    "logic.threshold": NodeSpec(
        "logic.threshold", {"in": "float"}, {"out": "bool"}),
    "actuator.pwm_fan": NodeSpec("actuator.pwm_fan", {"duty": "float"}, {}),
    "actuator.gpio_led": NodeSpec("actuator.gpio_led", {"on": "bool"}, {}),
    "debug.console": NodeSpec("debug.console", {"in": "any"}, {}),
}


def _types_compatible(src: str, dst: str) -> bool:
    if src == dst:
        return True
    if src in _NUMERIC and dst in _NUMERIC:
        return True  # int -> float and float -> int are numeric
    if src == "any" or dst == "any":
        warnings.warn(
            f"'any' port in edge ({src} -> {dst}); type safety is weakened",
            stacklevel=4,
        )
        return True
    return False


class _Node:
    """A live node instance: params + per-tick private state."""

    def __init__(self, node_id: str, spec: NodeSpec, params: Dict[str, Any]):
        self.id = node_id
        self.spec = spec
        self.params = params
        self._window: deque = deque(maxlen=params.get("window", 8))
        self._last_bool = False

    def step(self, inputs: Dict[str, Any], tick: int,
             log: Dict[str, List[Any]]) -> Dict[str, Any]:
        ntype = self.spec.ntype
        if ntype == "sensor.tmp117":
            # Host simulation of the TMP117: deterministic slow thermal wave.
            # On target this node is replaced by the I2C driver read.
            value = 25.0 + 5.0 * math.sin(tick * 0.5)
            return {"out": value}
        if ntype == "filter.moving_avg":
            self._window.append(float(inputs["in"]))
            return {"out": sum(self._window) / len(self._window)}
        if ntype == "logic.threshold":
            level = float(self.params.get("level", 25.0))
            hyst = float(self.params.get("hysteresis", 1.0))
            v = float(inputs["in"])
            if v > level + hyst / 2:
                self._last_bool = True
            elif v < level - hyst / 2:
                self._last_bool = False
            return {"out": self._last_bool}
        if ntype == "actuator.pwm_fan":
            log.setdefault("pwm_fan", []).append(
                (self.params.get("pin"), float(inputs["duty"])))
            return {}
        if ntype == "actuator.gpio_led":
            log.setdefault("gpio_led", []).append(
                (self.params.get("pin"), bool(inputs["on"])))
            return {}
        if ntype == "debug.console":
            log.setdefault("console", []).append(inputs["in"])
            return {}
        raise FlowError(f"no step() for node type {ntype!r}")  # pragma: no cover


def _parse_port(ref: str, node_id: str, nodes: Dict[str, _Node],
                direction: str) -> Tuple[str, str]:
    """Split '<node-id>:<port>' and validate the node and port exist."""
    if ":" not in ref:
        raise FlowError(f"edge on {node_id}: malformed port ref {ref!r}")
    nid, port = ref.split(":", 1)
    if nid not in nodes:
        raise FlowError(f"edge on {node_id}: unknown node {nid!r}")
    ports = (nodes[nid].spec.inputs if direction == "in"
             else nodes[nid].spec.outputs)
    if port not in ports:
        raise FlowError(
            f"edge on {node_id}: node {nid!r} has no {direction} port {port!r}")
    return nid, port


def load(flow: Dict[str, Any]) -> Tuple[Dict[str, _Node], List[Tuple[str, str, str, str]], List[str]]:
    """Validate a flow document; return (nodes, edges, topo order).

    Edges are (src_id, src_port, dst_id, dst_port). Raises FlowError on
    duplicate ids, unknown types, bad ports, type mismatches, or cycles
    (the cycle path is included in the message).
    """
    if flow.get("version") != FLOW_VERSION:
        raise FlowError(
            f"unsupported flow version {flow.get('version')!r} "
            f"(interpreter supports {FLOW_VERSION})")

    nodes: Dict[str, _Node] = {}
    for n in flow.get("nodes", []):
        nid = n["id"]
        if nid in nodes:
            raise FlowError(f"duplicate node id {nid!r}")
        spec = REGISTRY.get(n.get("type"))
        if spec is None:
            raise FlowError(f"node {nid!r}: unknown type {n.get('type')!r}")
        nodes[nid] = _Node(nid, spec, n.get("params", {}))

    edges: List[Tuple[str, str, str, str]] = []
    for e in flow.get("edges", []):
        src_id, src_port = _parse_port(e["from"], "edge", nodes, "out")
        dst_id, dst_port = _parse_port(e["to"], "edge", nodes, "in")
        stype = nodes[src_id].spec.outputs[src_port]
        dtype = nodes[dst_id].spec.inputs[dst_port]
        if not _types_compatible(stype, dtype):
            raise FlowError(
                f"edge {e['from']!r} -> {e['to']!r}: "
                f"type mismatch ({stype} -> {dtype})")
        edges.append((src_id, src_port, dst_id, dst_port))

    order = _topo_sort(nodes, edges)

    # Every input port must be driven by exactly one edge — an unconnected
    # input is a flow authoring error, and failing at load beats a KeyError
    # mid-tick.
    driven = {(dst, dport) for _, _, dst, dport in edges}
    for nid, node in nodes.items():
        for port in node.spec.inputs:
            if (nid, port) not in driven:
                raise FlowError(
                    f"node {nid!r}: input port {port!r} has no incoming edge")

    return nodes, edges, order


def _topo_sort(nodes: Dict[str, _Node],
               edges: List[Tuple[str, str, str, str]]) -> List[str]:
    deps: Dict[str, set] = {nid: set() for nid in nodes}
    rdeps: Dict[str, set] = {nid: set() for nid in nodes}
    for src, _sp, dst, _dp in edges:
        deps[dst].add(src)
        rdeps[src].add(dst)
    order: List[str] = []
    ready = sorted(nid for nid, d in deps.items() if not d)
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for nxt in sorted(rdeps[nid]):
            deps[nxt].discard(nid)
            if not deps[nxt]:
                ready.append(nxt)
        ready.sort()
    if len(order) != len(nodes):
        cycle = sorted(set(nodes) - set(order))
        raise FlowError(
            f"flow has a cycle involving nodes: {', '.join(cycle)} "
            f"(dataflow graphs must be DAGs)")
    return order


def tick(nodes: Dict[str, _Node],
         edges: List[Tuple[str, str, str, str]],
         order: List[str], tick_no: int,
         log: Dict[str, List[Any]]) -> Dict[Tuple[str, str], Any]:
    """Step every node once in topological order; return port values."""
    values: Dict[Tuple[str, str], Any] = {}
    by_dst: Dict[str, List[Tuple[str, str, str]]] = {}
    for src, sport, dst, dport in edges:
        by_dst.setdefault(dst, []).append((src, sport, dport))
    for nid in order:
        inputs = {dport: values[(src, sport)]
                  for src, sport, dport in by_dst.get(nid, [])}
        outputs = nodes[nid].step(inputs, tick_no, log)
        for port, v in outputs.items():
            values[(nid, port)] = v
    return values


def run_flow(flow: Dict[str, Any], ticks: int = 20) -> Dict[str, List[Any]]:
    """Load a flow and run it for ``ticks`` ticks; return the sink log."""
    nodes, edges, order = load(flow)
    log: Dict[str, List[Any]] = {}
    for t in range(ticks):
        tick(nodes, edges, order, t, log)
    return log


def main(argv: List[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="eFlow host interpreter (v1)")
    ap.add_argument("flow", help="flow JSON file")
    ap.add_argument("--ticks", type=int, default=20)
    args = ap.parse_args(argv)
    with open(args.flow, encoding="utf-8") as f:
        flow = json.load(f)
    log = run_flow(flow, args.ticks)
    for sink, entries in log.items():
        print(f"== {sink} ({len(entries)} samples) ==")
        for e in entries[-5:]:
            print("  ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
