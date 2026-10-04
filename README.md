# eFlow

Visual programming and dataflow authoring for EmbeddedOS, layered on EoStudio and eBuild.

**Status: Planned.** There is no implementation in this repository yet — and
there is none anywhere else either. eFlow does not live in `eos` today; the
design host for visual authoring is [EoStudio](https://github.com/embeddedos-org/EoStudio),
and the build target is the project shape `ebuild new` produces.

This repository exists so the component has a home, an issue tracker, and a
place to record decisions before any code moves. It is deliberately not a
mirror: duplicating the sources here would give the platform two copies to
keep in step, and §24 of the architecture document is explicit that internal
modules should not be promoted into separate brands until they have stable
interfaces and users.

## What eFlow owns

- Visual/dataflow authoring of embedded applications
- Generation into the same project shape `ebuild new` produces
- Round-tripping against EoStudio's editors

There is no implementation anywhere yet. §29 lists a full graphical IDE among
the things to defer until the CLI and VS Code workflows are excellent.

## Where the code is now

There is no implementation anywhere yet — not here, not in `eos`, not in
EoStudio. §29 lists a full graphical IDE among the things to defer until the
CLI and VS Code workflows are excellent. When design starts, the host is
EoStudio (visual editors) and the output shape is `ebuild new`.

| | |
|---|---|
| Implementation | None yet (planned) |
| Design host | [EoStudio](https://github.com/embeddedos-org/EoStudio) |
| Build target shape | `ebuild new` project layout |
| Maturity | [`eos/STATUS.md`](https://github.com/embeddedos-org/eos/blob/master/STATUS.md) |
| Decision of record | [Repository taxonomy](https://github.com/embeddedos-org/eos) — §22 |

## When code moves here

The architecture document sets one condition, and it has not been met:

> Visual programming inside EoStudio initially. — §22

Until then, design work on eFlow happens here, in this repo's docs. Opening
the code split earlier would cost a release cycle, a CI pipeline and a
versioning story for a component whose interface is still changing.

## Reference

- Architecture & Ecosystem Design Document — §18 (Tooling / Later)
- [Repository taxonomy](https://github.com/embeddedos-org/eos) — §22
- [Organization model](https://github.com/embeddedos-org/.github) — §23

## License

MIT. See [LICENSE](LICENSE).
