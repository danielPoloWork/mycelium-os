# ADR-0003: Adopt the flat Python src-layout (supersedes ADR-0002)

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** Maintainer (owner decision D-024, 2026-07-31; scaffold confirmation 2026-08-29)
- **Related:** ADR-0002, [RFC-0001](../rfc/0001-mycelium-os-v1.md) (cross-cutting fold), decision log D-024 (`.draft-specs/00-verdict-and-decisions.md`)

## Context

ADR-0002 adopts the series-normative Maven-style tree
(`src/main/python/<group>/<slug>/`) and explicitly rejects "the language's default flat
layout". This project carries a prior, owner-level decision that conflicts with it:
**D-024 — one name everywhere** — fixes the import package as a flat top-level
`mycelium` (PyPI distribution `mycelium-os`, binary `mycelium`, entry-point group
`mycelium.plugins`), and forbids shipping two names. A nested
`src/main/python/mycelium/mycelium` path would surface a doubled identity exactly where
every contributor looks first, and Python packaging tooling (`uv`, `hatch`, editable
installs, entry points) is built around the src-layout convention `src/<package>/`.

In the EADOS precedence order, a recorded human decision outranks a template convention.
RFC-0001 (cross-cutting fold) already flagged this ADR as required scaffold-time work.

## Decision

Adopt the **flat Python src-layout**:

```text
src/mycelium/    # production sources — the one importable package (D-024)
tests/           # test sources (pytest convention)
tests/bench/     # benchmarks (pytest-benchmark; profile command already targets this path)
```

- The version constant lives at `src/mycelium/__about__.py` (seeded by roadmap item 1.5).
- Subdivision inside `src/mycelium/` remains **by component**, not by file type —
  ADR-0002's internal-structure rule survives; only the root shape changes.
- `tools/consistency_lint.py` `CONFIG` (`src_main`, `version_file`) and every governance
  document reference these paths.

## Alternatives Considered

- **Keep ADR-0002's normative tree.** Rejected — it contradicts D-024 (a recorded owner
  decision, higher precedence), doubles the name in every path, and forces a packaging
  shim for no benefit a single-language project can collect.
- **Hybrid (`src/main/python/mycelium/`, dropping the slug level).** Rejected — satisfies
  neither convention: still alien to Python tooling, still divergent from the series
  shape, and unique to this repo (the worst of both).

## Consequences

- Python tooling works with zero shims: `[tool.hatch]`/`uv` defaults, `mypy --strict src`,
  entry points, editable installs all see `src/mycelium` natively.
- The repository diverges from the PBR-series normative shape. The cost is deliberate and
  recorded here; a future EADOS profile knob for flat-package languages would let the
  factory express this without a superseding ADR (lesson drafted for the factory's
  ledger).
- ADR-0002 is **superseded** for the tree shape; its component-subdivision rule and its
  rationale for cross-project consistency remain the reference for everything else.

## References

- D-024 (naming, one-name-everywhere), `.draft-specs/00-verdict-and-decisions.md` §3
- RFC-0001 §Cross-cutting (namespace deviation), `docs/rfc/0001-mycelium-os-v1.md`
- AGENTS.md §5 (updated in the same change)
