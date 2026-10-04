# eFlow dataflow design (draft)

> Status: design document, pre-implementation. eFlow has no code yet; this
> doc fixes the vocabulary (nodes, edges, types) so the first prototype and
> the EoStudio visual editors agree on the model.

## Goals

1. **Author embedded behavior visually** — sensor → filter → actuate
   pipelines an engineer can draw, not just write.
2. **Generate, don't interpret, on target** — the dataflow graph compiles to
   the same project shape `ebuild new` produces (C sources + build files).
   The interpreter below is a *host-side* tool for simulation and testing,
   never shipped to the device.
3. **Round-trip with EoStudio** — the JSON graph is the single source of
   truth; EoStudio's editors and the CLI compiler both read/write it.

Non-goals: a general-purpose visual language, live reprogramming of
deployed devices, replacing C for tight control loops.

## The graph model

A flow is a JSON document:

```json
{
  "flow": "blinky-with-sensor",
  "version": 1,
  "nodes": [
    {"id": "temp",   "type": "sensor.tmp117", "params": {"addr": "0x48", "rate_hz": 1}},
    {"id": "smooth", "type": "filter.moving_avg", "params": {"window": 8}},
    {"id": "fan",    "type": "actuator.pwm_fan", "params": {"pin": "PB3"}}
  ],
  "edges": [
    {"from": "temp:out",   "to": "smooth:in"},
    {"from": "smooth:out", "to": "fan:duty"}
  ]
}
```

### Nodes

- `id` — unique within the flow (string).
- `type` — dotted capability path: `<domain>.<kind>`. Domains: `sensor`,
  `filter`, `actuator`, `logic`, `net`, `debug`. New domains need an eFlow
  maintainer's sign-off so the palette stays curated.
- `params` — node-type-specific configuration, plain JSON values. Types
  validate params against the node type's schema at load.

### Edges

- `from` / `to` — `"<node-id>:<port>"`. Ports are named, typed, and
  directional (`in` / `out`).
- The graph must be a DAG for codegen. Cycles are rejected at load with the
  cycle path in the error — no silent feedback loops.
- Type rule: an edge connects ports of compatible types (numeric → numeric,
  bool → bool). `any` ports accept anything but warn.

### Port types (v1)

`float`, `int`, `bool`, `string`, `bytes`, `any`. Units are documentation,
not types, in v1 (`"unit": "celsius"` lives in params).

## Node-type registry (seed)

| Type | In | Out | Notes |
|---|---|---|---|
| `sensor.tmp117` | — | `out: float` | I2C temp sensor; params: addr, rate_hz |
| `filter.moving_avg` | `in: float` | `out: float` | params: window |
| `logic.threshold` | `in: float` | `out: bool` | params: level, hysteresis |
| `actuator.pwm_fan` | `duty: float` | — | params: pin, freq_hz |
| `actuator.gpio_led` | `on: bool` | — | params: pin |
| `debug.console` | `in: any` | — | host-only; stripped from target builds |

## Minimal interpreter sketch (host-side)

The interpreter exists so flows can be simulated and unit-tested on the
host before codegen. Pseudocode:

```
load(flow_json):
    nodes = {n.id: instantiate(n.type, n.params) for n in flow.nodes}
    edges = validate(flow.edges)          # ports exist, types compatible
    order = topological_sort(nodes, edges)  # raises on cycle, reports path
    return (nodes, edges, order)

tick(state, nodes, order, edges):
    values = {}                            # (node_id, port) -> value
    for node_id in order:
        inputs = {port: values[(src, sport)]
                  for (src, sport, dst, dport) in edges if dst == node_id}
        outputs = nodes[node_id].step(state, inputs)
        for port, v in outputs.items():
            values[(node_id, port)] = v
    return values
```

- `step()` is pure per tick: no hidden cross-tick state except what the
  node declares (e.g. the moving-average window buffer).
- Deterministic: same graph + same input sequence ⇒ same outputs. The
  simulator (EoSim) can replay flows tick-for-tick.
- Target codegen walks the same topological order and emits one C
  function per node plus a scheduler — the interpreter and the codegen
  share the ordering logic, so host simulation matches device behavior.

## Codegen contract (target)

- One `.c`/`.h` pair per node instance, named `<flow>_<node_id>.c`.
- A `flow_<name>_tick()` scheduler calling nodes in topological order.
- `debug.*` nodes are compiled out (`#ifdef EFLOW_HOST`).
- Generated code carries a header comment with the flow name, version, and
  the SHA-256 of the source JSON — traceability from binary back to graph.

## Open questions

1. Should params support expressions (e.g. `"rate_hz": "2*base"`) or stay
   literal? (Lean: literal in v1.)
2. Versioning/migration of the graph schema when node types evolve.
3. How flows compose (sub-flows as nodes) — deferred to v2.
