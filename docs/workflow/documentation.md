# Documentation Workflow

How documentation is maintained on `mycelium-os`. Documentation is part of the
deliverable — every PR ships its own doc updates in the same PR. The rules are in
[`AGENTS.md`](../../AGENTS.md) §7; this expands the *how*.

## Artifacts and when to touch them

| Artifact | Update it when… |
|---|---|
| `README.md` | the public surface, build/test/run flow, or milestone status changes |
| `docs/specs/` | behavior diverges from the frozen spec (update spec **or** add a superseding ADR) |
| `docs/adr/` | a non-trivial design decision is made, or a pattern is adopted/superseded |
| `docs/patterns/README.md` | a pattern is introduced, refined, rejected, or superseded |
| `ROADMAP.md` | an item completes (flip the checkbox) or new work is planned |
| `CHANGELOG.md` | a user-visible change lands (add a line to `[Unreleased]`) |
| `docs/journal/` | a work session changed the project's state (dated checkpoint) |
| `docs/bugs/` | a defect is verified, triaged, or fixed |
| `docs/i18n/translation-status.md` | a translated page is added, updated, or its English source moves |

## Same-PR discipline

A change to code and its documentation belong to the **same** pull request. "Docs
follow-up" is not allowed (`AGENTS.md` §10). The consistency lint
(`python tools/consistency_lint.py`) mechanically enforces the parts of this that can be
checked: version lockstep, ADR index ↔ files, pattern rows ↔ ADR+code, spec coverage map,
README ↔ ROADMAP milestone agreement, and bug-ledger integrity.

## Translations (D-028)

English is canonical and keeps its canonical paths. A translation is a **derived copy**
under `docs/i18n/<code>/` mirroring the source path — it never replaces or edits its
English source. Targets are `it`, `zh-Hans`, `ja`.

Two rules make this safe rather than decorative:

1. **Translate after, never instead.** A PR changes the English page; the translation
   follows in that PR or a later one. Blocking an English change on its translations would
   make the canonical source hostage to the derived ones.
2. **Freshness is gated.** Each `translated` row in
   [`docs/i18n/translation-status.md`](../i18n/translation-status.md) records the English
   source's commit SHA, and the consistency lint fails when the source has moved on. A
   silently drifting translation is worse than a missing one — a reader trusts it.

Which pages are tracked, why the rest are not, and the step-by-step procedure:
[`docs/i18n/README.md`](../i18n/README.md).

## API documentation

Public symbols are documented with `mkdocs-material (or Sphinx for API-heavy libs)`-compatible comments. The API-docs build
must be warning-free (quality bar, `AGENTS.md` §10). Narrative documentation lives in
Markdown under `docs/`; the split between generated API docs and hand-written narrative is
recorded in an ADR if non-obvious.
