"""eFlow — visual dataflow authoring for EmbeddedOS.

Host-side interpreter prototype (v1). Implements docs/dataflow-design.md:
load/validate a JSON flow, topologically order it, and tick it
deterministically. Target codegen walks the same order; the interpreter
never ships to the device.
"""
