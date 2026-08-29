# Requests for Comments (RFCs) — EADOS

Design documents for EADOS's **own** evolution (not the projects it generates — those get their
own `docs/specs/` from the templates). An RFC is the *deliberation* — context, alternatives,
schemas, diagrams, and roadmap — while an [ADR](../adr/README.md) is the immutable *decision
record* that ratifies it. Numbering is sequential and never reused.

## Index

| RFC | Title | Status | Ratified by |
|-----|-------|--------|-------------|
| [0001](0001-eados-delivery-os.md) | EADOS — the agentic delivery operating system | Accepted | [ADR-0011](../adr/0011-eados-phase-based-delivery-operating-system.md) |

## Roadmap

The delivery plan (M1 → M14, as of 2026-07-10) is the **single source of truth** in
[`ROADMAP.md`](ROADMAP.md) — living and checkbox-driven. RFC-0001 §12 points to it; it is not
duplicated here, so this line is a snapshot, not the source (`eados_lint`'s `roadmap-freshness`
gate keeps `ROADMAP.md` itself honest against the CHANGELOG).

## Diagrams

Diagrams are **code** (Mermaid) under [`assets/`](assets/README.md); GitHub renders the embedded
blocks inline. See the assets README for the SVG-generation recipe.
