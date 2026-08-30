# ADR-0016: Make snapshots restorable, and give garbage collection a defined live set

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §4.3
- **Related:** [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the CAS and
  `doc_state` this builds on), [ADR-0009](0009-adopt-build-publication-semantics.md) (the
  publication order rollback reuses), [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md)
  (the store protocol these operations speak through); spec 02 §§3–4, spec 05 §1;
  D-005, D-015, D-019; roadmap 3.2

## Context

Spec 02 §4.3 defines rollback in one sentence: *"`mycelium rollback <id>` repoints
`CURRENT`; nothing rebuilds."* Spec 05 §1 adds `mycelium snapshots` beside it and
`mycelium gc` — *"remove unreferenced CAS blobs and staging debris beyond retention"*.
Roadmap 3.2 asks for all three.

Taken literally, rollback is a one-line command: write a different id into `CURRENT`. That
reading only works if the store is *versioned* — if the rows belonging to every published
snapshot are still there to be pointed at. Ours is not, and deliberately so: the v0
publication semantics (ADR-0009) and the incremental compiler (ADR-0015) both write into
one mutable store, because a versioned store is platform-phase work (D-019). So the rows
in `store.db` always belong to the newest build. Moving the pointer alone would produce a
repository whose `CURRENT` names snapshot A while its data is snapshot B — which is
precisely the disagreement `mycelium doctor` has reported as corruption since 2.8, and
which every citation resolved against the served snapshot would then answer wrongly. The
literal implementation is a lie the tool already knows how to detect.

Garbage collection has a second, quieter problem. A content-addressed store can only
collect what nothing reaches, and after 3.1 *nothing recorded what a snapshot reached*.
The `build_cache` table maps build keys to blobs, but it is a cache: it names what might
be reused, not what a published snapshot needs. With only that table, either every blob
is reachable (the cache pins it forever, and `gc` collects nothing) or the sweep guesses
— and a wrong guess deletes an artifact a snapshot depends on.

Both problems have the same shape: a snapshot is a name and a manifest of *digests*, but
nothing says which artifacts it consisted of.

## Decision

**A snapshot carries the state it can be restored from.** Every publication writes one
content-addressed blob holding that build's whole `doc_state` table in canonical JSON —
per document: identity, path, source digest, source mtime, environment digest, artifact
digests, warnings — and a new `snapshot_state` row points the snapshot at it. This is a
**Memento**: the compiler's internal state captured in a form that can be handed back to
it later, without any consumer of a snapshot depending on that state's shape.

One blob and one row per snapshot, deliberately not one row per document per snapshot.
Publication stays O(changed) in *writes*: a rebuild that changed nothing serializes the
same bytes, addresses the same blob, and writes nothing at all.

**The assemble stage's output becomes addressable, though the stage stays uncached.**
ADR-0015 keeps `assemble` out of the build cache (its mtime input changes alone too
often), but its `Document` record is now stored in the CAS at the digest the manifest
already folds — `cas_put(canonical_json(record))` returns exactly
`digest_json(record.model_dump())`. One address, two uses: invalidation before, and
restoration now. Chunk artifacts were already in the CAS from the chunk stage.

**Rollback restores, then repoints — under a build's discipline, not beside it.** It takes
the writer lock, loads and *revalidates* every artifact the state names before touching
anything, verifies that the recorded state folds back to the manifest's published
`artifact_digests`, and only then replaces the corpus in one transaction, sets
`meta[current_snapshot]`, commits, and swaps `CURRENT` (ADR-0009's order, unchanged). An
interrupted rollback leaves `CURRENT` untouched. Restoring `doc_state` alongside the rows
is what makes the *next* build correct: it diffs against what is actually in the store, so
rolling back and rebuilding recompiles the documents that drifted and no others.

Nothing is recompiled — the promise the spec was making. The pointer swap alone was never
enough to keep it.

**A missing artifact is a refusal, never a partial restore**, naming the document and the
fix. Restorability is therefore checked twice, at two costs: `mycelium snapshots` reports
whether a snapshot's *state* is recorded and present (one lookup each), and `rollback`
verifies every artifact that state names (the deep check, which it needs anyway).

**Publication tells the truth about restorability.** Every build stats the artifacts of
its live documents — two per document — and when any is missing (a hand-deleted cache is
documented as safe, and stays safe), the snapshot publishes and serves normally but is
marked `degraded: ["snapshot_state"]` with a warning naming `mycelium build --clean` as
the repair. A snapshot is recorded as restorable when it *is*, not when it ought to be.

**Garbage collection's live set is computed from the survivors, before anything is
deleted:** the state blob of every retained snapshot, every document and chunks artifact
those states name, and the artifact of every retained `build_cache` row. Whatever remains
under `.mycelium/cas/` is unreachable by construction.

Retention has two dials, because there are two kinds of history: `--keep N` (default 10)
retains snapshots you might roll back to; `--cache-max-age DAYS` (default 30) retains
cached artifacts that only make future builds faster. The second dial is not a
convenience — without it the cache pins every blob it ever wrote and the sweep can never
collect anything. `created_at` on `build_cache`, which ADR-0015 recorded for exactly this
moment, is what it cuts on. **`CURRENT` is retained whatever its age**, including at
`--keep 0`, and including when it is not the newest snapshot — which is the state a
rollback leaves behind.

**Store schema v2** adds `snapshot_state`. Per ADR-0015 the writer recreates a
foreign-version store in place and recompiles, so the upgrade needs no operator action.

## Alternatives Considered

- **Repoint `CURRENT` and nothing else — the spec's literal text.** Rejected: with one
  mutable store it publishes a snapshot id whose data is a different snapshot. `doctor`
  would report the result as an interrupted build, citations would resolve against rows
  the manifest does not describe, and the failure is silent until someone reads an answer.
  The spec's sentence assumes versioned storage; this milestone's honest equivalent is
  restore-then-repoint.
- **Refuse to roll back at all until the platform phase.** Rejected: the operation the
  user actually wants — *"the last build broke something, put it back"* — is exactly what
  a byte-deterministic compiler with a content-addressed cache is in a position to give.
  Deferring it would leave the CAS holding everything needed and no way to use it.
- **Reconstruct a snapshot by recompiling its sources.** Rejected: the sources for an old
  snapshot are usually gone (that is why you are rolling back), and it would contradict
  *"nothing rebuilds"* even more thoroughly than restoring does.
- **One `snapshot_documents` row per document per snapshot.** Rejected: it puts an
  O(corpus) row write back into every publication — the cost 3.1 removed — and buys
  nothing a single deduplicated blob does not already give. A no-op build would write
  thousands of identical rows; it now writes zero bytes.
- **Put the document set in the snapshot manifest.** Rejected: the manifest is a stable
  contract (spec 03 §7, frozen at 6.1) and a consumer-facing one. Restore state is an
  implementation detail of this milestone's storage model, and a versioned store would
  delete it without changing what a snapshot *means*. It belongs in the derived store.
- **Trust cached artifacts on restore** (skip revalidation and the manifest fold).
  Rejected: it would make the cache an authority, which ADR-0015 explicitly refused. The
  fold is what turns "something plausible was found in the cache" into "this is the
  snapshot the manifest describes", and it costs one digest over a list of digests.
- **Reference-count blobs instead of mark-and-sweep.** Rejected: counters drift under
  crashes and concurrent writers, and repairing them requires the sweep anyway. The live
  set is small, cheap to recompute, and derived from data that is committed
  transactionally.
- **Collect by blob age instead of reachability.** Rejected: an old blob may be exactly
  what the oldest retained snapshot needs. Age is the right dial for a *cache*, and the
  wrong one for a snapshot's artifacts.

## Consequences

- **Rollback costs real work, and the numbers are stated rather than implied.** On 200
  documents / 1 800 chunks (Windows dev machine): rollback **4.0 s** against a **15.2 s**
  clean rebuild — 3.8× faster, and it needs no sources. The committed benchmark says the
  same at its own scale: 30 documents, rollback **229 ms** vs clean rebuild **500 ms**,
  with `snapshots` at **13 ms** and a steady-state `gc` at **109 ms**. It is *not* the
  O(1) pointer swap the spec sketches: the store is rewritten row by row and the lexical
  index with it, and every artifact is re-validated on the way in. Making rollback O(1)
  needs a versioned store, which is D-019 platform-phase work; this ADR does not pretend
  otherwise.
- **Publication grows a small fixed cost**: two stats per live document plus one
  serialization of the state. Measured at 200 documents, the no-op incremental build went
  from ~452 ms to ~473 ms; the single-edit build from ~546 ms to ~573 ms. The < 2 s
  single-edit budget is unaffected.
- **`gc` reclaims what it should and keeps what it must**: at `--keep 1
  --cache-max-age 0` on the same repository it removed 201 blobs (1.1 MiB) and 402 cache
  rows in ~1.1 s, and every retained snapshot still rolled back afterwards — the property
  the tests assert, because a collector that breaks its survivors is worse than none.
- **Snapshot history is cheap to keep**: an unchanged corpus re-addresses the same state
  blob, so a watch loop (3.5) rebuilding on every keystroke accumulates manifests, not
  artifacts.
- **The G6 golden is untouched.** Restorability changes what is *stored beside* a
  snapshot, not what the compiler produces: same records, same digests, same manifest
  bytes for the fixture corpus. That the gate passed without a re-bless is the evidence.
- **`.mycelium/` grows one more responsibility**, and the whole directory remains
  disposable (D-005): deleting it costs a rebuild, deleting only `cas/` costs
  restorability until the next `--clean` build, and both are reported rather than
  discovered.
- Patterns: **Memento** joins the catalogue for the snapshot state. Mark-and-sweep
  collection is deliberately *not* catalogued — it is an algorithm, not a design pattern
  in the project's taxonomy, and AGENTS.md §8 forbids force-fitting.

## References

- Spec: `.draft-specs/02-architecture.md` §3 (on-disk layout), §4.2–4.3 (the algorithm's
  `gc_unreferenced`, the snapshot manifest and rollback);
  `.draft-specs/05-interfaces-and-plugins.md` §1 (`snapshots`, `rollback`, `gc`)
- Decision log: D-005 (the derived world is disposable), D-015 (single writer, atomic
  publish), D-019 (the platform-phase store)
- [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) — the CAS, `doc_state`,
  and the digest-folding construction this restores against
- Tests: `tests/test_snapshots.py`; benchmarks: `tests/bench/test_snapshots_bench.py`
