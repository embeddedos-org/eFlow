# AGENTS.md - eFlow

eFlow is the planned visual programming and dataflow authoring component for
EmbeddedOS, layered on EoStudio and eBuild. The default branch currently contains
only project documentation and a license; there is no implementation or supported
build, test, lint, or format command in this repository yet. (Provenance:
`README.md` and the inspected `master` tree.)

## Repository layout

- `README.md` - project purpose, planned ownership, status, and architecture links.
- `LICENSE` - MIT license.
- `docs/wiki/` - source-controlled copies of the six published GitHub Wiki pages.
- `.github/PULL_REQUEST_TEMPLATE.md` - repository pull request checklist.
- `.github/workflows/linked-issue.yml` - organization linked-issue policy caller.

## Development

Read `README.md` before proposing product work. eFlow is planned, and this
repository does not yet contain a runtime, package manifest, build system, test
suite, or generated artifacts. Do not invent project commands or introduce a
second runtime. Keep documentation consistent with the current architecture and
with eFlow's intended role as an authoring client layered on EoStudio and eBuild.

## Validation

For documentation and governance-only changes, run checks appropriate to the
changed files:

```bash
git diff --check
npx --yes markdownlint-cli2 AGENTS.md
npx --yes yaml-lint .github/workflows/linked-issue.yml
```

There is no repository-native build or test command on the current default
branch. Record that absence rather than claiming an unrun native test.

## Pull requests

Open a same-repository issue before opening a human-authored pull request. In the
pull request body, replace the template placeholder with a GitHub closing keyword
and that issue number, for example `Fixes #3`. Keep changes focused and explain
validation results and any pre-existing baseline blockers.

## Security

Do not report suspected vulnerabilities in a public issue. The current default
branch has no root `SECURITY.md`; use GitHub's private security advisory workflow
when available, or a private maintainer contact exposed by the organization.
