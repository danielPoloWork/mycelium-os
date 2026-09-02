# ADR-0045: Ask the documents whether two runs are comparable, not the boundaries

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.13 (and 4.11, 4.12, 4.15); spec 04 §§7.1, 7.3;
  [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md);
  [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md)

## Context

Gate G3 says no release may regress a protected slice by more than 2 % against a committed
baseline (spec 04 §7.3). A regression check needs a controlled variable, and on a
self-hosting corpus the corpus is not one: this repository's documentation grows with every
PR, so adding an ADR moves per-slice scores without a line of retrieval code changing. G3
failed on exactly that on its first run, which is [BUG-0014].

The fix was to give the baseline a fingerprint of the corpus it was taken on and have G3
**enforce when the fingerprint matches and report when it does not**. The fingerprint had to
be identity-free — the manifest's `artifact_digests` fold chunk *records*, which carry
`doc_id`, and an unpinned checkout mints fresh ULIDs every build, so a gate keyed on them
would never enforce in CI — so it was defined as the fold of the chunks' own content
digests. That worked, and it has been holding the line since.

It also, quietly, made the gate blind in one direction. Roadmap 4.11 measured what
`[chunking] pack_atomic` does — uv/release nDCG@10 0.280 → 0.451, no slice regressed — and
4.15 exists to flip it on. That change moves **every chunk boundary in every corpus**, so
the chunk fold moves, so G3 takes its not-comparable branch and abstains. The gate best
placed to judge a chunking change is the one change it can never see, and 4.15 was
scheduled to land with, in its own words, "no gate G3 verdict to lean on".

That is not a small hole. A chunking change is the most dangerous kind of retrieval change
this project makes: it moves the retrieval unit, deletes anchors (4.12 re-anchored five
judgments for exactly that reason), and cannot be reasoned about from the diff. It is the
change a regression gate is *for*.

The three options roadmap 4.13 recorded were: digest the documents instead of the chunks;
carry both digests and enforce on the documents while reporting on the chunks; or gate on a
corpus whose judgments are all section-scoped. The third is a precondition rather than a
fix — 4.12 already made every judgment survive the flip — and it says nothing about
comparability. The first is the right instinct with a trap in it: the obvious document-level
digest is `Document.content_digest`, which is a digest of the file's text **including its
frontmatter**, and frontmatter is where the build writes the pinned `mycelium_id`. Keying on
it would reproduce BUG-0014's root cause precisely — a fingerprint that never matches on an
unpinned corpus, in CI first of all.

## Decision

**A corpus has two fingerprints, and they answer different questions.**

`content` — *what the corpus says.* Per document, a digest of its text as the published
chunks carry it, whitespace collapsed, folded over documents sorted by path. Built from
chunk text, so it carries no identity; whitespace-collapsed and concatenated in document
order, so the *placement* of the boundaries cannot reach it.

`chunks` — *how the corpus was cut.* The fold of the chunks' own content digests: exactly
the fingerprint BUG-0014 introduced, unchanged in meaning, so a baseline blessed before this
split still says what it said.

**Gate G3 enforces on `content` and reports `chunks`.** Same documents, different
boundaries, and the gate enforces — naming the re-cut in its verdict, so a reviewer reads
"the same documents cut differently — a chunking change, enforced rather than excused"
rather than wondering why the numbers moved. Different documents, and it reports without
enforcing, exactly as BUG-0014 requires.

**A baseline with no `content` fingerprint gets the comparison it was written for**, and the
verdict says so and names `--bless` as what arms the stronger one. Treating a missing field
as a match would let a stale baseline enforce against a corpus nobody checked; treating it
as a mismatch would silently stop enforcing everywhere at once.

Chunks are folded **in document order, keyed on each chunk's line span** rather than on its
anchor. Anchors sort lexicographically, so `…/10` precedes `…/2`: the order in which a
document's chunks concatenate would otherwise depend on how many there are, which is the one
thing the content fold must not be able to see.

Committed baselines are stamped with their content fingerprint **without being
re-blessed**, by `tools/stamp_baseline_fingerprints.py`, so 4.15 is measured against the
line that was already drawn. The tool rebuilds each corpus and refuses to write if the chunk
fold has moved since the bless — because then the recorded numbers describe a different
corpus, and stamping today's fingerprint onto them would be a lie rather than a migration.

That refusal fires on **this repository's own baseline**, and it is right to. Our corpus
grows with every PR, so that baseline was already stale when 4.13 arrived; G3 has been
abstaining on it and will continue to. The two vendored corpora — whose documents do not
move — are stamped and armed. So after this change uv/release is the set 4.15's flip has a
gate to clear, ours/release is a reported delta, and the decision about what a committed
baseline means for a self-hosting corpus is filed as roadmap 4.22 rather than taken here,
because taking it would mean moving numbers.

## Alternatives Considered

- **Fold `Document.content_digest`.** The literal reading of 4.13's first option, and one
  line of code. Rejected: that digest covers the whole file including frontmatter, so it
  moves when the build pins a `mycelium_id`. It is the exact failure BUG-0014 diagnosed for
  the manifest's record digests, re-introduced one field along.
- **Keep one fingerprint and let the operator override.** A `--gate-anyway` flag, or a
  "corpus changed, enforce regardless" switch. Rejected: an override is what a reviewer
  reaches for when the gate is inconvenient, which is how a gate becomes decoration — the
  failure mode BUG-0014's own fix was written to avoid.
- **Re-bless the baselines in this change instead of stamping them.** Simpler: no tool, no
  new field, `--bless` writes both digests. Rejected because it defeats the purpose. A
  baseline re-blessed from the change under test cannot gate that change, and 4.15's whole
  problem is that it had no line to be measured against. Stamping adds the field and moves
  no number.
- **Fold the KIR node texts instead of the chunk texts.** More principled — KIR is upstream
  of chunking, so boundary-independence would be structural rather than argued. Rejected on
  availability: a published snapshot serves chunks, and KIR lives in the CAS behind a
  digest. Reaching into tier 1 to answer a question about tier 3 would couple the gate to
  custody for no gain the collapse does not already give.
- **Gate on section-scoped judgments only** (4.13's third option). Rejected as a
  *comparability* answer: it makes judgments durable across a re-cut, which ADR-0029 already
  argued and 4.12 already delivered, but it leaves the gate with no way to tell a re-cut
  corpus from a changed one. It is a precondition for 4.15, not a fix for G3.

## Consequences

- **4.15 has a gate to clear — on the vendored corpora.** Their baselines are stamped at
  today's default, so flipping `pack_atomic` leaves the documents untouched, `content`
  matches, and G3 enforces the 2 % per-slice rule against the pre-flip numbers. uv/release
  is therefore the verdict that binds; ours/release still abstains, because its baseline
  could not be stamped (roadmap 4.22). The item's "no gate G3 verdict to lean on" no longer
  holds, and its ROADMAP text is corrected with that scope stated rather than glossed.
- **The property is measured, not asserted.** One corpus compiled twice — `pack_atomic` off,
  then on — must move the chunk fold and hold the content fold. It is a test, so a future
  change to either the chunker or the fingerprint that breaks the relationship fails in CI
  rather than in a reviewer's memory.
- **Baselines gain a field, and keep their numbers.** `content_digest` is added; `per_slice`
  and `corpus_digest` are byte-identical. The diff is three added lines, which is the receipt
  that no score moved.
- **The report is longer, and says which comparison ran.** Every G3 verdict now ends in one
  of four phrases — same boundaries, cut differently, not comparable, or predates the
  fingerprint. A gate that abstains has always been allowed here; a gate that abstains
  without saying why is what this ADR removes.
- **`corpus_digest_of` is gone**, replaced by `corpus_fingerprint_of` returning
  `CorpusFingerprint`. Pre-1.0, and `mycelium.eval` is not one of the five contracts that
  freeze at 1.0 (architecture §10), so the rename is taken rather than aliased.
- **A collapse is a deliberate blind spot.** Whitespace-only changes to a document — a
  reflow, a re-wrapped paragraph — move the chunk fold and not the content fold, so G3 will
  enforce across them. That is the intended reading: re-wrapping a paragraph does not change
  what the corpus says. It is stated here so the next person to find it knows it was chosen.
- **The frozen-set guard's own gap is now covered by tests.** 4.15 recorded that
  `src/mycelium/config.py` was missing from `check_frozen_release_sets.py`'s `TUNING_PATHS`,
  which let a single change flip a shipped default *and* re-judge the set measuring it. PR
  #61 added the path; `tests/test_frozen_release_sets.py` is what keeps it, along with the
  assertion that every guarded path still exists — a guard naming a file that moved guards
  nothing, silently.

## References

- Spec 04 §7.1 (the frozen release set), §7.3 (the gate table).
- [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md) — why
  comparability is checked at all, and why the fingerprint must be identity-free.
- [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md) — the chunking change this gate
  could not see, with the numbers 4.15 has to hold.
- [ADR-0029](0029-let-a-judgment-name-a-section.md) — judgment durability across a re-cut,
  the other half of making 4.15 safe.
- `tools/stamp_baseline_fingerprints.py` — the migration, and the check it refuses on.
