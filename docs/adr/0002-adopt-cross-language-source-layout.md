# ADR-0002: Adopt the cross-language source layout

- **Status:** Superseded by [ADR-0003](0003-adopt-flat-python-src-layout.md) (2026-08-29)
- **Date:** 2026-01-01
- **Deciders:** Maintainer
- **Related:** ADR-0001, AGENTS.md §5

## Context

`mycelium-os` is one of a family of projects intended to share the same technical-
enterprise structure regardless of implementation language. Source trees vary widely by
language ecosystem (`src/`, flat package roots, `pkg/`, crate roots). Without a fixed shape,
sibling projects diverge and the agent's mental model has to be relearned per repo.

## Decision

We adopt a **Maven-style cross-language source tree**:

```text
src/main/python/mycelium/mycelium/    # production sources
src/test/python/mycelium/mycelium/    # test sources
src/bench/python/mycelium/mycelium/   # benchmarks (where applicable)
```

For this repository `<lang>` = `python` and the namespace/package is `mycelium`,
mirroring the path. Subdivision inside `mycelium/` is by **component**, not by file
type. This layout is **normative** for every sibling project; only the `<lang>` segment and
the language's native namespace idiom change.



## Alternatives Considered

- **The language's default flat layout.** Rejected — it optimizes for one ecosystem at the
  cost of cross-project consistency, which is the whole point of the series.
- **A bespoke per-project layout.** Rejected — defeats the goal of a reproducible enterprise
  structure that an agent can navigate identically everywhere.

## Consequences

- Build tooling is configured to treat `src/main/python/...` as the source root; some
  ecosystems need a small shim (e.g. a build manifest pointing at the nested path).
- The layout is enforceable: code outside the tree is a review failure, and changing the
  shape requires superseding this ADR.
- Consumers import the public surface via `from mycelium.sdk.types import KirDocument`.

## References

- AGENTS.md §5 (Source Tree & Cross-Language Layout).
