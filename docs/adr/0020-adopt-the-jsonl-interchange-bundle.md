# ADR-0020: Make the export bundle a verifiable claim, not a directory of files

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §9
- **Related:** [ADR-0009](0009-adopt-build-publication-semantics.md) (the commit-to-swap
  window this refuses to export through),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the ordering the manifest
  folds by), [ADR-0016](0016-make-snapshots-restorable.md) (the same
  verify-before-you-claim discipline, applied to rollback),
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the determinism this extends to the
  output format); spec 03 §9, spec 05 §1; D-005, D-006; roadmap 3.6

## Context

D-006 fixes JSONL as the **interchange** format, and is careful about what that does not
mean: not the query engine (SQLite, D-005), not the system of record (Git and the Markdown,
F-4), and "not committed by default". Spec 03 §9 draws the tree — `manifest.json`, a
`records/` directory of one JSONL file per artifact class, an optional `markdown/` copy —
and states the contract in one sentence: *"One JSONL line = one record exactly as specified
above."*

The obvious reading is a serialisation chore: iterate the store, dump JSON, done. What
makes it more than that is who the consumer is. A bundle leaves this repository and is read
by a tool that cannot ask it questions. Everything the repository knows implicitly — which
snapshot these rows belong to, whether the working tree still matches them, whether two
exports of the same corpus are comparable — is either encoded in the bundle or lost.

Three decisions follow, and each is a refusal rather than a feature.

## Decision

**A bundle names one snapshot, and contains that snapshot.** `mycelium export` reads
`CURRENT`, requires its manifest to exist, and requires the store's own
`meta[current_snapshot]` to agree with it. When they disagree — the crash window ADR-0009
documented and `doctor` reports — the export **refuses**, because the store's rows then
belong to a different build than the directory would be stamped with. A bundle labelled
snapshot A holding snapshot B's records is the class of quiet inconsistency this project
spends its effort avoiding, and here it would escape into someone else's tool.

**A bundle's bytes are a function of its snapshot.** Records are written in a declared
order — documents by path, chunks by anchor, edges by identity — serialised through
`canonical_json` (sorted keys, fixed number spelling, no insignificant whitespace) and
LF-terminated regardless of platform. Exporting the same snapshot twice produces
byte-identical files, so a bundle can be digested, cached, diffed between machines, and
compared across a release. This is gate G6's property applied to the output format, and it
costs nothing but choosing an order and using the canonicaliser the project already has.

Documents by path and chunks by anchor is not arbitrary: it is the order the snapshot
manifest folds its own corpus digests by (ADR-0015), so a consumer comparing a bundle
against the manifest it carries is comparing like with like.

**`--with-markdown` copies the sources that were compiled, or nothing.** Each file's digest
is recomputed and checked against the `content_digest` its record carries; any drift —
edited, deleted, unreadable — fails the export and names the files. The alternative, copying
whatever is on disk, produces a bundle whose records describe snapshot A and whose Markdown
is the working tree's B, with nothing in the bundle to reveal it. The fix is one
`mycelium build`, and the error message says so.

**`manifest.json` is copied byte for byte** rather than re-serialised. Spec 03 §9 says
"verbatim", the manifest is immutable and already deterministic, and copying is a stronger
promise than re-emitting faithfully.

**`symbols.jsonl` is written empty; `entities.jsonl` is absent.** Symbols are a declared
artifact class whose extraction stage arrives at 5.1 — an empty file says "this class
exists and this snapshot has none", while a missing one leaves a consumer to distinguish
"unsupported" from "empty" with no evidence. Entities are the opposite case: spec 03 §9
marks them "if present", and their stage is optional and off by default (5.4), so absence
*is* the signal that no entity stage ran.

**Bundles land in `<root>/export/<snapshot-id>/`, and `mycelium init` gitignores them.**
The path is spec 03 §9's own tree. The gitignore entry is D-006's "not committed by
default" made true: a directory the tool writes into a repository is committed by default
unless something says otherwise. `init` now appends gitignore entries individually rather
than treating the file as all-or-nothing, so a repository initialised before this item
gains `export/` on its next `init` — which is what "idempotent" was supposed to mean.

## Alternatives Considered

- **Serialise the store and stop there.** Rejected: it produces the files without the
  guarantees. Every check added here is one the consumer cannot perform for itself, because
  it needs facts — the pointer, the source digests — that stay behind in the repository.
- **Export whatever is on disk under `--with-markdown`, warning about drift.** Rejected: a
  warning printed at export time is not attached to the bundle, and the bundle is what
  travels. The inconsistency would arrive silently at the far end.
- **Skip the drifted files and export the rest.** Rejected: a `markdown/` tree quietly
  missing three documents is harder to diagnose than a refusal, and a consumer cannot tell
  it from a corpus that never had them.
- **Re-serialise the manifest into the bundle.** Rejected: "verbatim" is a promise worth
  keeping literally, and re-emitting introduces a way for the two to differ.
- **Write `entities.jsonl` empty too, for symmetry.** Rejected: the spec distinguishes the
  two cases and so should we — `symbols` is a declared class of every snapshot, `entities`
  is the output of an optional stage.
- **Default to `.mycelium/export/`**, where the gitignore already reaches. Rejected: it
  contradicts spec 03 §9's tree, and burying an artifact whose whole purpose is to be handed
  to another tool inside the derived-store directory is the wrong affordance. Two gitignore
  lines keep both properties.
- **Add a checksum file over the records.** Rejected as invention: the tree is explicit, the
  bundle is already byte-deterministic, and a consumer that wants a digest can take one.
  Worth revisiting when a consumer asks.
- **Ship `--with-vectors`.** Deferred by the spec itself ("until a consumer exists"), and
  nothing here changes that.

## Consequences

- **The bundle is checkable by its recipient**: counts can be compared against the manifest
  it carries, every line validates against its published record schema, and two exports of
  one snapshot are byte-comparable. Those are the properties that make JSONL an interchange
  format rather than a dump.
- **`export` is a read-only command over the published snapshot.** It takes no build lock —
  it reads through a read-only store handle exactly as `search` does, so it cannot block a
  build or be blocked by one. The thing it must not do, assembling a bundle while the
  pointer and the store disagree, it detects rather than locks against.
- **Re-exporting a snapshot removes the previous bundle directory first.** Records rewrite
  identically, but a `markdown/` left by an earlier `--with-markdown` run would survive
  beside records that no longer claim it.
- **`symbols.jsonl` is empty until roadmap 5.1**, while `edges.jsonl` has been populated
  since 3.4. A consumer written today against the layout keeps working as those stages
  arrive; that is the point of writing the declared classes now.
- **`init` writes two gitignore entries**, and repositories scaffolded before this item pick
  the second one up on their next `init`. No existing line is ever rewritten.
- **Gate G6 is untouched, and that is the evidence** that export is a pure reader: it adds
  no stage, changes no digest, and the golden did not move.

## References

- Spec: `.draft-specs/03-data-model.md` §9 (the bundle tree and the one-line-one-record
  contract); `.draft-specs/05-interfaces-and-plugins.md` §1 (`mycelium export`)
- Decision log: D-005 (SQLite is the query engine), D-006 (JSONL is interchange — not the
  engine, not committed by default)
- Tests: `tests/test_export.py`
