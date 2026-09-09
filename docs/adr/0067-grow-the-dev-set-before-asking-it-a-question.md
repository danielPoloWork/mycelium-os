# ADR-0067: Grow the dev set before asking it a question, and keep the cases that embarrass it

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.39 (this item), 4.36 (where it was filed), 4.42; RFC-0001;
  spec 04 §§7.1, 7.6; D-010;
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0043](0043-judge-across-the-configurations-a-set-is-scored-under.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md),
  [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md),
  [ADR-0065](0065-one-section-cannot-document-two-commands.md)

## Context

`uv/dev` had been twelve cases since it was written: conceptual 4, fact 5, **exact 1**,
**symbol 1**, unanswerable 2, and **no `relationship` case at all**. A set that thin is flat
under a ranking change by construction, and the consequence was concrete rather than
theoretical — ADR-0058 found *every* safe setting of the heading family scoring **exactly**
the baseline on it, so ADR-0063 could ship the one parameter `ours/dev` could see and had to
refuse the other. The refused one was priced: `heading 3.0/0.5` and `4.0/0.5` pass gate G3 on
both frozen release sets and are worth uv/release 0.611 and 0.616 against the shipped 0.604 —
three to four times the split's own gain — and they could not be *proposed* because no dev
set could see them.

Spec 04 §7.6 wants ≥ 60 judged cases by Phase 1 and ≥ 200 by Phase 3; ADR-0052 arms a slice
at four cases. This item is the release side's work done for dev.

## Decision

**Ten cases, written from the documents, committed before anything was scored on them.**

The commit order is the evidence and it is visible in the branch: the first commit adds the
cases and scores nothing; the second measures. Nothing about any candidate informed which
cases were written — they were selected by *slice definition* and by which slices were thin,
which is a mechanical criterion a reviewer can check:

| slice | was | now | what was added |
|---|---:|---:|---|
| `exact` | 1 | **4** | `UV_PREVIEW`, `--bare`, `UV_PROJECT_ENVIRONMENT` — rare literal tokens, each with one dominant home in the corpus |
| `symbol` | 1 | **4** | `uv build`, `uv venv`, `uv init` — bare command names |
| `relationship` | 0 | **4** | two ideas the corpus states in two places |
| conceptual / fact / unanswerable | 4 / 5 / 2 | unchanged | already at or above the threshold |

Graded on the conventions already in force: the section that documents the thing at 3, the
section that frames or teaches it at 2, a feature-list entry at 1 (ADR-0062, ADR-0065), and
section-scoped wherever the chunk is large enough that another chunking setting would split
it (ADR-0043). Every judged anchor was verified to resolve against the built corpus. Eight of
the ten name documents that carried no judgement before, taking coverage from 20 of the
corpus's 81 documents to 26.

**The item's question is answered: the dev set can now see the leaf weight.**

| setting | uv/dev nDCG@10 | MRR | R@10 |
|---|---:|---:|---:|
| `heading 2.0/2.0` *(unsplit)* | 0.607 | 0.629 | 0.692 |
| `heading 2.0/0.5` *(ships)* | 0.609 | 0.630 | 0.692 |
| **`heading 3.0/0.5`** | **0.614** | **0.632** | **0.717** |
| `heading 3.0/1.0` | 0.612 | 0.631 | 0.717 |
| **`heading 4.0/0.5`** | **0.599** | 0.607 | 0.717 |
| `heading 3.0/3.0` | 0.573 | 0.573 | 0.717 |
| `heading 4.0/4.0` | 0.550 | 0.544 | 0.717 |

At twelve cases every one of the safe rows read 0.673 — the same number to three decimals. At
twenty-two the leaf weight has an **interior optimum**: 3.0 beats the shipped 2.0 and 4.0 is
*worse than the baseline*. That second half matters more than the first, and it points the
opposite way to the release sets: `4.0/0.5` is the **better** setting on uv/release (0.616
against 3.0/0.5's 0.611), and the grown dev set **refuses it**. A dev set that only ever
agreed with the held-out sets would be worth nothing.

**Nothing is shipped here.** This is a judgements change; the leaf weight is a retrieval
change, and the value of the commit order is destroyed if the set is grown and the candidate
it enables lands in the same PR. Filed as roadmap 4.42.

**And the four `relationship` cases are kept although they score 0.090.** They are the
uncomfortable part of this ADR and the reason it is worth reading.

## The mistake in four of the ten, kept rather than corrected

Measured after committing, the new cases split sharply:

| case | slice | ours | grep |
|---|---|---:|---:|
| `u-0013` `UV_PREVIEW` | exact | **1.000** | 1.000 |
| `u-0014` `--bare` | exact | **1.000** | 1.000 |
| `u-0015` `UV_PROJECT_ENVIRONMENT` | exact | **1.000** | 1.000 |
| `u-0016` `uv build` | symbol | **0.947** | 0.389 |
| `u-0017` `uv venv` | symbol | 0.459 | 0.047 |
| `u-0018` `uv init` | symbol | 0.319 | 0.124 |
| `u-0019` lockfile / other tools | relationship | **0.000** | 0.000 |
| `u-0020` arbitrary environments | relationship | 0.262 | 0.228 |
| `u-0021` pyproject before building | relationship | **0.000** | 0.000 |
| `u-0022` application or library | relationship | 0.098 | 0.145 |

The `relationship` slice reads **0.090 against grep's 0.093** — neither retriever can serve
it, so as a *discriminator* it is nearly dead, and that is my error in writing it. I took
`u-1022`'s note as the design rule — *"the query uses neither's noun"* — and applied it to all
four, which turned every one of them into a **vocabulary-gap** case: the class ADR-0025 named
as forgone and ADR-0064 found in `u-1023`. A `relationship` case should test whether the
retriever finds the section that *relates* two things; it should not simultaneously test
whether it can bridge "can another tool read" to "tool-agnostic". The release set's four do
not: `u-1009` says *lockfile* and *workspace*, `u-1022` says *project environment*.

**They are kept anyway**, and this is the decision rather than an admission. I found the
mistake *because I measured*, which is precisely the sequence the commit-order discipline
exists to distrust. Rewriting a case after seeing it score badly is indistinguishable from
fitting the set, whatever the stated reason — and "my design rule was wrong" is exactly the
reason a person fitting a set would give. Each of the four was verified against the documents
and each is correctly judged; their difficulty is therefore information, not a defect. The
numbers are on the record, and any revision belongs in a later change that starts from them.

The three `exact` cases at 1.000 are worth the same scepticism from the other side: they are
easy because the slice is *defined* as trivially retrievable, and a slice of four such cases
will not discriminate much either. What the grown set demonstrably gained is in `symbol`,
where the four cases span 0.319 to 0.947 — and that spread is what made the leaf weight
visible.

## Alternatives Considered

- **Rewrite the four `relationship` queries in the documents' vocabulary.** It would raise
  the slice, make it discriminate, and be defensible on its merits — and it is refused
  because of *when* I would be doing it. See above. The honest version of this is a separate
  change proposed from the recorded numbers, where a reviewer can see that the set moved after
  the measurement rather than before it.
- **Delete the two cases scoring 0.000.** Worse than rewriting them: it removes the evidence
  that this corpus has questions nothing serves, which is a finding ADR-0064 already
  established with `u-1023` and which two more cases corroborate.
- **Add cases to `conceptual` and `fact` too**, bringing dev to release's 25. Rejected as
  scope: both already clear ADR-0052's four, and every case added is a judgement that has to
  be defended. The item asked for the thin slices.
- **Grow `ours/dev` as well.** Rejected: it is not thin (five slices at 2–5 cases, 20 cases
  total) and it is not the set that could not see the candidate. One corpus per change.
- **Ship `heading 3.0/0.5` here, now that dev supports it.** Rejected on the discipline this
  whole item is built on. `tools/check_frozen_release_sets.py` would not stop it — it guards
  the *release* sets — and that is exactly why it has to be refused by judgement rather than
  by the tool.
- **Write the cases after measuring the candidate, to target the blind spot precisely.**
  The efficient version, and unusable: cases written to make a known candidate visible are
  cases chosen to fit it.

## Consequences

- **`uv/dev` is 22 cases and every slice but `unanswerable` is at four or more** — the
  threshold ADR-0052 arms a slice at. `uv-docs-ingested/dev` follows mechanically at 22:
  `build_ingested_cases.py` carried 62 anchors and dropped 3 (the feature-list mentions, at
  coverage 0.39–0.42, the same tier it already dropped for `u-1007`), and `--check` reproduces
  the result byte-for-byte.
- **The dev/release gap has closed on this corpus**, from +0.069 to **+0.005** (uv/dev 0.609
  against uv/release 0.604). A dev set materially easier than the held-out set is a dev set
  that flatters every candidate; that property is gone.
- **uv/dev's headline number falls, 0.710 → 0.609.** Nothing regressed — the new cases are
  harder than the old twelve, which is what a set written from the documents rather than from
  the retriever's strengths looks like.
- **Roadmap 4.42 is filed** with the numbers: `heading 3.0/0.5` now has dev support and
  `4.0/0.5` is refused by the same measurement. It is a *retrieval* change and its own PR.
- **Growing a *dev* set re-rendered six documents in the ingested twin, and that disarmed
  G3 there.** This is 4.26's coupling arriving from the other side and it was not anticipated
  when the item was written. The third corpus assigns `docx`/`html`/`pdf` in rotation over the
  **judged** documents and everything else is HTML (ADR-0039, ADR-0056); nine of the ten new
  cases name documents that were previously unjudged distractors, so six of them appended to
  `format-rotation.json` and took a real format (three were already in the format their slot
  assigned). Append-only did its job — nothing already rendered moved, `docx`/`html`/`pdf`
  going 10/62/9 — but six documents' chunks changed, which moves the ingested corpus digest
  and switches G3 from enforcing to reporting.

  So the bless rides with this change, which is what ADR-0056 requires on an enforced set
  rather than an option: **uv-docs-ingested/release 0.630621 → 0.634104**, three cases moved
  (`u-1021` 0.289 → 0.315, `u-1004` 0.431 → 0.387, `u-1022` 0.787 → 0.885), and the worst
  slice movement is **`fact` −1.20 %** — inside G3's −2 % bar, so the gate would have passed
  had it been able to compare. `exact` +0.6 %, `relationship` +3.9 %, the rest unchanged. The
  ingested *dev* set falls 0.596 → 0.548 for the same reason, which is the price of the six
  documents being read from DOCX and PDF instead of HTML.

  The Markdown corpus's release set is untouched and G3 still **enforces** on it: *"same
  corpus, same boundaries, same judgements, no enforced slice regressed."*
  `check_frozen_release_sets.py` passes — no release set's judgements changed, and a bless is
  not a retrieval change.
- **Neither dev set carries a baseline**, so G3 reports "nothing to regress against" on them
  as it always has.
- **A case-design rule is now written down** in `eval/README.md`, pointing here: a
  `relationship` case relates two things, and making it *also* a vocabulary-gap case tests
  two failures at once and discriminates neither.

## References

- Spec 04 §7.1 (the dev/release split), §7.6 (corpus plan: ≥ 60 by Phase 1, ≥ 200 by
  Phase 3); D-010.
- Measured this session, after the cases were committed:
  `python tools/measure_ranking.py` (the `heading` rows on uv/dev),
  `mycelium eval eval/corpora/uv-docs --set eval/dev.jsonl --against grep`, and the per-case
  table above.
- [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md) — where the twelve-case
  dev set was first found unable to answer a field-weight question.
- [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md) — the refusal this unblocks,
  and the plateau argument it shipped on.
- [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) — the four-case threshold.
