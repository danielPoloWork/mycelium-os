# ADR-0112: Date the baseline to a release, because the drift it records is the incumbent's

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.3
- **Related:** [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) (which set a gate can live
  on, and the clause this narrows), [ADR-0056](0056-make-the-format-assignment-append-only.md)
  (a bless never rides with a retrieval change),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) (the decay instrument this completes),
  [ADR-0110](0110-drop-the-markup-and-keep-the-words-on-evidence-a-placeholder-cannot-forge.md)
  (the change that disarmed G3 here, and the session this misled),
  [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md) (why the corpus
  excludes what it does); D-010; spec 04 §7.3; roadmap 4.17, 5.40, 5.42

## Context

Roadmap 5.42 carried two halves. The first is bookkeeping: 5.40 moved chunk text, gate G3
disarmed itself on `uv/release`, and ADR-0056 forbade re-blessing in the same PR. The second is
the one worth deciding — **what our own `ours/release` baseline is for**, given that it had
drifted 0.5232 → 0.5206 on us and **0.2842 → 0.2466 on the incumbent** with nobody's change
responsible.

The item offered two answers: re-bless on a stated cadence, or keep the baseline old *because*
the drift is the signal and make the verdict say so. It also said, correctly, that leaving it
to be re-blessed whenever somebody notices is not an answer.

### What the drift actually is

Measured with `tools/measure_slice_decay.py` against `69a433a`, the commit that last blessed
this baseline — the corpus grows 157 → 173 documents, and the judgements, the compiler and the
scorer are all held at today's:

| arm | ours/release | recall@50 |
|---|---|---|
| mycelium | 0.5238 → **0.5209** (−0.0029) | 0.853 → 0.824 |
| grep | 0.2842 → **0.2466** (−0.0376) | 0.618 → 0.618 |
| **lead** | **+0.2396 → +0.2744** | |

**The whole of the drift is the incumbent's, and it is the product's own claim arriving as a
regression report.** Sixteen documents diluted a term-counting baseline by 13 % and left ours
within half a percent — which is precisely what `tests/test_eval.py`'s fairness guard has
recorded across five releases, and precisely what D-010 says this project exists to demonstrate.
Read against a stale baseline, that shows up in G3's verdict as *our* numbers falling.

It is not hypothetical that this misleads. At 5.40 the session that measured a compiler change
read `ours/release` against this baseline, saw grep collapse and `r-0015` go 1.0000 → 0.6309,
and came within one paragraph of attributing all of it to the change under test. What separated
them was building a controlled arm by hand. The decay instrument now names the same two cases —
`r-0015` first-judged-hit 1 → 2, `r-0019` 4 → 5 — as corpus growth, by ref.

### The instrument that was supposed to answer this could not

ADR-0044 built `measure_slice_decay.py` to be *"the instrument G3 cannot be"*: it holds the
judgements and the code fixed and varies only the corpus. It scored **one arm**, through a
direct `store.search_chunks` call, so it could say what growth did to us and had nothing to say
about the incumbent — the arm that moves four times as far. A tool built to answer "corpus or
code?" was blind to the larger half of the answer.

## Decision

**`ours/release` is re-blessed once per release, as its own PR, in the release procedure's
pre-flight — and this change is the first application of that cadence.** The step is written
into [`docs/workflow/release.md`](../workflow/release.md) with the two-run rule beside it, so it
has an owner and a moment rather than depending on somebody noticing.

**The rejected alternative is the "drift is the signal" reading, and ADR-0044's tool is why.**
Keeping the baseline old to detect slow decay was a real argument when roadmap 4.17 found
`relationship` halved between two blesses — but the answer to that finding was an instrument,
and the instrument can target *any* ref on demand. A baseline can record drift only since
whenever the last bless happened to be, which is an interval nobody chose. Given a tool that
answers "since v0.3.0" or "since any commit", a baseline that is merely old is a worse version
of it that also makes G3's standing report unreadable.

**`measure_slice_decay.py` gains `--retriever`, and both arms now go through
`build_retriever`.** Without it the decision above could not have been argued, because the
number that decides it is the incumbent's. Stated precisely, because the temptation is to
overclaim: the direct call it replaced already agreed with the harness to four decimals on
every slice, so nothing it printed was wrong. What changes is that the agreement is structural
rather than coincidental, and that the tool can now be asked about the arm that matters.

**ADR-0053's "what it must never be is stale" is kept and given a meaning.** That ADR was right
that a report is only worth reading against numbers someone meant; what it did not say is
*when* someone means them. Now: at each release, against that release's corpus.

**`uv/release` is re-blessed in the same PR**, which is the bookkeeping half. It carries no
judgement and no retrieval change — the sets, the corpus and the code are identical to the
commit before it — so the two blesses cannot interact.

## Alternatives Considered

- **Keep the baseline old; make the verdict explain the drift.** The item's other answer.
  Rejected on the measurement above: no wording makes a delta that mixes dilution with change
  interpretable, because separating them requires a second corpus, which is the decay tool's
  whole method. It would also have needed a change inside `src/mycelium/eval/` — a tuning path
  — which ADR-0056 forbids in a PR that blesses. The wording that *would* help is naming the
  release the baseline describes, and that follows from the cadence rather than replacing it.
- **Re-bless on every PR that moves the corpus.** Rejected: that is the behaviour G3's refusal
  to enforce across a corpus change exists to prevent ([BUG-0014]), and it would make the
  per-case record meaningless by resetting it continuously.
- **Re-bless on a fixed date cadence** (monthly, say). Rejected: the corpus moves with releases,
  not with the calendar, and a release is a moment that already has a procedure, a version to
  name and a maintainer performing it.
- **Archive the superseded baseline so the long record survives.** Attractive, and refused as
  scope creep with a weak motive: git holds every superseded baseline already, and
  `measure_slice_decay.py <ref>` reads any of them. A second copy in the tree would be a
  history file nobody diffs.
- **Drop the `ours/release` baseline entirely**, since G3 only reports on it. Rejected:
  ADR-0052 put per-case scores in it, and per-case numbers are how a slice mean is read
  (ADR-0044, ADR-0058). What it needed was a date, not a deletion.

## Consequences

- **`uv/release` re-blessed, and nothing moved.** Both arms — `mycelium` **0.613833** and
  `grep` **0.532054** — byte-identical per slice and per case to the values blessed at
  `b4bc729`; only `blessed_from_snapshot`, `corpus_digest` and `content_digest` change. That is
  what 5.40 predicted, and if it had moved a number this ADR would be reporting a finding
  instead. Gate G3 is armed again on the only set that enforces it.
- **`ours/release` re-blessed as the first application of the cadence**, and it absorbs exactly
  the drift measured above: `mycelium` 0.523178 → **0.520949**, `grep` 0.284211 → **0.246565**.
  Three of our cases move (`r-0004`, `r-0006`, `r-0008`, none by more than 0.03) and two of the
  incumbent's carry its whole fall — `r-0015` 1.0000 → 0.6309 and `r-0019` 0.3216 → 0.0507,
  the same two the decay tool attributes to corpus growth by rank. From here the reported delta
  describes one release of growth rather than four.
- **The baseline now describes the corpus including this PR's own ADR and roadmap entry**, which
  is unavoidable on a self-hosting corpus and is the standing state ADR-0053 named. It is stated
  rather than hidden.
- **`measure_slice_decay.py` can score either arm**, and the incumbent's decay — the larger,
  previously invisible half — is one command away:
  `python tools/measure_slice_decay.py <ref> --retriever grep`.
- **A limit, stated:** the cadence binds the *release*, not every reader. Between releases the
  reported delta still mixes growth with change, and the honest way to attribute a change
  remains the controlled arm — build the same corpus with and without it. This ADR shortens the
  interval; it does not make the delta a substitute for the experiment.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.3 (gates, baselines).
- Decision log: D-010 (the incumbent is the bar, and the corpus is not to be fitted).
- Re-runnable: `python tools/measure_slice_decay.py 69a433a --set release --retriever grep`,
  and the same without `--retriever` for our own arm.
- The fairness guard that records the same dilution across five releases:
  `tests/test_eval.py::test_the_grep_baseline_is_fair`.
