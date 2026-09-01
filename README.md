# eFlow

Visual programming and dataflow authoring for EmbeddedOS, layered on EoStudio and eBuild.

**Status: Planned**, and correctly so — unlike its sibling placeholder
repositories, eFlow has no implementation anywhere in the platform yet.

The pointer at `eos` in the previous version of this file was wrong. eFlow is not
kernel-adjacent and no part of it belongs there. §18 of the v2.0 master design
places it inside EoStudio:

```
EmbeddedOS Studio
  |-- Project / Board Config
  |-- Code / Debug / Trace
  |-- eFlow visual design
  |-- eAI model tools
  `-- EoSim integration
```

## What eFlow is, and what it must not become

> §18.1: eFlow should generate/configure standard EmbeddedOS components and
> manifests; it should not create an incompatible second runtime.

That is the whole design constraint. eFlow draws a graph —

```
[Camera] -> [Object Detection] -> [Decision] -> [GPIO/Motor]
```

— and emits component manifests from it. It does not execute anything. The
moment it grows its own scheduler or its own IPC, the platform has two runtimes
and every EmbeddedOS guarantee has to be re-established inside the second one.

§18 makes the same point about its host: "EoStudio should follow a stable
eBuild/SDK rather than preceding it. The graphical environment is a client of
the platform toolchain, never a second implementation."

## Why nothing is being built yet

eFlow's output is component manifests. That format did not exist until
embeddedos-org/embeddedos-stack#20, and is still in review. Building a graph
editor that emits an undefined format would mean inventing the format in the
editor — which is precisely how a second, incompatible runtime starts.

The order is: component manifest lands, the registry (§11) can resolve them,
EoStudio drives eBuild through a stable interface — and only then does a visual
layer on top have something real to generate.

EoStudio is not yet a clean client of eBuild either. It carried a 588-line second
build system with seventeen backends, none of them `ebuild`, and its single
reference to the tool was a string that was not valid CLI
(embeddedos-org/EoStudio#24, partially addressed by EoStudio#25). §18's "client
of the platform toolchain, never a second implementation" is not satisfied today.

## When this repository would earn code

Three things, in order:

1. The component manifest format is merged and stable.
2. EoStudio genuinely drives eBuild rather than reimplementing it.
3. There is a user for a visual layer who is blocked by its absence.

Until all three hold, this repository is an issue tracker and a design record. It
is deliberately not a mirror of anything.

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

| | |
|---|---|
| Implementation | [`eos`](https://github.com/embeddedos-org/eos) → `(not yet started; EoStudio is the host)` |
| Maturity | [`eos/STATUS.md`](https://github.com/embeddedos-org/eos/blob/master/STATUS.md) |
| Decision of record | [Repository taxonomy](https://github.com/embeddedos-org/eos) — §22 |

## When code moves here

The architecture document sets one condition, and it has not been met:

> Visual programming inside EoStudio initially. — §22

Until then, work on eFlow happens in `eos`. Opening the split earlier would
cost a release cycle, a CI pipeline and a versioning story for a component
whose interface is still changing.

## Reference

- Architecture & Ecosystem Design Document — §18 (Tooling / Later)
- [Repository taxonomy](https://github.com/embeddedos-org/eos) — §22
- [Organization model](https://github.com/embeddedos-org/.github) — §23

## License

MIT. See [LICENSE](LICENSE).
