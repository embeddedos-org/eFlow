# eFlow flow format (reference for eflow-validate)

The agent-facing contract for flow documents. The CLI
(`python -m eflow validate`) checks both layers.

## Document shape (schema/eflow-flow.schema.json)

A flow is a JSON object with exactly these keys (`additionalProperties:
false` — extras are rejected):

- `flow`: non-empty string, the flow name (kebab-case, unique per project).
- `version`: integer, must be `1` (the only version the interpreter loads).
- `nodes`: non-empty array of node objects.
- `edges`: array of edge objects.

Node object (no extra keys):

- `id`: non-empty string, unique within the flow.
- `type`: dotted capability path `<domain>.<kind>`, matching
  `^[a-z]+\.[a-z0-9_]+$`. Domains: `sensor`, `filter`, `actuator`,
  `logic`, `net`, `debug` (new domains need a maintainer's sign-off).
- `params`: optional object of node-type-specific plain JSON values.

Edge object (no extra keys):

- `from`: `<node-id>:<out-port>` (matches `^[^:]+:[^:]+$`).
- `to`: `<node-id>:<in-port>`.

## Semantic rules (eflow/interpreter.py `load()`)

- Every node `type` must be in the interpreter's `REGISTRY` (current
  v1 set: `sensor.tmp117`, `filter.moving_avg`, `logic.threshold`,
  `actuator.pwm_fan`, `actuator.gpio_led`, `debug.console`).
- Edge ports must exist on the referenced nodes, with the right
  direction (`from` = out-port, `to` = in-port).
- Port types must be compatible: identical types, or int↔float; `any`
  connects to anything but emits a warning (type safety is weakened).
  bool→float (and any other non-numeric mismatch) is rejected.
- Every input port must be driven by exactly one edge; unconnected
  inputs are rejected.
- The graph must be acyclic; the error names the nodes in the cycle.

Port types (v1): `float`, `int`, `bool`, `string`, `bytes`, `any`.
