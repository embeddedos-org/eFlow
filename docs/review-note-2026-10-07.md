# eFlow PR #1 review note — 2026-10-07

> Review-only duty for today's daily run. eFlow#1 ("docs: eFlow is genuinely
> Planned, and the eos pointer was wrong") is **open, unmerged, by another
> contributor** — this note records findings and a verdict; it does not merge
> the PR. Author merges.

## What the PR changes

`README.md` (+62/−3): corrects the old line claiming "the code that will become
eFlow lives in `eos` today" (contradicted by the parenthetical "(not yet
started; EoStudio is the host)"). New text states: eFlow is genuinely
**Planned**; §18 of the v2.0 master design places it inside EoStudio, not eos;
the design constraint is §18.1 — eFlow draws graphs and emits component
manifests, it must not grow its own scheduler/IPC (no second runtime); three
ordered conditions before this repo earns code (manifest format merged, EoStudio
drives eBuild cleanly, a real user is blocked by the absence of a visual layer).

## Verification against `docs/dataflow-design.md`

- **Placement claim holds.** The design doc fixes the graph vocabulary (nodes,
  edges, types) as the contract shared between "the first prototype and the
  EoStudio visual editors" — consistent with the PR's "inside EoStudio, not
  eos" claim.
- **Constraint claim holds.** The design doc's goal 2 ("Generate, don't
  interpret, on target") and §18.1's "graphical environment is a client of the
  platform toolchain, never a second implementation" are the same invariant;
  the PR restates it faithfully.
- **Sequencing claim is plausible.** The manifest format did not exist until
  embeddedos-org/embeddedos-stack#20 (still in review) — the PR's "don't build
  a graph editor against an undefined format" reasoning is sound.

## Finding (stale claim — needs one edit)

The PR body asserts "there is no implementation anywhere in the platform" and
the new README text says "eFlow has no implementation anywhere in the platform
yet." **That is inaccurate for this repository:** master already ships
`eflow/interpreter.py` with `eflow/flows/*.json` examples and
`tests/test_interpreter.py` — the host-side simulation interpreter the design
doc itself describes ("a *host-side* tool for simulation and testing, never
shipped to the device"). The correct statement is narrower: *no device-side
implementation and no codegen yet; only the host-side interpreter prototype
exists.* One sentence in the README's status section needs that correction.

## Verdict

**Changes-requested (minor):** fix the "no implementation anywhere" claim to
acknowledge the existing host-side interpreter prototype (one sentence), then
merge-by-author. No factual issues beyond that; the §18 placement and
manifest-first sequencing are accurate and consistent with dataflow-design.md.

Reviewed: 2026-10-07 (Mando, daily-run review duty for Aswin).
