# ADR-0052: Give a slice cases, or stop gating it — and name the case that moved

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1, §7.3
- **Related:** [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) (the
  finding this closes), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0039](0039-measure-what-projection-costs.md),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md),
  [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md),
  [ADR-0051](0051-hold-the-judgements-fixed-too.md); D-010; roadmap 4.20, filed at 4.17

## Context

ADR-0044 measured gate G3's rows and found most of them could not carry it. Re-measured
today, on the sets as they actually stand:

| set | slice | cases | can G3 fail this row? |
|---|---|---:|---|
| ours/release | `exact` | **1** | only by that one case moving |
| ours/release | `relationship` | **2** | only by one of two moving |
| ours/release | `unanswerable` | 2 | **no** — blessed 0.0000 |
| ours/release | `conceptual` | 4 | yes |
| ours/release | `fact` | 6 | yes |
| uv/release · uv-ingested/release | `symbol` | **1** | **no** — blessed 0.0000 |
| uv/release · uv-ingested/release | `exact` | **2** | only by one of two moving |
| uv/release · uv-ingested/release | `relationship` | **2** | only by one of two moving |
| uv/release · uv-ingested/release | `unanswerable` | 2 | **no** — blessed 0.0000 |
| uv/release · uv-ingested/release | `conceptual` | 3 | barely |
| uv/release · uv-ingested/release | `fact` | 7 | yes |

Seventeen rows; **five cannot fail at all** (a relative threshold against a 0.0000 baseline
returns 0.0 or 1.0, never a negative), and of the twelve that can, **eight hold three cases
or fewer**. The verdict string said `6 slice(s) compared` regardless, which is a gate
describing its own coverage inaccurately.

Two further facts sharpen it. Our own release set is *structurally* never enforced — this
repository's documentation is its corpus, so every PR changes the corpus and G3 correctly
takes its not-comparable branch (BUG-0014, roadmap 4.22). So the rows G3 actually enforces
are the `uv` ones, and **ten of those twelve are thin or unfailable**. And a slice's ideal
score is not always high: `unanswerable` cases name no relevant anchor, so nDCG@10 is 0.0000
by construction, and a *fall* in that row would mean the system got better at staying
silent. G3 was enforcing "must not decrease" on a metric whose correct value is its floor.

The item (4.20) put two remedies: judge more cases into the thin slices, or state which
slices G3 reports rather than enforces and why.

## Decision

**Both, and the arithmetic decides which per row.**

### One — the enforcement contract, stated and implemented

G3 enforces a slice when all three hold, and *reports it by name with the reason* when any
does not:

1. **Not `unanswerable`.** That slice is gated by G4 (false-answer rate ≤ 5 %), which asks
   the question it is for. G3 never enforces it, at any case count.
2. **The baseline is above zero.** A relative threshold cannot fail a zero, so a row blessed
   at 0.0000 is reported. Leaving it in the enforced count made the gate look wider than it is.
3. **At least `MIN_ENFORCEABLE_SLICE_CASES = 4` judged cases.**

The verdict now reads `1 of 6 slice(s) enforced; reported only: conceptual (3 case(s), below
the 4 G3 enforces on); … symbol (blessed at 0.0000 …); unanswerable (reported by design …)`
instead of `6 slice(s) compared`. On `uv/release` that is a worse-looking number than the one
it replaces, and the true one: those five rows were being counted as passes.

**Four is not a statistical threshold and is not presented as one.** At fourteen-to-twenty
cases per set no honest threshold exists: with a 2 % relative bar on a mean of ≈0.4, even a
seven-case slice fires when a single answer drops one rank. Four is the point at which the
row stops being one case wearing a slice's name, it is written in one place
(`MIN_ENFORCEABLE_SLICE_CASES`) so a reader can disagree with it there, and what turns G3
into a regression gate rather than a single-case alarm is set size — spec 04 §7.6's ≥ 1 000
cases at 1.0 — not a constant chosen at this milestone.

### Two — five new judged cases, where a set could grow

Every gated slice on our own release set now holds at least four cases:

| set | `exact` | `fact` | `conceptual` | `relationship` |
|---|---:|---:|---:|---:|
| ours/release | 1 → **4** | 6 | 4 | 2 → **4** |

Judged from the documents, before any of them was run — the discipline `eval/README.md`
states and the one ADR-0044 refused to break when re-judging would have rescued a slice.

**The `uv` sets could not grow here, and the reason is a coupling nobody had walked into
yet.** Eight cases were written for them and are not in this change, because adding them
newly judges three documents (`projects/sync.md`, `projects/run.md`,
`getting-started/features.md`) — and the third corpus's format assignment is *a function of
the judged set*: judged documents take DOCX, HTML and PDF in rotation over their sorted
paths, so a judged set that grows re-rolls the format of documents already rendered. Those
renderings are committed provenance that cannot be re-derived (typst embeds a build id,
measured at ADR-0039), and re-rolling them would move the per-format projection-cost table
with them. A second obstacle sits behind it: `tools/check_frozen_release_sets.py` forbids a
derived set moving with its source, which makes the carried twin unable to follow a source
that grows at all — the deadlock 4.15 met from the chunking side, reached from the
judgement side.

Both are real design questions about the *third corpus*, not about this gate, and neither
should be settled inside a change whose subject is what G3 can enforce. They are filed as
roadmap **4.26** with the eight drafted cases as its starting point.

### Three — the gate names the case that moved

The complaint was never sensitivity; it was attribution. `relationship 0.3040 -> 0.1064` is
a sentence a reader has to go and investigate, and ADR-0044's investigation took an
afternoon. G3 now appends the cases behind any slice it reports or fails, and `--bless`
records per-case scores so the next baseline can show `r-0011 0.3951->0.0000` rather than
today's numbers alone. A baseline without that field attributes with current scores only —
an absent field is reported as absent, never guessed at, the same discipline the
fingerprints follow (ADR-0045, ADR-0051).

## Alternatives Considered

- **Only state the contract; judge no new cases.** The cheaper half, and it is the option
  the roadmap item allows. Rejected because disarming is the right answer for a row that
  *cannot* be armed, not for one that can — and `exact` on our own release set could be
  armed for the price of reading three documents.
- **Grow the `uv` sets in this change too**, since they are the ones G3 enforces on. The
  eight cases are written; they are not here. Adding them newly judges three documents, and
  the third corpus assigns formats by rotation over the judged set — so the change would
  have re-rolled the format of documents whose renderings are committed provenance that
  cannot be re-derived, and moved ADR-0039's per-format table with them. Rewriting the four
  offending cases to stay inside the seventeen already-judged documents was the other way
  out, and is worse: it lets the tooling choose what gets judged. Filed as roadmap 4.26.
- **Only judge cases; leave the rule alone.** Rejected because it does not touch the two
  rows that are unfailable by construction, and because at 24 cases a −2 % per-slice bar is
  still a single-case detector. Growing the sets improves the measurement; it does not on
  its own make the gate mean what it says.
- **Loosen the −2 % threshold on thin slices** (a wider band for smaller *n*). Rejected: it
  buries the problem in a constant, and the number it would need is unknowable at this set
  size. A threshold that varies with *n* also reads as rigour while resting on nothing.
- **Drop the thin slices from the release sets entirely.** Rejected for the reason ADR-0044
  gave about re-judging: the slice is measuring something real, and removing the measurement
  because the gate cannot act on it is repairing the instrument by deleting the reading.
- **Enforce per case rather than per slice** — "no judged case may lose more than X". A
  better gate at these sizes, and genuinely tempting. Rejected here: spec 04 §7.3 defines
  G3 per slice, so this is a spec change rather than an implementation one, and it needs a
  measured X. The per-case *attribution* shipped here is what makes that case, if anyone
  wants to argue it later.
- **Re-bless the baselines so the new cases are enforced immediately.** Rejected, and not
  by preference: roadmap 4.22 owns re-blessing and says in its own text that it cannot ride
  along with a judgement change. Growing a set changes `cases_digest`, so G3 reports on all
  three sets until 4.22 re-blesses — which is ADR-0051's designed behaviour working, not a
  hole opened here.

## Consequences

- **On the sets G3 actually enforces, this makes the gate honest and *smaller*.** Our own
  release set is structurally never enforced (BUG-0014), so the rows that matter are the
  `uv` ones — and of their twelve, four are now reported by name rather than counted as
  passes. Roadmap 4.26 is what makes the gate bigger again; this change is what stops it
  claiming coverage it does not have in the meantime.
- **G3 reports rather than enforces on our own release set until roadmap 4.22 re-blesses**,
  because growing it changed its `cases_digest` — ADR-0051's designed behaviour. The
  baseline 4.22 writes will carry per-case scores.
- **The new cases immediately corrected a number that was flattering us.** `exact` on
  ours/release was blessed at **0.9833 on one case**; over four it is **0.7593**, with the
  new `STRIDE` case at 0.3331 — an acronym whose literal home is one document among three
  that mention it. The old figure was not a regression waiting to happen, it was a case
  reported as a slice.
- **The new cases were not chosen to score well.** `r-0017` (`STRIDE`) reads 0.3331 and
  `r-0016` (`Contributor Covenant`) 0.7098, both below the case they joined. Every one was
  written from the documents before anything was run; a set whose additions all scored well
  would be a set chosen after the fact — which is the failure ADR-0044 refused when
  re-judging would have rescued a slice.
- **A slice can now be *reported* and still be read.** The attribution line turns
  `exact 0.9833 -> 0.7593 (-22.8%)` into
  `[r-0003 0.9942, r-0015 1.0000, r-0016 0.7098, r-0017 0.3331]`, which says in one line
  what the movement is: three cases at or near the old number and one much harder — a
  population change, not a regression, legible without opening anything.
- **The frozen-set guard is untouched**, and the rule that blocks a source set from growing
  is left standing rather than relaxed in a change that does not need it. What it costs is
  measured and filed (4.26) instead of being worked around here.
- **Nothing in retrieval, chunking, the store or the metrics is touched**, which is what
  lets a judgement change ship at all (spec 04 §7.1). The one code change is the gate's own
  verdict.
- **What is still not fixed**: 88 → 93 cases is a seed, not a benchmark. A −2 % per-slice
  bar remains single-case-dominated at every size these sets will reach before 1.0, and this
  ADR says so rather than implying that four cases repaired it.

## References

- Spec 04 §7.1 (dev/release split), §7.3 (gate G3), §7.6 (the ≥ 1 000-case target); D-010
- [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) — the measurement that
  filed this item, and the re-judging it refused
- [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md) — the derived-set
  rules, one of which blocks roadmap 4.26 and is measured here rather than changed
- [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md) — why our own
  release set is never enforced, and therefore why the `uv` rows are the ones that matter
- `mycelium eval <corpus> --set eval/release.jsonl` — the verdicts quoted above
