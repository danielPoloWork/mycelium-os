# ADR-0046: Derive an identity rather than mint one, when a build may not write

- **Status:** Accepted
- **Date:** 2026-09-03
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.14; RFC-0001; spec 02 §4, spec 03 §§2-3, spec 05 §§1, 4.2;
  D-002, D-008; NFR-1; [ADR-0005](0005-adopt-in-repo-identity-library.md),
  [ADR-0009](0009-adopt-build-publication-semantics.md),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md)

## Context

`mycelium build` writes into the authored tree exactly once, and for exactly one reason:
a document with no `mycelium_id` gets one minted and inserted into its frontmatter.
ADR-0009 argued that write and it is right — a pinned identity is what makes a citation
survive a rename, and there is no other way to record it. But it has no off switch, and
that has been costing something all along:

- Compiling this repository's own corpus to measure anything modifies **105 tracked
  files**. Not one of them should be committed as part of the measurement, so every such
  session ends with a `git checkout -- .` that a distracted operator will one day forget.
- CI worked around it by observing that the runner's checkout is thrown away. True, and
  it hides the real problem rather than solving it.

The real problem is the one that surfaced while measuring 4.11 and stamping 4.13: **a
pinning build of an unpinned corpus is not reproducible.** Each run mints fresh ULIDs,
`Document.doc_id` is inside the record the snapshot manifest folds, so two builds of the
same tree publish two different corpora. On CI, where every run starts from an empty
store, *every* run measured a different corpus. Two of the three corpora that job scores
are unpinned — this repository (105 documents) and `uv-docs-ingested` (82) — so this was
not hypothetical.

Suppressing the write therefore cannot be the whole change. A document with no id still
needs one for the duration of the build, and the obvious answer — mint it and simply do
not write it — keeps the reproducibility defect and adds nothing. The question this ADR
answers is what identity a document takes when the build is not allowed to record one.

## Decision

`mycelium build --no-pin` (`build(..., pin_identity=False)`) compiles, publishes and
serves while leaving tier 2 **byte-identical**, and a document that carries no
`mycelium_id` takes an identity **derived from its repository-relative path** —
`derived_ulid(path)`: a valid ULID whose timestamp field is zero and whose 80 randomness
bits are the leading bits of the SHA-256 of the normalized path.

The derivation is total — no clock, no entropy, no state — so the same corpus compiles to
the same snapshot on any machine, in any order, as many times as you like. The zero
timestamp is the marker: no clock reports the Unix epoch, so `is_derived_ulid` is an exact
test, a derived id sorts before every minted one, and nothing needed a new record field to
carry the distinction.

Three consequences are made explicit rather than left to be discovered:

1. **The manifest says so.** A snapshot whose documents took derived identities carries a
   warning naming the count, because a build must be explainable from its manifest alone
   (spec 05 §4.2). It is counted from the ids in the published corpus, not from the flag —
   a derived id can also arrive from a `doc_state` row an earlier unpinned build wrote.
2. **A pinning build undoes it.** The plan's fast path skips the frontmatter parse when a
   document's digest is unchanged, on the premise that "an indexed document was pinned, so
   its id is still in the file". A derived id breaks that premise, so a pinning build that
   meets one falls through and pins for real. Without this, the first `--no-pin` build
   would have silently turned every later build into a no-pin build.
3. **A derived id does not survive a rename.** It is a function of the path, so renaming
   the document renames the document. Surviving a rename is precisely what pinning buys,
   and it is what a run that declines to pin gives up — for the duration of that run.

## Alternatives Considered

- **`--dry-run`: compile, report, publish nothing.** Rejected because it does not do the
  job. The measurement use case needs a published snapshot to score against; a build that
  publishes nothing leaves `mycelium eval` with nothing to read. `--no-pin` names the one
  thing that is suppressed, and suppresses only that.
- **Mint a ULID and simply not write it.** The smallest possible change, and it fixes the
  dirty tree. Rejected because it leaves the worse half of the problem in place: the same
  corpus would still fold a different manifest on every run, so two measurements would
  still not be comparable — and now with no file on disk to explain why.
- **Derive the id from the document's *content* digest.** Attractive: identity would then
  follow the document through a rename. Rejected — it inverts the failure. Content changes
  on every edit, so the id would change on every edit, and incremental builds would see a
  delete plus an add for a typo fix (ADR-0015). Path is stable under the operation that
  matters here (editing) and unstable under the one a measurement run does not perform
  (renaming).
- **Refuse to build documents that have no id when `--no-pin` is set.** Consistent, and
  useless: on this repository that is every document.
- **Make it a `mycelium.toml` setting.** Rejected: whether *this run* may write to the
  tree is a property of the invocation, not of the repository. A setting would also mean
  the answer could be committed, which is precisely the state an operator reaching for
  this flag is trying to avoid.
- **Leave CI throwing its checkout away.** Rejected: it addresses the symptom that costs
  nothing (a dirty checkout nobody keeps) and not the one that costs something (a corpus
  that differs between runs).

## Consequences

- **Measurement becomes a read-only act.** `mycelium build . --no-pin` on this repository
  compiles 105 documents and leaves `git status` clean — verified this session.
- **An unpinned corpus becomes reproducible.** Two from-scratch `--no-pin` builds of this
  repository produce identical `artifact_digests`; two pinned builds of the same tree do
  not. Both directions are tests, so the claim is not folklore.
- **CI's three eval builds are now repeatable**, and the workflow says why instead of
  saying that the checkout is discarded.
- **Gates are unaffected.** G3's comparability rests on the eval fingerprints, and both are
  identity-free by construction (ADR-0045) — the content fold is built from chunk *text*,
  the chunk fold from chunk digests. Anchors are `<doc-path>#<slug-path>/<ordinal>`
  (ADR-0005), so a judged case written against a pinned build names the same chunk in an
  unpinned one; that too is a test.
- **`--watch --no-pin` is allowed**, unlike `--clean` and `--require-vectors`, which watch
  mode refuses. Those are single-shot intents; "do not write into this tree" is a property
  of the whole session.
- **A new SDK function**, `derived_ulid`, alongside `new_ulid`. It is not a general-purpose
  identity constructor and says so: 80 bits gives 2^40 collision resistance by the birthday
  bound, comfortable for the 10²–10⁵ documents v1 targets (D-002) and not a claim beyond
  that.
- **What this does not decide.** Whether this repository's baseline should be re-blessed,
  and whether G3 can ever enforce on a corpus that grows every PR, is roadmap 4.22. This
  change removes one obstacle from that decision — our own corpus can now be compiled
  reproducibly — and takes none of it.

## References

- ROADMAP 4.14 (this item), 4.11 and 4.13 (where the cost was paid twice), 4.22 (the
  baseline decision this unblocks but does not take).
- Spec 02 §4 (the stage DAG and its build keys), spec 03 §§2-3 (identity rules, the
  document record), spec 05 §1 (CLI conventions), §4.2 (a build is explainable from its
  manifest alone).
- [ADR-0009](0009-adopt-build-publication-semantics.md) — why pinning is a tier-2 write at
  all, and why it is the only one.
- [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md) — the identity-free
  fingerprints that make this change invisible to gate G3.
