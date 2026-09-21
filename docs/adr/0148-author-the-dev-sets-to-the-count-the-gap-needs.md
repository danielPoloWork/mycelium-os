# ADR-0148: Author the dev sets to the count the gap needs

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 04 §§7.1, 7.6
- **Related:**
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) (the
  split this serves: a dev set is reported, never gated, and the number a reviewer reads
  is the *gap*),
  [ADR-0136](0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md) (roadmap
  6.8, which authored the three release sets and filed this),
  [ADR-0123](0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md)
  (`enforceable_at`, the arithmetic this borrows),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) (what a thin slice
  can and cannot say),
  [ADR-0067](0067-grow-the-dev-set-before-asking-it-a-question.md) (the road: written
  from the documents, committed before anything is scored on them),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md),
  [ADR-0101](0101-let-the-exact-slice-name-the-section-that-documents-the-literal.md),
  [ADR-0065](0065-one-section-cannot-document-two-commands.md),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (the grading conventions every new
  case follows),
  [ADR-0039](0039-measure-what-projection-costs.md) (the carry, unchanged),
  [ADR-0056](0056-rotate-the-ingested-corpuss-formats-over-a-recorded-order.md) (the
  append-only format rotation this change deliberately does not grow); D-010;
  spec 04 §§7.1, 7.6; roadmap 6.8, 6.33

## Context

ADR-0027 split every corpus into a `dev.jsonl` and a `release.jsonl`. The release set is
what CI gates; the dev set is scored beside it and **reported, never gated**, so a run
prints the gap between the set tuning may read and the set it may not. No threshold ships
— nobody has the evidence to set one — so the gap is a number a reviewer reads, and the
only thing it has to be is *legible*.

Roadmap 6.8 authored the three release sets to the count `enforceable_at` derives for
them, taking them from 19/25/25 cases to 286/404/404, and left the dev sets at 20, 22 and
22. That was the right split, and ADR-0136 said why: enforcement comes from the release
sets, and doubling a 646-judgement review surface to get a *reported* number is not a
trade worth making in one change. What it left behind is what this item measures.

**Measured before deciding anything.** Scored on a clean checkout of `origin/main`, at
the committed defaults, all three corpora:

| set | dev nDCG@10 | release nDCG@10 | gap |
|---|---:|---:|---:|
| this project's docs | 0.4685 (20 cases) | 0.4785 (286) | **−0.0100** |
| `uv` docs | 0.6143 (22) | 0.6903 (404) | **−0.0760** |
| `uv` docs, projected | 0.6127 (22) | 0.6477 (404) | **−0.0350** |

Two things are wrong with that table, and neither is about retrieval.

**One: the gap has changed sign since the split was built, and not because overfitting
reversed.** ADR-0027 measured **+0.115** and **+0.153** — retrieval scoring about a
quarter worse on cases it had never been tuned against, which is exactly what the split
was for. Every gap above is *negative*. Nothing about tuning explains that. What happened
is 6.8: the release sets were re-authored from the documents at ten to sixteen times their
old size, while the dev sets stayed the cases frozen on 2026-08-31. **The gap currently
measures the difference between two differently-authored sets, not the difference between
a set tuning read and one it did not.**

**Two: per slice, one case is worth more than the whole number being reported.** The
resolution of a slice's mean is what ADR-0044 named — a slice of `n` cases moves in steps
of one case's swing over `n` — and `enforceable_at` already writes down what a typical
answered case is worth (`q`, the median non-zero per-case score). Against the gap each
row reports:

| set | slice | dev cases | gap | one case is worth | as a multiple of the gap |
|---|---|---:|---:|---:|---:|
| ours | conceptual | 5 | +0.0259 | 0.1306 | **5.0×** |
| ours | exact | 2 | +0.2295 | 0.3704 | **1.6×** |
| ours | fact | 4 | −0.0950 | 0.2039 | **2.2×** |
| ours | relationship | 2 | +0.0337 | 0.2082 | **6.2×** |
| uv | conceptual | 4 | −0.0218 | 0.2500 | **11.5×** |
| uv | exact | 4 | +0.0964 | 0.2500 | **2.6×** |
| uv | fact | 5 | +0.2240 | 0.2000 | 0.9× |
| uv | relationship | 4 | −0.4857 | 0.0254 | 0.05× |
| uv | symbol | 4 | −0.1859 | 0.1039 | 0.6× |
| uv-ingested | conceptual | 4 | +0.0916 | 0.2039 | **2.2×** |
| uv-ingested | exact | 4 | +0.1506 | 0.2500 | **1.7×** |
| uv-ingested | fact | 5 | +0.2513 | 0.2000 | 0.8× |
| uv-ingested | relationship | 4 | −0.5262 | 0.0469 | 0.09× |
| uv-ingested | symbol | 4 | −0.1002 | 0.1049 | **1.0×** |

**Nine of the fourteen rows report a gap that a single case could erase or reverse.** The
worst is `uv`'s `conceptual`, where one of four cases is worth eleven and a half times the
overfitting signal its row prints. `exact` on our own set prints **+0.2295** — a
twenty-three-point overfitting signal — off two questions. These are the rows a reviewer
is being invited to read, and ADR-0044 already showed what arithmetic like that is worth.

## Decision

**Each dev slice is authored to the count `enforceable_at` derives for the release slice
it is subtracted from.** Nothing else about the instrument moves: no bar is re-cut, no
threshold is invented, and no gate changes what it enforces.

The count is *derived, not guessed*, and it is read from a frozen baseline — the property
`enforceable_at`'s docstring insists on, for the reason it gives: a requirement computed
from the run under test is gameable in the one direction that matters. A dev set has no
baseline of its own, because it gates nothing; the release baseline is therefore both the
only frozen thing available and the right thing to read, because **the gap is a
subtraction against exactly that row**. Sizing the dev slice to the release slice's count
makes the two sides of the subtraction equally precise, so the gap inherits the release
row's resolution instead of the dev row's much coarser one. No new constant is introduced
to achieve that.

Where the two `uv` corpora disagree on a slice's count, the larger is used, because one
set of judgements is carried to both.

| set | cases before | cases after |
|---|---:|---:|
| `eval/dev.jsonl` — this repository's documentation | 20 | **239** |
| `eval/corpora/uv-docs/eval/dev.jsonl` — documentation we did not write | 22 | **333** |
| `eval/corpora/uv-docs-ingested/eval/dev.jsonl` — the same, projected | 22 | **329** |

**Every case was written from the documents, and the anchors were read rather than
retrieved.** The discipline is ADR-0067's and ADR-0136's, unchanged: the query is phrased
the way a reader would ask it, the anchor is chosen by opening the document, and no
candidate retriever was consulted at any point. The generators validate every anchor
against a real build before either set can be written, so a case naming a passage the
corpus does not hold cannot be committed.

**The grading conventions are the ones already on the record.** A `symbol` judgement names
the section that documents the named thing, with a framing page a 2 and a list entry a 1
(ADR-0062, ADR-0065); an `exact` judgement names the section that documents the literal,
not every section containing the string (ADR-0101); a judgement may name a section rather
than a chunk where the answer is spread across it (ADR-0029).

**`unanswerable` and `injection` are not grown.** `unanswerable` is reported by design and
gated by G4, not by the per-slice condition, so it has no gap to power; `injection` is a
single standing probe. Both keep the cases they have.

**Our own dev set gains no `symbol` cases.** Our release set has no `symbol` row — ADR-0136
declined to add one — so there is no release slice to subtract from and therefore no gap
to make legible. The three standing `symbol` cases stay as the corpus's symbol evidence.

**The `uv` dev cases are authored inside the 66 documents that already hold a format
slot**, and unlike 6.8 that costs nothing. The twin's format assignment is an append-only
rotation, and a newly judged document takes a slot and must be rendered (ADR-0056); 6.8
rightly refused to keep its judgements inside the 29 documents that had slots, because
that was a third of the corpus and concentrating judgements there would have fitted the
judgements to the instrument. After 6.8 the rotation holds 66 of the corpus's 82
documents, and of the sixteen left out, **fifteen are navigation stubs** — one heading,
between 5 and 45 lines, mostly link lists — and the sixteenth is `docs/index.md`, which
ADR-0136 deliberately left unjudged so that roadmap 5.40's inline-HTML claim keeps its
only test site. The new cases judge **all 66**, so no document is re-rendered and no
committed binary moves.

**The twin is carried, not re-judged**, exactly as ADR-0039 requires: a judgement written
against the projection cannot measure what the projection costs.

## Measured

**The corpora were held fixed and only the judged sets varied.** The after run re-scores
against the same builds the before run used, in the same clean checkout, so nothing in
these two tables moves for any reason except the cases.

| set | dev before | dev after | release | gap before | gap after |
|---|---:|---:|---:|---:|---:|
| ours | 0.4685 (20) | **0.6056 (239)** | 0.4785 (286) | −0.0100 | **+0.1271** |
| `uv` | 0.6143 (22) | **0.7395 (333)** | 0.6903 (404) | −0.0760 | **+0.0492** |
| `uv` projected | 0.6127 (22) | **0.7189 (329)** | 0.6477 (404) | −0.0350 | **+0.0712** |

**Every row now reports a gap bigger than one case can move.** That is the whole of what
this item was for, and it is the one number worth quoting: what a typical answered case is
worth, as a multiple of the gap its row prints, was above 1.0 on **nine of fourteen rows**
and is now above 1.0 on **none of them** — the worst row is `exact` on the projected
corpus at 0.92, and eleven of the fourteen sit at or below 0.3. `uv`'s `conceptual` row,
which printed an overfitting signal one of its four cases was worth **eleven and a half
times over**, now holds 74 cases and one of them is worth 0.16 of what the row reports.

**The sign is back where ADR-0027 found it.** All three gaps are positive again, and our
own set's **+0.1271** sits close to the **+0.115** that ADR measured in 2026-08-31 before
either set had been re-authored. That is a *consistency* result, not a discovery.

**What this measurement cannot say, and the check that was run anyway.** The dev sets are
newly authored and have never been tuned against, so a positive gap today is not evidence
of overfitting — it is the baseline the gap will be read against from here. The obvious
alternative explanation is that this pass wrote *easier* cases than 6.8 did: several
authoring agents reported deliberately avoiding answers buried deep inside long sections,
which would bias the dev sets toward passages that are easy to retrieve. That was checked
rather than assumed, by comparing where each set's grade-3 anchors sit:

| set | grade-3 anchor is the section's first chunk | a section | a deeper chunk |
|---|---:|---:|---:|
| ours, dev (new) | 96.2 % | 3.0 % | 0.9 % |
| ours, release (6.8) | 92.6 % | 2.8 % | 4.6 % |
| `uv`, dev (new) | 95.8 % | 4.2 % | 0.0 % |
| `uv`, release (6.8) | 97.3 % | 2.7 % | 0.0 % |

The distributions are close, and on the `uv` corpus the *dev* set is marginally the deeper
anchored of the two while still scoring higher. **Anchor depth does not account for the
gap**, which is a measured negative rather than a reassurance: some other difference
between two authoring passes may. The honest reading is that the gap is now legible, its
sign agrees with the only prior measurement, and its *movement* — not today's value — is
what a reviewer should watch.

## Alternatives Considered

- **Leave the dev sets alone: they are reported, so who cares.** Rejected because a number
  nobody can read is worse than no number — it invites a reviewer to act on nine rows that
  a single case could reverse. ADR-0027 declined to gate the gap precisely so that it
  would be *read*, and that only works if it means something.
- **Pick a round number — fifty a slice, say — and author to it.** Rejected on D-011 and on
  this project's own habit: a constant chosen to look decisive is what ADR-0025 refused and
  what ADR-0123 replaced for the release sets. The count is derived from the row the gap is
  subtracted from, so it is a property of the comparison rather than of the author's taste.
- **Derive the count from the dev set's own numbers.** Rejected: a dev set has no frozen
  baseline to read, because it gates nothing, so the only numbers available are the ones
  from the run being judged — the exact input `enforceable_at` refuses, and for the reason
  it gives.
- **Grow `unanswerable` to match.** Rejected: it scores 0.0000 by construction, so it has
  no gap to make legible, and G4 is what gates abstention.
- **Add a `symbol` row to our own dev set.** Rejected for ADR-0136's reason, inverted:
  there is no release `symbol` row on that corpus to compare against, so the cases would
  print a gap against nothing.
- **Judge the sixteen `uv` documents that hold no format slot, for coverage.** Rejected:
  fifteen are single-heading navigation stubs of 5 to 45 lines, and judging them would
  extend the append-only rotation and force fifteen renders to buy nothing. The sixteenth,
  `docs/index.md`, is deliberately unjudged and ADR-0136 says why.
- **Re-judge the twin's carried dev cases against the projected documents** so that the
  four cases lost in the carry survive. Rejected on ADR-0039's standing argument, which
  this change does not reopen.

## Consequences

- **The gap is an instrument again, on all three corpora.** Fourteen of fourteen comparable
  rows now report a number larger than one case can move, against five of fourteen before.
- **Gate G2's verdict is re-recorded, and the default could not have moved.** `SETS` in
  `tools/measure_hybrid_gate.py` is `("dev", "release")`, so the recorded verdict carries a
  digest of every dev set and growing them stales it — `--check` fails on `uv/dev` and
  `uv-ingested/dev` until it is re-run. But the *profile* is decided by the release rows
  alone (`decision_of` filters to `/release`, because "dev rows do not vote"), so no dev
  set can change what ships.
  The re-record refreshes the digests and the reported dev columns; `lexical` remains the
  default for exactly the reasons ADR-0136 recorded. The re-record doubles as a check that
  nothing else moved: on the two corpora this change does not touch, the release rows come
  back **identical to ADR-0136's** — `uv/release` **+7.2 %** with the same `exact` slice
  paying, and `uv-ingested/release` **+3.5 %**. Our own `release` row reads **+21.4 %**
  against the +20.2 % recorded two days ago, which is this corpus documenting itself: the
  ADR and journal entry in this change are part of it, and `ours` is a `DATED_CORPORA` for
  that reason. The new dev rows read −1.3 % (ours), +6.7 % (`uv`) and +3.7 %
  (`uv-ingested`); none of them votes.
- **No baseline is re-blessed, because a dev set has none.** There is no `baselines/dev.json`
  anywhere in the tree: G3 compares release runs against frozen release baselines, and this
  change does not touch one. The two release sets are rewritten byte-for-byte by their
  generators, so `tools/check_frozen_release_sets.py` sees no edit and the conjunction it
  guards is not engaged.
- **The carry drops four whole cases, not just anchors**, and that is new. 6.8 reported 27
  dropped anchors with every case surviving; here 33 anchors drop and **four `uv` dev cases
  do not survive the projection** — three of them because their only grade-3 anchor is a
  section of `docs/getting-started/features.md`, the feature list the HTML lane shatters
  into a heading per item (ADR-0111's shape), and one because its section-scoped anchor
  over the Lambda Docker section has no single twin chunk. Three replacement `fact` cases
  were authored against passages that project, so the twin clears its own floor on every
  slice; the four cases are left in the source set, where they are honest questions about
  the Markdown corpus, and their loss is the projection's cost reported rather than
  repaired.
- **No document is re-rendered and no committed binary moves.** The rotation still holds 66
  entries, and the new cases judge all 66 — so the judged documents now cover the entire
  rotation rather than a part of it.
- **Spec 04 §7.6's 1.0 target is comfortably clear.** The committed sets hold **1 995 cases
  across six sets**, against 1 158 before; the target is ≥ 1 000.
- **A reviewer cannot check 530 judgements by reading them all**, and ADR-0136's answer
  still applies: what can be checked is the method, the conventions, the mechanical
  validation of every anchor against a real build, and a sample — the notes are written for
  that sample. Two mechanical properties are worth naming because they were enforced rather
  than hoped for: **no new query duplicates one already committed** on its corpus, dev or
  release, and every anchor was validated against a clean build before either set could be
  written.
- **Three queries were already in both a dev and a release set, and this change does not
  touch them.** Checking the new cases for collisions found the check was worth running on
  the standing ones too: `q-0007`/`r-0001` ("how do I report a security vulnerability"),
  `u-0016`/`u-1261` (`uv build`) and `u-0017`/`u-1243` (`uv venv`) each ask the same
  question on both sides of a split whose point is that the two sides are different
  questions. All three predate this item — 6.8 authored the release halves without checking
  against the dev sets — and all three are reported rather than repaired, because editing a
  standing judgement to tidy a number is the move `tools/check_frozen_release_sets.py`
  exists to make hard, and three collisions in 1 995 cases do not move any figure here.
- **Anchors came back section-scoped more often than the convention wants, and were
  normalised.** The authoring material listed sections rather than chunks, so 41 `uv`
  anchors arrived as section judgements where the section holds exactly one chunk; those
  were rewritten to the chunk form, which is the same judgement and the form the committed
  sets use. Ten anchors stay section-scoped, in sections that genuinely hold several chunks
  — ADR-0029's case for the notation.
- **Gate G5's tool-call sample started sampling, for the first time on this set.**
  `time_tool_call` times `TOOL_CALL_SAMPLE = 100` of a run's queries, and
  `tests/test_eval.py` asserted `tool_call.calls == overall.cases` — true only because
  every set it ran on was smaller than the sample. At 239 cases it is 100, and the
  assertion now states the contract it always meant, `min(cases, TOOL_CALL_SAMPLE)`.
  Nothing about the gate changes: it was designed to sample, and ADR-0128's reasoning for a
  hundred is about flake rather than coverage.
- **A new test pins this decision rather than its number.**
  `test_every_dev_slice_holds_the_count_its_release_row_needs` recomputes `enforceable_at`
  from each corpus's blessed release baseline and fails if any dev slice has fallen below
  it — so the rule survives the next person to edit a set, which a count written into a
  docstring would not.
- **The generators grow by roughly 6 200 lines of judgements**, which is data rather than
  code, and is the shape [BUG-0026] requires: a set edited by hand is invisible to its
  generator and deleted by the next run.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (the sets and the split), §7.6
  (the corpus plan and the 1.0 target).
- Assets: `eval/dev.jsonl`, `eval/corpora/uv-docs/eval/dev.jsonl`,
  `eval/corpora/uv-docs-ingested/eval/{dev.jsonl,carry.json}`, `eval/g2-verdict.json`;
  generators `tools/build_eval_cases.py`, `tools/build_uv_docs_cases.py`,
  `tools/build_ingested_cases.py`.
- Re-runnable: `python tools/build_eval_cases.py`,
  `python tools/build_uv_docs_cases.py --check`,
  `python tools/build_ingested_cases.py --check`,
  `python tools/measure_hybrid_gate.py --check`,
  `mycelium eval . --set eval/dev.jsonl --against grep`.
