# 2026-09-03 — the flag was the easy half (roadmap 4.14)

- **Session scope:** roadmap 4.14 — let a build compile without writing to the tree.
- **PR:** #66 (`feat/build-without-pinning`). Follows #65 (4.13), merged as `b8e49f9`.
- **Milestone 4:** 4.14 done; 4.8, 4.18, 4.19, 4.20, 4.21, 4.22, 4.15 open.

## The item as filed, and the item as it turned out

As filed, this was a convenience: compiling this repository to measure something leaves
105 modified files, so give it a `--no-pin`. Size S, and the flag really is about twenty
lines.

The twenty lines are not the change. Suppressing the write raises a question the item did
not ask — *what identity does a document take when the build may not record one* — and the
obvious answer (mint it, just do not write it) turns out to preserve the worse half of the
problem. `Document.doc_id` is inside the record the snapshot manifest folds. A pinning
build of an unpinned corpus mints a fresh ULID per document, so **the same tree publishes a
different corpus on every run**. CI, which starts every run from an empty store, has been
doing exactly that — for this repository (105 documents) and for `uv-docs-ingested` (82),
two of the three corpora the eval job scores.

That the checkout is thrown away made it harmless. It never made it reproducible.

So the identity is **derived from the path** instead: `derived_ulid`, a valid ULID with a
zero timestamp and 80 bits of SHA-256 over the normalized path. Total — no clock, no
entropy, no state — so the same corpus compiles to the same snapshot anywhere. The zero
timestamp is the marker rather than a new record field: no clock reports the Unix epoch,
so `is_derived_ulid` is exact and a derived id sorts before every minted one.

Measured, on this repository: two from-scratch `--no-pin` builds produce identical
`artifact_digests`. `git status` is clean afterwards.

## What the tests caught that review would not have

The plan skips the frontmatter parse when a document's digest is unchanged, and the comment
above it states the premise out loud: *an indexed document was pinned, its pinned identity
is frontmatter, frontmatter is content — so an unchanged digest proves the id is still in
the file.* A derived id makes that false. It was never written anywhere.

The consequence, before the fix: after one `--no-pin` build, a normal `mycelium build`
pins **nothing**, forever. The store already has an id for every document and the digests
have not moved, so the fast path answers first, and the corpus never gains the identities
the operator went back to get. Silent, and permanent until someone deletes `.mycelium/`.

`test_pinning_after_an_unpinned_build_replaces_the_derived_ids` failed on the first run,
which is the only reason I know. A pinning build that meets a derived id now falls through
and pins for real.

## Two claims that had to be tests, not prose

Both are about whether a measurement taken this way means anything:

- **Reproducibility, with its counterfactual.** Two `--no-pin` builds fold identically —
  and two *pinned* builds of the same tree do not. The second test is the one that keeps
  the first honest; without it, "reproducible" is a property nobody checked against the
  alternative.
- **Anchors do not move.** An anchor is `<doc-path>#<slug-path>/<ordinal>` (ADR-0005) —
  path and structure, no identity — so a judged case written against a pinned build names
  the same chunk in an unpinned one. If that were false, `--no-pin` would have made
  measurement easier to run and impossible to compare, which is worse than the problem.

Gate G3 needed no change at all: 4.13 had already made both eval fingerprints
identity-free (ADR-0045), for a closely related reason — a fold over anything
identity-bearing would never match in CI. That decision paid for itself one item later.

## What this does not decide

Whether this repository's release baseline gets re-blessed, and whether G3 can ever enforce
on a corpus that grows every PR, is 4.22. This removes one obstacle from that decision —
our own corpus can now be compiled reproducibly — and takes none of it.
