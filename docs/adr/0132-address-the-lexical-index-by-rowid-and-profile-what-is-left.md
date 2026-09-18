# ADR-0132: Address the lexical index by rowid, and profile what is left before touching it

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 01 §8
- **Related:** [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) (the store, and
  the `UNINDEXED` anchor this fixes), [BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md)
  (the defect, and the candidate list this corrects),
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (which measured it and filed it here),
  [ADR-0084](0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md) (the
  fingerprint that made this bump cheap),
  [ADR-0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) (the
  precedent: the cost everyone assumed was the arithmetic was the row-by-row read),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) (the stemmer this profile
  found), [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) and
  [ADR-0009](0009-adopt-build-publication-semantics.md) (the content-addressed writes it
  found first); spec 01 §8, spec 02 §4; D-005, D-016; roadmap 6.4, 6.19, 6.20, 6.30, 6.31

## Context

Spec 01 §8 budgets a cold build of a thousand documents at 60 s. Roadmap 6.4 measured
**193.5 s** — missed by 3.2× at exactly the size the budget is stated for — and found that
the throughput *degraded* with corpus size, 134 ms per document at 250 and 194 at 998, so it
was not a fixed per-document cost.

The superlinear term was named: [BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md).
`put_chunks` deleted each chunk's row from `chunks_fts` before inserting it; `anchor` is an
`UNINDEXED` column of an FTS5 table, which is stored and nothing more, so SQLite answers
`DELETE … WHERE anchor = ?` with a full scan of the index. Writing *N* chunks cost O(*N*²).
A thousand chunks into an empty store took 2.7 s; the thousand after nine thousand others
took 68 s. That is also why the 10⁵-chunk reference corpus NFR-2 names had never been built:
loading it through the compiler is about nine hours.

Roadmap 6.19 asks for two things, and is explicit that they are different sizes: fix the
quadratic, then **profile what is left before touching any of it** — because ADR-0026 is the
precedent where the cost everyone assumed was the vector arithmetic turned out to be reading
the vectors row by row.

## Decision

**A `chunks_fts` row carries the `rowid` of the `chunks` row it indexes, and the delete is
gone rather than made cheap.** The upsert into `chunks` returns that rowid, the index row is
written at it, and `INSERT OR REPLACE` does in one seek what a scan and an insert did in two
statements. The rowid is the one key FTS5 can seek on; the anchor never was. `delete_document`
became a single statement over a rowid subquery — `DELETE FROM chunks_fts WHERE rowid IN
(SELECT rowid FROM chunks WHERE doc_id = ?)` — instead of a per-anchor loop, which matters
because that is the path every *rebuild* takes.

Replacing rather than deleting-then-inserting is not a shortcut, it is the same guarantee
stated better: a chunk's index row *is* the row at its rowid, so a replace cannot leave the
old text behind, which is what the delete existed to prevent. FTS5's own `integrity-check`
is run against that claim in the test suite rather than assumed.

**The store version bumps and the ranking fingerprint does not, and the difference is the
point.** `SCHEMA_VERSION` goes v6 → v7 because a store written before this holds rowids that
mean nothing, so it must be rebuilt — which is what a version bump says under D-016's
rebuild policy. But no DDL changed, so `fts_schema()` is byte-identical, so
`retrieval_identity()` is byte-identical (`sha256:44bb6f6c…`, verified before and after), so
**gate G2's verdict is untouched** and nobody needs the embedding model to re-record it.
This is the first bump in the project's history that changes no schema at all, and it is the
case ADR-0084 was written for: the store version moves for every table, the fingerprint moves
only for what BM25 can see, and conflating them once cost a re-record that only one machine
could finish.

**[BUG-0031]'s candidate list is corrected where it was wrong.** It said the first two
candidates both move `retrieval_identity()`. True of the first — an external-content table
changes the DDL — and false of the second, which is the one taken. The record now says so;
the wrong sentence is kept with its correction rather than edited away, because a candidate
list that was consulted and found inaccurate is worth more than a tidy one.

**What is left was profiled before anything else was touched**, which is the half of the item
that is not a patch. `tools/benchmark_reference_profile.py --profile` runs one cold build
under `cProfile`, separately from the timed run so the published number never carries the
profiler's overhead, and records both self and cumulative time. It found that the item's own
guess was wrong. The item expected the remaining time across *"parse, chunk, tree-sitter
extraction and graph resolution"*. Measured, the graph and symbol stages are **0 %** each,
and the two real costs are:

| Cost | Share of the build | Mechanism |
|---|---|---|
| Content-addressed blob writes | **~79 s of 91.7 s** | three `cas_put` per document; each atomic write costs 26.4 ms on this machine |
| The Porter stemmer | **~7.4 s** | four stem columns per chunk, 620 k word occurrences over 10 339 distinct words |

**A deterministic profiler's shares are read as a hint and never as a measurement**, and this
run is why. cProfile charges per call, so it inflates the stemmer — 14.3 million inner calls —
and flattens the file operations, at three thousand. Taken at face value the profile says
stemming is 22 % of the build; measured on its own, unprofiled, it is 7.4 s of 91.7 s, about
8 %. Every number in the table above is from a direct measurement; the profile is what said
*where to point one*.

**Nothing found by the profile is fixed here**, which is the item's own instruction and the
rule this project has applied since 6.4 filed six items rather than six patches. They are
**6.30** (the atomic-write ceremony: a temp file, an fsync and a rename cost 13.8 ms on top
of a 12.6 ms plain write, for a store D-005 calls derived and disposable) and **6.31** (the
stemmer is a pure function called 620 000 times over 10 339 distinct words; memoised it is
23.6× faster). Each names a mechanism and a number, which is what makes it a one-sitting item
rather than an investigation.

## Alternatives Considered

- **Make `chunks_fts` an external-content table over `chunks`.** [BUG-0031]'s cheapest-first
  candidate, and rejected on inspection: external content requires the content table to hold
  the indexed columns, and four of the nine are *derived* — the three stem columns and
  `title`, which comes from `documents`. Adopting it would mean adding them to `chunks`, which
  is a real schema change, a bigger diff, and the one option that genuinely would have moved
  `retrieval_identity()` and demanded a G2 re-record on a machine with the embedding model.
- **Ask `chunks` whether the anchor exists, and delete only when it does.** The third
  candidate, and the only one that touches nothing. Rejected because it fixes the case that
  is already cheap and leaves the expensive one: on a cold build every chunk is new, so the
  existence check would skip every delete — but a *rebuild* goes through `delete_document`
  first, whose per-anchor loop it does not touch at all. It optimises the path that was about
  to stop hurting and leaves the path that keeps hurting.
- **Keep the delete and make it cheap by rowid, rather than replacing.** Two statements where
  one does, and the second is strictly weaker: a replace cannot leave a stale row, whereas a
  delete-then-insert pair can if anything ever runs between them.
- **Leave `SCHEMA_VERSION` alone, since no DDL changed.** Tempting — it would spare every
  user a rebuild — and wrong. A store written by the old writer has FTS rowids assigned by
  FTS5's own counter, which agree with `chunks` only by coincidence; the new writer would
  replace the wrong row. The bump is what makes the invariant true of every store the code
  will ever read, and the store is derived data whose rebuild is one command (D-005).
- **Fix the stemmer and the write ceremony here too, since the profile found them.** Rejected
  on the item's own words — *"before touching any of it"* — and on reviewability: this pull
  request's claim is that a quadratic is gone and the build is linear, which is checkable
  against one number. Folding in two more optimisations would make that number a sum of three
  changes, and the fsync question in particular is a durability argument that deserves its own
  page rather than a paragraph in someone else's.
- **Report the profile's percentages as the answer.** Rejected once the stemmer was measured
  on its own and came in at a third of its profiled share. A profile that is quoted rather
  than confirmed is how a project optimises the thing that was easiest to instrument.

## Consequences

- **The build is linear in corpus size, which is the property to check rather than the
  total.** 93 ms per document at 250 and 92 at 1 000, against 134 and 194 before. The cold
  build fell from **193.5 s to 91.7 s**, and the 250-document one from 33.5 s to 23.2 s.
- **The 60 s budget is still missed, by 1.5× where it was missed by 3.2×**, and the report
  says so. What is now known is that the remainder is not the compiler's algorithms: it is
  ~79 s of writing three small files per document on a machine that charges 26 ms for each.
- **The incremental rebuild improved without being touched** — 3 945 ms p95 at 1 000
  documents against 6 307 ms — and still misses NFR-3's 2 s. It is 6.20's, and its floor is a
  different mechanism (`_plan` reads and digests every file).
- **The reference corpus is compilable in principle now.** Nine hours was the quadratic; at a
  flat 92 ms per document, 20 000 documents is about half an hour. Nothing here claims it was
  *run* — the query measurement still comes from a directly-populated store, as ADR-0120 says.
- **Six tests pin what the fix rests on**: the rowid tie, that a rewrite keeps it and loses
  the old text, FTS5's own integrity check after a replace, the document delete leaving other
  documents alone, and the cost property as a *ratio* — a late batch may not cost five times
  an early one — because a wall-clock budget on a CI runner is a flake, and the defect was a
  25× degradation, not a 20 % one.
- **`--profile` is part of the benchmark tool**, so the next person to ask where the build's
  time goes runs a flag rather than writing a script, and the answer lands in the manifest.
- **The version bump found a misdiagnosis in gate G2's currency check, and it is corrected
  here.** `corpus_fingerprint_of` swallows every exception and returns an *empty* fingerprint,
  which matches no recorded digest — so a store the running build cannot open was reported as
  *"the corpus changed since the verdict was recorded; re-run `--record` (needs the model)"*.
  That sends a reader to the one machine holding the embedding model for a problem whose
  remedy is `mycelium build`. It had never fired because this is the first store-version bump
  since the check was written, and it fired on all three corpora at once. An unreadable store
  is now reported the way an absent one already was — not compared, with the remedy named —
  and a test pins the distinction. The fix is in the checker rather than the fingerprint,
  which keeps a tuning path untouched.
- **A limit, stated.** All of this is one machine, and the machine is unusually slow at
  writing files: a plain 4 KiB write costs 12.6 ms here, which is hundreds of times an
  unencumbered SSD, because a real-time scanner sits in the path. That constant is *most* of
  what is left, so a faster machine would show a different balance — the stemmer would matter
  relatively more, and the build might well come in under budget. The manifest records the
  calibration so a reader can scale; nothing here turns one machine's wall-clock into a
  portable number.

## References

- Spec: `.draft-specs/01-product-strategy.md` §8 (the cold-build budget);
  `.draft-specs/02-architecture.md` §4 (the stage DAG and the content-addressed cache).
- The report: `docs/benchmarks/2026-09-19-the-quadratic-in-the-lexical-index.md`, with its
  manifest — which carries the stage breakdown and the profile.
- Decision log: D-005 (the store is derived data), D-016 (rebuild is the migration).
- Re-runnable: `python tools/benchmark_reference_profile.py --out <dir> --scales 250,1000
  --no-reference --profile 1000`, and `uv run pytest tests/test_store.py -q`.
