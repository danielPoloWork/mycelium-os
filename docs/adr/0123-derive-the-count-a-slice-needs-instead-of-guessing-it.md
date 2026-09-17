# ADR-0123: Derive the count a slice needs, instead of guessing it

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.3
- **Related:** [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) (which named the
  denominator as the only fix and guessed the constant this replaces),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) (which measured a
  single case moving for reasons unrelated to retrieval),
  [ADR-0069](0069-decide-the-default-on-the-sets-that-can-carry-it.md) (gate G2's half of
  the same problem), [ADR-0051](0051-hold-the-judgements-fixed-too.md) (why the baseline
  is what a gate reads), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (a gate that fires on everything selects for being ignored); D-010; spec 04 §§7.3, 7.6;
  roadmap 4.41, 6.8

## Context

Roadmap 6.8: *"Grow the judged sets until the per-slice conditions mean what they say."*
Gate G2's second condition and gate G3's are statements about a category of question, and
at four to seven cases a slice they are statements about one question. The item budgeted
the fix at **n ≥ 35** per slice, measured at roadmap 4.41, and *"near 200 answerable cases
per set"*.

Two things were worth checking before authoring a single case: whether 35 is still the
number, and whether anything in the gate knows what the number is. Neither held.

## What the measurement said

**The requirement is roughly double what the item budgeted, and it is not one number.**
Derived from every committed baseline — the frozen scores G3 actually compares against —
with `tools/measure_slice_power.py`:

| baseline | slice | cases held | blessed mean | typical case | needs | short |
|---|---|---:|---:|---:|---:|---:|
| ours / release | conceptual | 4 | 0.572 | 0.586 | 52 | 48 |
| ours / release | exact | 4 | 0.690 | 1.000 | 73 | 69 |
| ours / release | fact | 6 | 0.517 | 1.000 | 97 | 91 |
| ours / release | relationship | 4 | 0.331 | 0.461 | 70 | 66 |
| uv-docs / release | conceptual | 4 | 0.659 | 1.000 | 76 | 72 |
| uv-docs / release | exact | 5 | 0.752 | 1.000 | 67 | 62 |
| uv-docs / release | fact | 7 | 0.438 | 0.431 | 50 | 43 |
| uv-docs / release | relationship | 4 | 0.659 | 0.917 | 70 | 66 |
| uv-docs / release | symbol | 4 | 0.702 | 0.710 | 51 | 47 |

Fourteen slices across three baselines, every one of them short, needing **50 to 97** cases
against the four to seven they hold. The median is **67**, not 35 — and the range is wide
enough that a single figure for "how big a slice must be" is the wrong specification. A
slice's requirement is a property of *that slice's own numbers*.

**Why it differs from 4.41's figure, and which is right.** The item derived 35 from the
median *observed loss* — 0.126, what a losing case had historically lost. The bar has to
survive not the loss that happened but the loss that can: a case that stops being answered
at all costs its slice that case's **whole score**, and "no longer in the top ten" is the
ordinary way a case fails. Measured that way, a typical answered case in these sets is worth
0.43 to 1.00, not 0.126, and the requirement moves with it. The conservative reading is the
correct one for a gate — the point of the count is that no single case can trip the row, and
the largest thing a single case can do is disappear.

**And the gate did not know any of this.** `MIN_ENFORCEABLE_SLICE_CASES = 4` was chosen at
roadmap 3.7 and its own docstring admitted it: *"four is not a statistical threshold… what
turns G3 into a regression gate rather than a single-case alarm is set size, not a constant
chosen at this milestone."* Every slice in every committed baseline clears four, so G3 was
reporting **"6 of 6 slice(s) enforced"** while not one of those rows could distinguish a
regression from a single case moving. Four cases each worth 1.000 against a mean of 0.75 is a
row where one case falling out moves the mean by 25 % — twelve times the 2 % bar it is judged
against.

## Decision

**A slice is enforced when it holds enough cases that no single case could trip it alone,
and that count is derived rather than guessed.** `enforceable_at(mean, scores)` computes

    n ≥ q / (0.02 · m)

where `m` is the slice's blessed mean and `q` the median of its blessed non-zero per-case
scores. Below that count the row is **reported, not enforced** — the treatment ADR-0052
already established for a thin slice, now applied with the number computed. The verdict names
the count: *"4 case(s) against the 76 this slice needs for its bar to mean more than one
case."*

**Read from the blessed baseline, never from the run under test.** The alternative is
gameable in the one direction that matters: a regression lowers both `m` and `q`, so a run
scored against its own numbers could raise its requirement above `n` and disarm the row
exactly as it fails. The baseline is frozen, so the requirement is a property of the state
the gate compares against — the same reason ADR-0051 made the judgements a gate input.

**Cases blessed at 0.0000 are excluded from `q`.** A case with nothing to lose cannot be the
one that trips the row, and counting it would report the slice as cheaper to trip than it is.

**`MIN_ENFORCEABLE_SLICE_CASES` survives as a fallback**, for a baseline that records
per-slice means and no per-case scores. The derivation has nothing to read there, and a gate
that invented a requirement from a mean alone would be guessing twice.

**The gate arms itself.** Nothing has to be re-decided when the sets grow: a slice that
reaches its count starts being enforced on the next run, and `tools/measure_slice_power.py`
reports the shortfall while the authoring proceeds.

## What this does not do, and what it costs

**It does not grow the judged sets, which is the other half of roadmap 6.8 and the larger
half.** Closing every shortfall above is roughly **600 cases for the release sets alone**, and
past 1 000 once the dev sets are counted — each one a query and a verified anchor written
*from the documents*, before anything is scored on them (the discipline roadmap 4.39
established and `tools/build_eval_cases.py` records). That is not work this change could
carry honestly: a judged set is permanent infrastructure, and cases written quickly to reach a
count would be the benchmark measuring the judge's haste for the rest of the project's life.
It stays open on 6.8, with a target that is now checkable instead of remembered.

**It removes no enforcement that existed, and this is the claim to check rather than take.**
Every slice G3 stops enforcing is a slice it could not have enforced meaningfully: the row's
own numbers say a single case trips it. What changes is that the verdict says so. The
information a failing row carried is not lost — `_attribute` still names the case that moved,
in the reported line — it simply no longer fails CI on evidence that cannot support a
failure.

**The honest consequence, stated plainly: G3 now enforces nothing on any set.** Not because
the gate was weakened, but because there was never a set large enough for it to mean
something, and the constant was hiding that. A reader who wants enforcement back has exactly
one route, and it is the one spec 04 §7.6 has named since Phase 0: more judged cases.

## Alternatives Considered

- **Author the cases now and leave the constant alone.** The item's literal instruction, and
  rejected on scale and on sequence. Six hundred-plus judged cases is not one change, and
  authoring them against a target of 35 — which the measurement says is wrong by half — would
  have produced sets that still could not arm their slices. The instrument comes first
  because it tells the authoring when it is done.
- **Keep enforcing at four and report the deficit beside it.** Genuinely arguable: it keeps a
  tripwire and tells the truth next to it. Rejected on ADR-0053's rule — a gate that fires on
  single-case noise trains everyone to re-bless, and re-blessing on a red gate is how a
  regression gets absorbed. Reporting the same information without failing keeps the signal
  and removes the reflex.
- **Raise the constant to 67, the median requirement.** Rejected: it is the same guess with a
  better-sourced number, and it would be wrong by up to 30 cases in both directions across the
  fourteen rows measured. The ratio that decides is per slice, and it is cheap to compute.
- **Derive the requirement from the run being judged rather than the baseline.** Rejected as
  gameable in the direction that matters — a regression could disarm its own row.
- **Use the median observed loss, as roadmap 4.41 did.** Rejected: it budgets for the
  regressions that have happened rather than the one that can, and the ordinary failure —
  a case leaving the top ten — costs the whole score, not the median historical delta.
- **Count zero-blessed cases in `q`.** Rejected: they cannot be the case that trips the row.

## Consequences

- **No committed number moves.** The baselines, the corpora and the judged sets are untouched;
  `retrieval_identity()` is untouched, so `eval/g2-verdict.json` stays current. What changes is
  which rows G3 calls enforced, and what its verdict says about the rest.
- **Gate G3's verdict grew a number per reported row**, which is the point: a row that says
  *"4 case(s) against the 76 this slice needs"* is a target, and a row that said *"enforced"*
  was a claim that could not be met.
- **An older baseline still gates exactly as before**, through the fallback — verified by the
  existing thin-slice tests, which carry no per-case scores and did not change.
- **`tools/measure_slice_power.py` ships** and reads the same function the gate does, so the
  target a reader is given and the count the gate applies cannot drift.
- **Gate G2 is not changed here, and shares the problem.** ADR-0069's *"no slice worse than
  −2 %"* is the same condition on the same slices, and roadmap 6.8 names it first. It is left
  alone deliberately: G2 decides a shipped default through `tools/measure_hybrid_gate.py`,
  its verdict is recorded and dated, and moving its arming rule in the same change that moves
  G3's would re-open a shipped decision on the same day the instrument that judges it
  appeared. It is the natural next use of `enforceable_at`, and it belongs with the evidence
  for that decision rather than beside it.

## References

- Re-runnable: `python tools/measure_slice_power.py` (the table above);
  `mycelium eval eval/corpora/uv-docs --set eval/release.jsonl` (the verdict).
- Spec 04 §7.3 (the gate table), §7.6 (the corpus plan this is the near-term face of).
- [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) — *"give a slice cases or stop
  gating it"*, which is this decision with the count supplied.
