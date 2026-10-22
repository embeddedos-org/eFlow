# eFlow

Visual programming and dataflow authoring for EmbeddedOS, layered on EoStudio and eBuild.

**Status: Prototype.** A host-side implementation lives in this repository:
the interpreter (`eflow/interpreter.py`), the validate-before-run CLI
(`eflow/cli.py`), a servable stdio MCP server (`eflow/mcp_server.py`), the
flow JSON Schema (`schema/eflow-flow.schema.json`), example flows
(`eflow/flows/`), tests (`tests/`), and the `eflow-validate` agent skill
(`skills/eflow-validate/`). What does not exist yet is target codegen and
the EoStudio visual editors — those remain future work. eFlow does not
live in `eos`; the design host for visual authoring is
[EoStudio](https://github.com/embeddedos-org/EoStudio), and the build
target is the project shape `ebuild new` produces.

This repository is the component's home: it holds the prototype, the
issue tracker, and the decision record. It is deliberately not a mirror
of anywhere else: duplicating sources here would give the platform two
copies to keep in step, and §24 of the architecture document is explicit
that internal modules should not be promoted into separate brands until
they have stable interfaces and users.

## What eFlow owns

- Visual/dataflow authoring of embedded applications
- Generation into the same project shape `ebuild new` produces
- Round-tripping against EoStudio's editors

The host-side prototype above is implemented; target codegen is still
future work. §29 lists a full graphical IDE among the things to defer
until the CLI and VS Code workflows are excellent.

## Where the code is now

Here, in this repository — the interpreter, CLI, MCP server, schema,
example flows, tests, and skill listed in the status note above. It is
host-side only: it validates and simulates flows; it does not generate
target code yet. When the visual authoring layer starts, the host is
EoStudio (visual editors) and the output shape is `ebuild new`.

| | |
|---|---|
| Implementation | Host-side prototype (interpreter, CLI, MCP server, schema, tests, skill) |
| Design host | [EoStudio](https://github.com/embeddedos-org/EoStudio) |
| Build target shape | `ebuild new` project layout |
| Maturity | [`eos/STATUS.md`](https://github.com/embeddedos-org/eos/blob/master/STATUS.md) |
| Decision of record | [Repository taxonomy](https://github.com/embeddedos-org/eos) — §22 |

## When the visual layer moves here

The architecture document sets the shape of the remaining work:

> Visual programming inside EoStudio initially. — §22

The prototype in this repo is the CLI-side half of that plan. The
EoStudio visual editors and target codegen stay future work until the
CLI and VS Code workflows are excellent (§29).

## Reference

- Architecture & Ecosystem Design Document — §18 (Tooling / Later)
- [Repository taxonomy](https://github.com/embeddedos-org/eos) — §22
- [Organization model](https://github.com/embeddedos-org/.github) — §23

## License

MIT. See [LICENSE](LICENSE).
