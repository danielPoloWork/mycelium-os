# ADR-0133: Raise the floor off the contents, and state the corpus the budget holds for

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §4.2, NFR-3
- **Related:** [ADR-0015](0015-compile-incrementally-through-a-content-addressed-stage-cache.md)
  (the incremental compiler, and the dirty detector this amends),
  [ADR-0009](0009-adopt-build-publication-semantics.md) (mtime is an input: it becomes
  `created_at`), [ADR-0016](0016-make-snapshots-restorable.md) (restorability, which cost two
  probes a document), [ADR-0018](0018-build-the-graph-from-authored-links.md) (resolution is
  global, and re-runs every build), [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the measurement that filed this), [ADR-0132](0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md)
  (the cold build's remainder, and the discipline of profiling before touching),
  [BUG-0013](../bugs/2026/09/BUG-0013-a-link-to-a-non-document-warns-as-broken.md) (why an
  unresolved link asks the filesystem at all); spec 01 §8, spec 02 §4.2, spec 06 §Phase 1;
  D-005, D-008, D-016; roadmap 6.4, 6.19, 6.20

## Context

NFR-3 and spec 06's Phase-1 exit gate both say a single-document edit rebuilds in **< 2 s
p95**, and neither says on what corpus. Roadmap 6.4 built the reference profile and measured
the gate at the conditions its neighbours name: **2 206 ms p95 at 250 documents, 6 307 ms at
998** — linear in the corpus, not in the edit. After 6.19 removed the write path's quadratic
the number improved without being touched, to 3 945 ms at 1 000 documents, and still missed.

The item that filed this named the mechanism and called it a decision rather than a bug:
`_plan` read and digested *every* discovered file on every build — *"content truth comes from
the digest, never from metadata"* — and its own docstring called that read *"the incremental
floor"*. It also named a second whole-corpus pass, `resolve_edges` asking the filesystem
whether each unresolved link's target exists. And it offered two answers: raise the floor off
the filesystem with a metadata prefilter that falls back to the digest, or accept that the
budget is wrong and give NFR-3 the corpus size it holds for, the way NFR-2 states 10⁵ chunks.

### The measurement, taken to the decision

The floor was measured pass by pass before anything was changed, at 1 000 documents on the
machine of record, with the machine contended by a process outside this project's control (a
`find / -iname …` left running by an earlier session, which the permission model would not let
this one stop — so every absolute figure here is high and the shape is what to read):

| pass, per no-op rebuild of 1 000 documents | cost | what it was |
|---|---:|---|
| `_plan`: read and digest every file | **2 625 ms** | the named floor — 1.5 ms a read, 0.1 ms a digest |
| `resolve_graph`, with the filesystem probe | 687 ms | **3 922 `exists()` calls** for 1 963 unresolved links, 1 516 distinct paths; 114 ms without them |
| `store`, of which restorability | 608 ms, of which **376 ms** | **two `exists()` per live document** — more than reading the whole store (69 ms) |
| `discover` | 485 ms | `rglob("*.md")` over ten directories |
| `symbols` | 250 ms | resolution over every document's state, for 33 symbols |
| encoding the snapshot's restore state | 213 ms | a Python walk over 2.4 MB of canonical JSON |
| **total** | **4 890 ms** | of which 77 ms was deciding what was dirty |

Two things this table settled. **The named floor was half the floor**: the read was 54 % of a
no-op rebuild, and four other passes the item did not name — three of them filesystem probes,
one of them discovery — were most of the rest. And **none of it was the edit**: the one-edit
rebuild cost 5 563 ms, of which the edited document's own chain was about 190 ms. NFR-3's
budget was being spent on the corpus, at roughly 4.9 ms a document, before any document was
compiled.

### What the read was protecting

ADR-0015 chose the read over an mtime shortcut for three reasons, and they deserve to be
weighed against what a stat memo actually gives up. *Renames preserve mtimes* — true, and a
rename is a path change: the new path has no `doc_state` row and is read, the old one is gone
and is removed, and a memo keyed by path never sees a rename at all. *Pinned-mtime trees defeat
it* — the determinism gate pins every mtime to one constant, and a memo keyed by size **and**
mtime is defeated only by an edit that keeps the size, which the gate's fixture mutations do
not; and G6 builds a fresh workspace with no rows to trust. *A false "clean" is the one failure
a determinism product cannot afford* — the real argument, and the one this record answers with
guards rather than with a read: the case a size-and-mtime memo cannot see is a same-size edit
that also restores the file's previous mtime, and that case is either racy (an edit within the
filesystem clock's tick of the previous read) or deliberate (`touch -r`, a tool preserving
timestamps). Git's index, make, ninja and cargo all rest on the same memo; Git closes the racy
half with a rule it calls *racily clean* and leaves the deliberate half to the user.

## Decision

**The floor moves off the contents.** `doc_state` records, beside a document's digest, the
size and mtime the file had when the digest was computed — a **stat memo**. On the next build a
file whose size and mtime match keeps that digest without being read; the digest remains the
only identity anything downstream compares, and every stage, cache key, artifact and gate
downstream of the plan step is untouched. Content truth still comes from the digest; what
changed is how the digest is *obtained*. The store version bumps v7 → v8 for the two columns
(rebuild is the migration, D-016), and the memo travels in the snapshot's restore state so a
rolled-back snapshot trusts what the build it restores trusted.

**Three guards bound the case the memo cannot see, and each is a test.** *The racy window*: a
file whose mtime falls within two seconds of the previous build's start is read regardless,
because a coarse filesystem clock — FAT keeps two-second mtimes — can give a later edit the
timestamp the memo recorded; the previous build's start is kept in the store's `meta`, not in
the restore blob, because a wall-clock reading there would make two builds of one unchanged
corpus address two blobs. *`mycelium build --rescan`*: reads and digests every document once
at the old floor and no more, every cache still applying — the operator's way to distrust the
memo, distinct from `--clean`, which distrusts everything. *`mycelium doctor`*: re-digests
every indexed document on demand and names the ones whose bytes no longer match the index
under an unchanged size and mtime, with `--rescan` as the remedy — the old floor, paid where a
person asked for a diagnosis rather than inside every build. A document edited normally since
the last build has a different size or mtime and is counted as pending, not drift.

**The other whole-corpus passes are taken off the filesystem too, because the measurement said
they were most of what remained.** Restorability is answered from one listing per cache shard
(`cas_inventory`, 256 `scandir` calls whatever the corpus size) instead of two `exists()` per
document. An unresolved link's existence probe is answered from one listing per *directory*
for the whole resolution (`_DirectoryProbe`), so a directory that fifteen hundred candidates
fall into is read once and not fifteen hundred times, and the probe compares names the way the
filesystem does. Discovery walks the scope with `scandir` and never enters a directory the
corpus rules exclude, where `rglob` walked `.git/` and `.venv/` to reject their files one by
one. A reused document's state row is reused as it stands rather than decoded into the build's
entry and encoded back, and the snapshot's restore state is written with the C encoder,
byte-identical to the canonical form it replaces and pinned so by a test.

**NFR-3 gains the conditions it never had.** The budget now reads: a single-document edit
rebuilds in < 2 s p95 **on the 1 000-document reference corpus, on local reference hardware**
— the same corpus spec 01 §8's cold-build budget names — and its floor is one metadata read
per discovered document, never a content read of an unchanged one. The curve above that size
is *published* in the report rather than promised, because what remains is honestly O(corpus):
a `stat` a document, a row a document, a state entry a document. A budget with no corpus size
is met or missed by machine, not by design, and stating the size is what makes the number a
gate rather than a hope — the argument ADR-0120 made for NFR-2, applied to its neighbour.

**What was measured after, on the same corpus and the same contended machine** (the report
carries the full curve and the manifest):

| 1 000 documents, end to end | before | after |
|---|---:|---:|
| no-op rebuild, p50 | 5 110 ms | **1 565 ms** |
| one-edit rebuild, p50 (worst of five) | 5 776 ms (9 364) | **1 719 ms** (1 811) |
| documents read per rebuild | 1 000 | **0**, or the edited one |
| `plan` stage (`stat`, the rows, the memo) | 2 625 ms | **343 ms** |
| `graph` stage | 687 ms | **264 ms** |
| restorability, inside `store` | 376 ms | **74 ms** |
| `discover` stage | 485 ms | **93 ms** |
| restore-state encoding, inside `store` | 213 ms | **82 ms** |
| `symbols` stage | 250 ms | 235 ms — untouched, see below |

## Alternatives Considered

- **Restate the budget and change nothing.** The item's second answer, and rejected on the
  table above: a floor of 4.9 ms a document meets 2 s only below ~400 documents on this
  machine, which would have made NFR-3 a statement about small corpora. The budget *is*
  restated — but at the size the cold-build budget already names, which the floor now meets.
- **A memo on mtime alone.** Rejected — it is the shortcut ADR-0015 refused, and the refusal
  stands for mtime alone: a same-tick edit is indistinguishable. Size joins the key, and the
  racy window covers the tick.
- **Include `ctime` or the inode in the memo, as Git does.** Considered and not done. On
  Windows `st_ctime` is creation time until a future Python changes it, and `DirEntry.stat`
  leaves `st_ino` zero there, so the extra fields would guard on one platform and not the
  other while the tests could not tell. Size, mtime and the racy window are what every platform
  gives the same way.
- **Record the racy-window clock per row, or in the restore blob.** Per row would be exact
  and would rewrite a row on every trusted build; in the blob it would make two builds of one
  unchanged corpus address different blobs, breaking the property `record_snapshot_state`
  exists for. One `meta` value — the previous build's start — is sufficient (a file modified
  after any earlier build's read is either seen by the next build's stat or lands in its
  window) and costs nothing.
- **Walk the whole repository once and answer every link probe from the set.** Rejected: a
  link may legitimately name `.github/PULL_REQUEST_TEMPLATE.md` or a file in an excluded
  directory (BUG-0013's own cases), so the walk could not prune, and walking `.venv/` to
  answer a link question is worse than the probes were. Listing the directories the candidates
  actually fall into gives the same answers for the cost of a handful of `scandir` calls.
- **Make edge and symbol publication incremental — diff the tables instead of rewriting them.**
  Measured and left alone: rewriting the edge table cost 0.5 ms and the symbol table 5.8 ms at
  this corpus size. The `symbols` stage's 235 ms is not the table write either. The profile of
  what remains attributes it to `symbol_edges`: some 20 000 symbol *uses* decoded from every
  document's state, and ~3 500 `references` edges each given an identity — a canonical-JSON
  digest computed once to key the edge and once more when the store writes it. That is
  content-proportional Python work with two obvious economies (decode once, hash once), and it
  is filed as roadmap 6.32 rather than fixed here, on the 6.19 discipline: the profile was
  taken after this item's change and nothing it found is touched in the same pull request.
  ADR-0018's reason for global republication stands regardless.
- **Keep `--clean` as the only escape hatch.** Rejected: `--clean` recompiles everything, 92 s
  at 1 000 documents on an idle machine, for a doubt that a 1.5 s read answers. A distinct
  intent deserves a distinct flag, and the doctor's remedy has to be one an operator will run.
- **Let watch mode be where reads are skipped, as ADR-0015 suggested.** Rejected as
  insufficient: a watcher knows which files changed, but every `mycelium build` a person types
  does not, and NFR-3 is a claim about that build.

## Consequences

- **The incremental build reads nothing it does not have to.** `BuildStats.read` reports how
  many documents were read; on an unchanged corpus it is zero, and `mycelium build --json`
  carries it beside `rescan`.
- **A blind spot exists, is named in the code, and has a detector and a remedy.** A same-size
  edit under a restored old mtime is not seen until `--rescan`, `--clean`, or the next change to
  the file. `tests/test_build_floor.py` pins the blind spot itself, so narrowing or widening it
  is a decision somebody takes rather than a diff nobody read.
- **`SCHEMA_VERSION` bumps to v8**; every existing store rebuilds once on its next build. The
  `chunks_fts` statement is untouched, so `retrieval_identity()` and gate G2's verdict stand
  (ADR-0084), as at 6.19.
- **`tools/verify.py` derives `retrieval` for this change**, because `src/mycelium/store/` is a
  tuning path, and the ladder rebuilt every corpus under the new store version.
- **The benchmark tool measures the floor on its own.** `measure_noop` times rebuilds in which
  nothing changed, beside the edit, and both carry the compiler's per-stage medians into the
  manifest — so the next person asking where a rebuild's time goes reads it off the manifest.
- **Two specs and the gate note are amended**: NFR-3 in spec 01 carries its conditions; spec 02
  §4.2's minimality guarantee states the floor; spec 06's Phase-1 note records the answer beside
  the question 6.4 left there.
- **A limit, stated twice.** Every figure in this record was taken on a machine contended by a
  process this session could not stop, so the absolute values are high and the report says so
  in its first line; the ratios and the shape — which passes vanished, which are O(corpus) —
  are what travel. And the floor that remains is O(corpus) by construction: the single-document
  edit rebuilds in **717 ms p95 at 250 documents and 1 754 ms at 1 000** — inside the budget
  at the size it now names — then 3 805 ms at 2 500 and 6 961 ms at 5 000, about 1.35 ms a
  document plus ~200 ms of publication, so the 2 s line is crossed again near **1 200
  documents** on this contended machine, where the unmodified compiler crossed it near 250.
  That crossing is exactly why the budget now names the corpus it holds for.

## References

- Spec: `.draft-specs/02-architecture.md` §4.2 (the incremental algorithm; amended);
  `.draft-specs/01-product-strategy.md` §8 and `docs/specs/01_spec_mycelium.md` NFR-3 (the
  budget; conditions added); `.draft-specs/06-roadmap-and-governance.md` §Phase 1 (the gate).
- The report: `docs/benchmarks/2026-09-19-the-floor-was-the-whole-corpus.md`, with its
  manifests — the baseline taken on the unmodified compiler and the curve taken after.
- Git's *racily clean* rule: `Documentation/technical/racy-git.txt` in the Git source tree.
- Re-runnable: `python tools/benchmark_reference_profile.py --out <dir> --scales 250,1000
  --no-reference`, and `uv run pytest tests/test_build_floor.py -q`.
