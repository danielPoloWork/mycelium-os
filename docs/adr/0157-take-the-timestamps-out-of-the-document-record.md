# ADR-0157: Take the timestamps out of the document record, and keep the mtime as a memo

- **Status:** Accepted
- **Date:** 2026-09-25
- **Deciders:** the maintainer (D-032, owner decision) with the tech-lead (EADOS delivery
  agent), per RFC-0001 / spec 03 §3
- **Related:**
  [ADR-0009](0009-adopt-build-publication-semantics.md) (mtime → `created_at`/`updated_at`;
  amended here),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (mtime as a dirty input;
  amended here),
  [ADR-0133](0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md)
  (the stat memo, which is the role the mtime keeps),
  [ADR-0154](0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md)
  (the measurement that found the mtime to be what kept every fresh clone cold),
  [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (which records are frozen, and which change at a MINOR),
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (gate G6, which pinned mtimes to hold);
  D-016, D-032; spec 02 §4.1; spec 03 §§3, 7, 8; spec 04 §4 (recency); roadmap 6.20, 6.38,
  7.4, 7.7

## Context

Roadmap 7.4 measured what any cache could take off a cold build, and the largest number it
found was not a cache's. A restored `.mycelium/` — every stage artifact, every row — still
re-assembled and re-stored every document of a fresh checkout, 40 s against 55 s cold at
1 000 documents; the same checkout given the mtimes its cache was built with rebuilt
**nothing**, in 1.6 s. The whole difference was one field: ADR-0009 made a document's
`created_at` and `updated_at` the source file's mtime, ADR-0015 therefore made the mtime a
dirty input, and a clone's mtimes are the moment it was written.

Roadmap 7.7 asked what the record's time should be a function of, and named three
constraints. Reading them against the code moved two:

- **The record is not frozen.** The item said the fields are covered by the 1.0 promise.
  `docs/compatibility.md` says the opposite in so many words: `document` is among *the other
  record schemas*, which *may change at a MINOR with a `CHANGELOG.md` line*; only KIR and the
  manifest are frozen. The frozen manifest contract does pin the tag `mycelium/document/v0`
  by value, which is why the tag does not move — and it has not moved for any field change
  since v0.1.0 (PR #56 added `secret_flags` under it).
- **Nothing reads the fields.** `mycelium show` does not print them, `mycelium_fetch` does
  not return them, retrieval never reads them — roadmap 6.38 found that a recency boost had
  *no field to read*, because `updated_at` is a build timestamp and uv's 81 documents span
  0.7 seconds of it. They reach the store row, the export bundle and the G6 golden, and the
  golden could only hold by pinning every fixture's mtime before building. And
  `created_at` never differed from `updated_at`: both were set from the same stat on every
  assemble, so the first carried no information at all.
- **What a deterministic time would cost.** The last-commit time is the honest alternative,
  and on the machine of record one `git log --name-status` over 196 commits takes **5.5 s
  warm and 20 s cold** — three to twelve times the whole incremental floor — before the
  questions of an uncommitted edit, a shallow clone and a directory that is not a
  repository. A frontmatter-declared date would be a fourteenth key in the frontmatter
  contract (ADR-0082) that no document in either corpus declares today.

## Decision

**D-032 (owner decision, 2026-09-25): `created_at` and `updated_at` do not belong to the
Document record and are removed.** A value derived from the filesystem's mtime is metadata
of the build process, not of the document; it appears in no compiled record and influences
no compilation result. The mtime is kept **only as the stat memo** of the build state
(ADR-0133) — how a digest is obtained cheaply, never whether a document is dirty. If a
surface ever needs a document's creation or update date, it arrives as metadata the author
declares explicitly, with no inference from the filesystem or from Git.

What follows from it, and ships with it:

- **Dirty detection compares the source digest and the environment digest.** A file with
  the same bytes under a new mtime — a touch, a copy, every file of a fresh clone — is
  reused. The memo still misses on it, so the file is read and digested once, and the memo
  is refreshed so the next build does not pay the read again.
- **The store is v9.** `documents.created_at`, `documents.updated_at` and
  `doc_state.source_mtime` are gone; an older store is recreated on first open (D-016).
  The snapshot-state blob no longer carries `source_mtime`, and an older blob's extra key is
  ignored on restore.
- **Gate G6 no longer pins mtimes, and tests that it need not.** `observe_build` builds the
  checkout as it is; `tests/test_determinism.py` touches every file and asserts the
  observation identical. The pin was a workaround for the claim; the test is the claim.
- **Watch mode does not build for a touch.** `has_real_change` compares the digest alone.
- **The document record's tag stays `mycelium/document/v0`**, for the two reasons in the
  context: the promise classifies the change as a MINOR with a CHANGELOG line, and moving
  the tag would move the frozen manifest golden, which is precisely what the promise
  reserves for an RFC.
- **`tools/measure_cache_ceiling.py`'s `documents` digest joins the portable set**, and its
  `restored-mtimes` arm stays as a control: the two restored arms coincide now, and a gap
  between them would be the mtime finding its way back into the record.

## Alternatives Considered

- **Last-commit time from Git** (the item's first option). Rejected on cost and on
  reach: 5.5–20 s per build here, wrong for an uncommitted edit, empty on a shallow clone,
  absent outside a repository — every case needing a fallback that reintroduces the
  checkout. The owner's decision closes it on principle as well: no inference from Git.
- **First build that saw the digest** (the item's second option). Rejected: a wall-clock
  value makes two clean builds of one tree differ, which breaks G6; an mtime-at-first-sight
  value makes an incremental build differ from a clean one, which breaks the
  incremental-equals-clean invariant ADR-0015 rests on.
- **Frontmatter-declared `created:`/`updated:`, else null.** The recommendation put to
  the owner, and the owner chose the stricter reading: nothing is declared today, so the
  keys would be a contract extension for no consumer, and the day a surface needs a date
  is the day to add the key it needs.
- **Keep the mtime in the record but drop it from the dirty check.** Rejected: it solves
  the cache case and breaks incremental-equals-clean the same way the second option does.
- **Leave it, and document `git restore-mtime`.** Rejected: the item's own bar was to beat a
  recipe, and a recipe every clone has to remember is the shape of thing this repository
  keeps refusing (ADR-0118's rule, one level down).
- **Bump the record tag to `mycelium/document/v1`.** Rejected for the reasons above; the
  CHANGELOG line is the promise's own mechanism for this change.

## Consequences

- **A fresh clone with a restored `.mycelium/` is incremental.** Measured with
  `tools/measure_cache_ceiling.py` after the change
  ([report](../benchmarks/2026-09-25-a-restored-checkout-rebuilds-nothing.md)): a fresh
  checkout with another's `.mycelium/` builds in **5.4 s** at 1 000 documents against 40.1 s
  before and 58.3 s cold, with **0 documents rebuilt**; the 3 s it still spends over the
  mtime control is the memo reading every file once, paid on the first build only. The remote cache
  7.1 describes was worth about 9 ms of computation a document (ADR-0154); this is the
  rest of a cold build, for a directory cache nobody has to build.
- **A consumer of the export bundle that read `created_at` or `updated_at` loses two
  fields** that held one checkout's mtime twice. The CHANGELOG says so; no consumer in this
  repository read them.
- **`provenance.ingested_at` is the one time a document record still carries**, and it is
  a fact about the acquisition, not the checkout. Recency (spec 04 §4) stays unbuilt for
  the reason 6.38 gave, now with the record saying so rather than holding noise.
- **Store v9 rebuilds every existing store once**, at the next build, by D-016's policy.
- **The G6 golden changes by sixteen lines** — the two fields of eight documents — and
  the `documents` digest with them; nothing else moves.

## References

- `src/mycelium/sdk/types.py` (the record), `src/mycelium/build/orchestrator.py` (the
  dirty check and `_assemble`), `src/mycelium/store/schema.py` (v9),
  `src/mycelium/determinism.py`, `src/mycelium/watch.py`.
- `tests/test_determinism.py`, `tests/test_build_incremental.py`, `tests/test_build_floor.py`,
  `tests/test_watch.py`, `tests/test_sdk_types.py`, `tests/test_sdk_schema.py`,
  `tests/test_measure_cache_ceiling.py`.
- Spec 03 §§3, 8 (amended in place); `.draft-specs/00-verdict-and-decisions.md` D-032.
