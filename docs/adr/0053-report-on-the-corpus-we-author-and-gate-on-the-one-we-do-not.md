# ADR-0053: Report on the corpus we author, gate on the one we do not

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.22; RFC-0001; spec 04 §§7.1, 7.3, 7.5; D-010;
  [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md);
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md),
  [ADR-0051](0051-hold-the-judgements-fixed-too.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md)

## Context

Gate G3 enforces a −2 % per-slice regression threshold, and it enforces only when the run
and the baseline are comparable: the same documents (`content_digest`, ADR-0045) and the
same judgements (`cases_digest`, ADR-0051). Otherwise it reports and names what changed.

That guard is right, and on **this repository's own release set it can never be satisfied.**
This project's documentation *is* its corpus — every PR here adds an ADR, a journal entry, a
CHANGELOG line — so `content_digest` moves on nearly every change. `eval/baselines/release.json`
has therefore carried per-slice numbers that CI has never once enforced, and could not.

`tools/stamp_baseline_fingerprints.py` said so out loud when it refused this corpus at
roadmap 4.13: the chunk fold had moved since the bless, so the numbers described a corpus
that no longer existed. What made that a decision rather than a maintenance chore is the
second half: the deltas G3 *reports* were measured against those same stale numbers. A
report against a corpus that no longer exists is not a weaker measurement — it is a number
that looks like one.

Two facts made the drift concrete rather than theoretical. `exact` read
`0.9833 -> 0.7560 (-23.1%)`, which reads exactly like a regression and is not one: the slice
held **one** case at the bless and holds four now (roadmap 4.20), and the case the 0.9833 was
measured on reads **0.9942** today. And the vendored baselines — the ones G3 *does* enforce
on — were blessed before roadmap 4.19's stemming index, which moved every release set up by
nine to eleven points. So the only enforcing gate in the project was carrying nine points of
headroom: a change that gave the whole stemming gain back would have passed it.

## Decision

**G3 reports on the set whose documents we author, and enforces on the sets we do not.**
That is the contract, stated rather than left to be deduced from three digest comparisons:

| release set | corpus | G3 |
|---|---|---|
| `eval/release.jsonl` | this repository's documentation, authored in this repository | **reported** |
| `eval/corpora/uv-docs/eval/release.jsonl` | vendored, frozen | **enforced** |
| `eval/corpora/uv-docs-ingested/eval/release.jsonl` | derived from the vendored corpus, frozen | **enforced** |

**Our baseline stays committed, and is re-blessed deliberately.** It is not only G3's
threshold: since ADR-0052 it carries the per-case scores behind every slice mean, and that is
the only continuous per-case record of our own corpus there is. What it must never be is
stale — a report is only worth reading against numbers someone meant. So a re-bless is its
own PR, carrying the per-slice diff in its body, and it never rides along with a retrieval
or a judgement change.

**All three baselines are re-blessed here, against the retriever that actually ships.** Ours
because it described a vanished corpus; the vendored two because they predated ADR-0048 and
were quietly granting the gate headroom.

**The compensation for the reported set is named where it is met.** `mycelium eval`'s verdict
now says that where the documents are authored in the same repository, the report branch is
the *standing* state rather than a transient one — the sentence that stops a permanent
report reading as a gate. The instrument that asks the regression question there is
`tools/measure_slice_decay.py` (roadmap 4.17), which holds the judgements and the compiler
fixed and varies only the corpus. It stays out of the product's own output: it is this
repository's script, not something an installed user has.

## Alternatives Considered

- **Stop committing our baseline.** The item's other option, and the tempting one: a file
  that can never gate is a file that misleads. Rejected because deleting it deletes the
  *report* too, and with it ADR-0052's per-case history — one milestone after that history
  was built. The failure this project has actually had is a decay crossing several
  milestones unremarked (`relationship`, 0.304 → 0.106, roadmap 4.17), and the answer to
  that is a truer continuous record, not none.
- **Make G3 enforce on our set anyway**, by comparing only the slices whose cases' documents
  did not change. Rejected: a slice mean's denominator is the slice, not the document, so
  the comparison would still be over a corpus where competing documents arrived — the
  ranking effect that moves scores most. It would trade an honest abstention for a
  plausible-looking number.
- **Exclude our own documentation from its own corpus** so the corpus stops moving.
  Rejected: self-hosting is the product's own dogfood claim and its TTFV story (NFR-4). The
  corpus moving is the point.
- **Declare enforcement in the baseline file** — an `enforcement: "reported"` field written
  at bless time. Rejected as a mechanism that changes no behaviour: G3 already computes the
  answer from the digests, and a second, hand-maintained source of the same truth is a
  thing to get out of sync. The distinction is a property of the corpus, and it is recorded
  where properties of corpora are recorded — here, and in `eval/README.md`.
- **Re-bless ours together with a retrieval change**, saving a PR. Rejected by spec 04 §7.1's
  own discipline and by this project's history: a bless that rides along cannot be read as
  either a measurement or a decision.

## Consequences

- **Ours/release is honest again.** Overall `0.4499 → 0.4982`; `conceptual` (0.4507 →
  0.4921) and `fact` (0.4354 → 0.4602) move up on unchanged populations, `relationship`
  moves up on the two cases it already held (0.1064 → **0.3013** on r-0006 and r-0011), and
  `exact` moves down (0.9833 → 0.7593) only because it went from one case to four. Every
  number is now a number someone meant.
- **The decision demonstrated itself inside its own PR, and the effect is measured.** The
  first bless here was taken before this ADR and its journal entry were written. Adding them
  — *one* document and eight chunks to a 115-document corpus — moved four per-case scores and
  both overall means: ours `0.4998 → 0.4982`, the incumbent's `0.3332 → 0.3306`, `r-0019`
  0.4777 → 0.4375 as the new ADR competes with the documents its case names. Nothing about
  retrieval changed. That is the whole argument for this decision, produced by accident: a
  −0.3 % move from writing the ADR that explains why the gate cannot enforce here. It also
  means the committed baseline is one documentation edit behind the tree that merges it, so
  CI will *report* on our set in this very PR — which is the contract, working.
- **The enforcing gate lost its headroom.** `uv/release` mycelium goes `0.4920 → 0.5483`
  and `uv-ingested/release` `0.5911 → 0.6469`, with no slice down on either. From here, a
  change that gives back the stemming gain fails G3 instead of passing it. Every one of
  `uv/release`'s grep scores is identical before and after — the check that the frozen
  corpus really is frozen, and that the incumbent does not read our index.
- **`uv-ingested/release` gains a grep entry** it never had, so the third corpus can report
  against the incumbent like the other two.
- **One case is now visibly unserved.** `r-0018` ("can an agent keep querying while a build
  is running") scores **0.0000**: its two documents state the two halves of the answer and
  the query uses neither's noun. It was added at 4.20 and nothing recorded its score; the
  per-case baseline records it now. It is the named instance roadmap 5.3's graph-expansion
  ablation exists to move, and it is *not* roadmap 4.23's inflection failure — every word in
  that query appears in the corpus as spelled.
- **G3's verdict is longer by one sentence** on the report branch, and a test asserts it. The
  cost of stating the standing state is that the sentence appears on every non-comparable
  run; the alternative is a reader inferring permanence from three digests, which is the
  inference nobody makes.
- **A re-bless is now a documented, repeatable act** rather than a judgement call: its own
  PR, per-slice diff in the body, and no retrieval or judgement change alongside.
- **Set size remains the real limit.** Four slices on the vendored sets still cannot carry a
  gate (ADR-0052), so "enforced" means one slice on each of them today. That is spec 04
  §7.6's target at 1.0 and roadmap 4.26's to grow — this ADR fixes which *sets* a gate can
  live on, not how thin their slices are.

## References

- Spec 04 §7.1 (frozen release sets), §7.3 (the gates), §7.5 (run manifests).
- Measured this session, on `main` at `ff7777d`: the three per-slice diff tables above, and
  `exact`'s per-case attribution (`r-0003` 0.9942 today against the 0.9833 it was blessed at
  alone).
- [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md) — what comparability
  means, and why the chunk fold was the wrong question.
- [ADR-0051](0051-hold-the-judgements-fixed-too.md) — the second variable a baseline must fix.
- [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) — the per-case scores this decision
  keeps the baseline for.
