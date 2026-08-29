# ADR-0004: Seed language profiles for C, C#, VB.NET, JavaScript, PHP, and Lua

## Status

Accepted

## Context

EADOS is open to any language: a profile can be authored on demand from
[`_template.yaml`](../../orchestrator/profiles/_template.yaml). The six original seeds (C++,
Python, Java, Go, Rust, TypeScript) covered systems, data, JVM, cloud, and web-frontend work,
but a maintainer's standard toolbox also includes C, C#, VB.NET, JavaScript, PHP, and Lua.
Authoring those on demand every time is friction and risks per-project inconsistency for
languages used repeatedly.

The maintainer also listed SQL, CSS, and HTML. These are **supporting technologies**, not
primary application languages: EADOS's project model (build/test/lint, a version constant, a
namespaced source tree) does not map onto them, and forcing primary profiles would produce
awkward, low-value artifacts.

## Decision

Ship six additional, schema-complete seed profiles — `c`, `csharp`, `vbnet`, `javascript`,
`php`, `lua` — each binding the language's de-facto enterprise toolchain (build, test, format,
lint, coverage, docs, sanitizer/race, packaging) and verified by the render-smoke (a manifest
for the language renders a repo whose `consistency_lint` and `self_review` pass).

Do **not** ship primary profiles for SQL, CSS, or HTML. Treat them as **secondary components**
declared within a project (the SQL schema a backend owns; the HTML/CSS of a frontend). The
[language-fit advisory](../../orchestrator/language-fit.md) records this stance.

## Consequences

- Twelve languages generate with zero authoring friction; the rest remain on-demand.
- Each seed joins the stay-current maintenance surface (tool versions, runner images, action
  pins) — a known, bounded upkeep cost, the reason the stay-current routine exists.
- A mediocre seed would be worse than none, so each is held to the ground-truth bar of
  `cpp.yaml` and proven by the render-smoke before landing.
- SQL/CSS/HTML standalone artifacts (a published design-system, a SQL migration package) would
  need an adapted "project kind"; that is deferred until a concrete need arises (a future ADR).
