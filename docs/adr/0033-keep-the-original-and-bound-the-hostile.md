# ADR-0033: Keep the original, and bound what an engine is asked to read

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.2; RFC-0001; spec 02 §§3-5, §8; spec 03 §§1-4; D-004, D-005,
  D-015, D-017; NFR-6, NFR-7; [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md),
  [ADR-0016](0016-make-snapshots-restorable.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md)

## Context

Roadmap 4.1 gave ingestion its contracts and four engines. It stopped one step short of
being usable: the bytes it acquired went nowhere. This item is the other half — **keep the
original**, and **survive what arrives**.

Two problems, and neither is the one the roadmap line makes it sound like.

**The CAS this project already has is the wrong lifecycle.** `mycelium.build.cas` stores
build-cache artifacts under `.mycelium/cas/`, and its own docstring says the right thing
about them: *"Nothing in the published snapshot references the CAS — it is purely reuse, so
deleting the whole directory costs one clean rebuild and nothing else (D-005)."*
`mycelium gc` acts on exactly that belief: it computes a live set from retained snapshots
and cache rows, and deletes every blob outside it. Put an acquired PDF in that directory
and the first `gc` deletes the evidence a citation quotes. Architecture §4 is explicit that
tier 1 is *"content-addressed original bytes + KIR under .mycelium/cas"* and that the
compiler is a pure function of tiers 1-2 — so tier 1 shares the CAS's *address space* and
must not share its *lifecycle*.

**Hostile input was not handled, and measurement said so.** Two defects, both found by
running real engines against generated fixtures rather than by reasoning about them:

| Input | Before | Why no byte ceiling helps |
|---|---|---|
| HTML nested 5 000 deep (55 KB) | docling: **45 s**; at 50 000 deep (550 KB) it had **not returned after five minutes** | cost is superlinear in *structure* |
| the same file, via pandoc | **`RecursionError`** out of `json.loads` — uncaught, so it escaped `parse()` as an unhandled exception | a hostile file crashed ingestion instead of being quarantined by it |
| 50 MB of zeros in a 51 KB `.docx` | opened and expanded | 51 KB is far below any sane ceiling |

The connector's 64 MiB limit is a bound on *bytes*. All three of these are small.

A third, smaller thing: 4.1's pandoc adapter set an opaque node's `blob` field to the digest
of a payload **it never stored**. A digest naming bytes nobody wrote is a claim a reader
cannot follow.

## Decision

**Tier-1 custody is a named subtree of the CAS that the garbage collector never sweeps, and
ingestion writes the original into it before deciding whether the document is worth
parsing.**

`.mycelium/cas/originals/` holds acquired originals and the KIR compiled from them, each
content-addressed and each accompanied by a `CustodyRecord` (`mycelium/custody/v0`) written
*beside the blob* rather than into the store — because the store is tier 3 and disposable,
and an index that can be deleted must not be the only thing that knows a piece of evidence
exists. `CUSTODY_DIRNAME` is declared in `mycelium.build.cas`, beside the layout it excepts,
so the module that deletes blobs and the module that writes them read the same rule from the
same place.

Custody obeys three rules that the build cache deliberately does not:

- **Write-once.** `first_seen` is set at first acquisition and never moves. Re-ingesting
  unchanged bytes must produce an unchanged record, or an incremental rebuild is invalidated
  by a clock.
- **Amendments only grow**, and grow deterministically: `sources` is a sorted set, so two
  machines that met the same bytes at two URIs in opposite orders hold byte-identical
  records.
- **A corrupt blob is reported, not deleted.** `cas_get` discards a blob that fails its own
  digest because losing it costs a recompile. Custody must not: a corrupt original is the
  loss of the only copy of something a citation quotes, so `mycelium doctor` reports it and
  the operator decides.

**The order in `ingest_source` is acquire → store → guard → parse → store**, and storing
before guarding is a decision, not an oversight. It costs a write for a document that turns
out to be hostile, and buys the ability to look at that document afterwards; a quarantined
file whose bytes were never kept cannot be re-examined, and re-examining them is the whole
reason to quarantine rather than drop (roadmap 4.6).

**Hostile input is bounded by shape, in layers, before any engine runs.**
`mycelium.ingest.safety` refuses an archive whose own directory declares a bomb (ratio,
total size, member count, member names that climb out), and refuses markup nested or
populated past a ceiling, from one linear scan. The ceilings are set where no honest
document reaches them: depth 256 against a corpus whose deepest document nests 8. What the
pre-scan cannot see, the shared `KirBuilder` catches — node count and total text — so a new
adapter inherits the last line of defence without knowing it exists. And `RecursionError` is
caught wherever a tree is decoded or walked, because a hostile document must fail as *one
document*.

**An opaque node no longer names a blob nobody stored.** Where pandoc's payload is literal
source text — `RawBlock`, `RawInline` — it is kept as the node's `text`, the same treatment
ADR-0006 gives raw HTML in authored Markdown. Where the construct is structured, the node
carries its name and its position and nothing else. `blob` is reserved for a payload that is
actually in custody.

## Alternatives Considered

- **Put custody in a sibling directory, `.mycelium/custody/`.** The lifecycle difference
  would be visible in the layout at a glance. Rejected because architecture §4 places tier 1
  *under* `.mycelium/cas`, and having just spent ADR-0032 on two deliberate spec deviations,
  a third for cosmetics is not worth the drift. The name plus an explicit, tested exclusion
  carries the same signal.
- **Pin custody blobs by adding them to the garbage collector's live set.** The mechanism
  already exists and it would need no new subtree. Rejected because the live set is computed
  from the SQLite store, which is tier 3: delete the store — a supported, documented,
  disposable act — and every original becomes unreferenced and is collected on the next
  sweep. Tier 1 cannot be pinned by tier 3.
- **Store the custody record in the store rather than beside the blob.** Faster to query and
  it is where records normally live. Rejected for the same reason, and one more: a record on
  disk beside its bytes survives a store rebuild, and `mycelium doctor` can then still tell
  an operator what the evidence *was* when the blob is gone.
- **Bound hostile input with a wall-clock timeout on the parse.** It catches everything,
  including what the pre-scan does not model. Rejected as the *primary* defence: an
  in-process timeout in CPython cannot reliably interrupt a C extension, the threshold is a
  machine-speed guess, and a document that succeeds on a fast laptop and fails in CI is a
  worse property than a document that is refused everywhere for a stated, reproducible
  reason. The pandoc subprocess keeps its timeout, because there the kill is real.
- **Reject the mislabelled file whose bytes contradict its extension.** Tempting, and it is
  detected already (4.1). Rejected: the operator's pinned parser list was written against
  *names*, an extension is a claim the operator made, and refusing it would turn a warning
  into a build failure for a file that may well be exactly what its owner intended.
- **Name a design pattern for the guards.** "Guard" is not in the canonical taxonomy;
  *Guarded Suspension* is a concurrency pattern about blocking until a precondition holds,
  and nothing here blocks; *Specification* composes predicates as objects, and these are
  four fixed checks with no composition and no caller that wants any. Both are recorded as
  rejections in the catalogue rather than force-fitted, which §8 forbids — the honest
  description of `safety.py` is "four functions that raise".
- **Extend the `Parser` protocol with a payload sink**, so an adapter could store opaque
  bytes in custody and set `blob` honestly. Rejected for now: it widens a contract that
  froze one PR ago for a field with no consumer yet. When 4.3's fidelity reports need
  extracted images, that is the moment to decide it — with a use case in hand.

## Consequences

- **`mycelium gc` grew a promise it must keep.** `kept_custody_blobs` and
  `kept_custody_bytes` are reported so an operator reclaiming space can see how much of
  what is on disk is not reclaimable and why. The load-bearing test builds a repository,
  puts an original in custody alongside a collectable cache blob, runs `gc` with
  `keep=0, cache_max_age_days=0` — the most aggressive sweep the command offers — and
  asserts the cache blob is gone and the evidence is not.
- **`mycelium doctor` gained a `custody` check** that re-hashes every tier-1 blob. It is the
  only check that reports a problem it deliberately does not fix.
- **A new exported contract**, `mycelium/custody/v0`, joins `RECORD_MODELS` and therefore the
  exported `schemas/` directory. It is *not* a snapshot artifact class: a custody record
  outlives every snapshot that referenced it.
- **The hostile suite is now a committed fixture set** with a per-file time budget in the
  test. Eight files, each generated by `make_fixtures.py` so a reviewer can see what makes
  it hostile, and each asserted to produce one typed failure — with the two that were real
  defects going from "45 s / never returns" and "unhandled `RecursionError`" to a refusal in
  under a tenth of a second.
- **The ceilings are a compatibility surface.** A document that ingested yesterday and
  breaches a ceiling today would start failing, so the defaults are set two orders of
  magnitude clear of anything observed and asserted as such in a test. They are not
  configurable yet; `[ingest] max_failed_elements` and its neighbours arrive at 4.3, and the
  ceilings should join them there rather than growing a key of their own now.
- **`atomic_write_bytes` is the new primitive** under `atomic_write_text`. Custody stores a
  DOCX, and `O_BINARY` mattering for manifest bytes matters far more for a file that
  contains 0x0A by coincidence.
- **What this does not do**: project evidence Markdown or write fidelity reports (4.3), scan
  for secrets or decide what happens to a failed document (4.6), or add a `mycelium ingest`
  command. `ingest_source` raises a typed error and leaves the decision to its caller —
  which is what lets 4.6 quarantine, a test assert, and a future build stage record.

## References

- Spec 02 §3 (tiers and layout), §5 (the evidence lane), §8 (untrusted content, path
  safety); spec 03 §1 (canonical bytes and digests), §4 (KIR, the `opaque` escape hatch).
- D-004 (three-tier authority), D-005 (the derived world is disposable), D-015 (crash
  safety), D-017 (all source content untrusted).
- Measured this session, on this machine: docling on nested HTML — 0.6 s at depth 200, 7.3 s
  at 1 000, 45.3 s at 5 000, no return within 300 s at 50 000; the same input through pandoc
  — `RecursionError` at depth 1 000; a 51 247-byte `.docx` declaring 52 428 829 uncompressed
  bytes. After the guards: every one refused in under 0.1 s.
- [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) — the contracts and engines
  this item stores the output of.
- [ADR-0016](0016-make-snapshots-restorable.md) — where the garbage collector's live set was
  defined, and the reasoning this ADR has to carve an exception out of.
