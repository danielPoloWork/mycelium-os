# ADR-0059: Make the plan one implementation too, and let `retrieval` gate every corpus

- **Status:** Accepted
- **Date:** 2026-09-07
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.35 (this item), 4.26 (where it was filed), 4.31; RFC-0001;
  spec 04 §§7.1, 7.3; AGENTS.md §10;
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md),
  [ADR-0055](0055-run-the-gates-the-change-implicates.md) (refined here),
  [ADR-0056](0056-make-the-format-assignment-append-only.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md)

## Context

Roadmap 4.35 asked one question — *should every retrieval change gate the vendored
corpora?* — and offered two answers: widen `retrieval` to include them, having measured
what that costs, or state the gap in ADR-0055 as a deliberate economy with its reason.

Measuring it first changed the question.

**The economy is already being paid.** CI's `eval` job runs when the mode is `retrieval`
*or* `full`, and it builds and gates all three corpora. Nothing about widening `retrieval`
costs the runners anything, because the runners already do it. The item's premise — that a
regression on the two enforcing sets is "invisible to both the local loop and CI" — is
wrong about CI.

**What is actually broken is that the two disagree.** `ci.yml` states the guarantee in its
own comment:

> `tools/verify.py` is the same derivation a contributor runs locally, so what CI decided
> and what they saw cannot drift: **one implementation, two callers.**

That is true of the *mode*. It was never true of the *plan*. What a mode runs lived in two
places — `plan()` in `verify.py`, and job conditions plus shell steps in the workflow — and
nothing compared them. Measured on `main`:

| mode | CI runs | `verify.py` ran |
|---|---|---|
| `retrieval` | gates `.`, `uv-docs`, `uv-docs-ingested`; agent-task suite | gates `.` only |
| `full` | the above, plus the benchmarks alone | gates all three; no benchmarks |
| a change to `src/mycelium/eval/harness.py` | **no gate at all** | no gate at all |

A contributor could pass the local loop and then be told something new by CI, which is the
one thing a scoped loop must not do — the whole safety argument of ADR-0055 rests on the
local scope being *narrower in time, not in coverage*.

The third row is not hypothetical. PR #81 changed `eval/harness.py` — the module that drives
the retriever over the cases, averages the results and decides every gate — and CI reported
`eval / gates G1-G6` as **skipping**. The gates were run because the author widened by hand;
nothing made them.

This is the same failure this project has named before. `mycelium.corpus` exists because
discovery and watch mode "agreed by having the same rule written twice, which is agreement
by coincidence" (ADR-0021). The mode has one implementation and two callers; the plan had
two implementations and one name.

**What widening costs**, measured on this machine:

| step | time |
|---|---:|
| `retrieval`'s gates as they stood (`build .`, `gates .`) | 19.2 s |
| the four corpora steps | 26.2 s |
| the agent-task suite | 9.9 s |
| **`retrieval`'s gates after** | **55.3 s** |
| the benchmarks, alone (`full` only) | 93.1 s |

A `retrieval` run is dominated by the suite — 730 s of the ~750 s total. The four corpora
and the task suite add **36 s, or 4.8 %**. On the runners they add nothing at all.

## Decision

**Widen `retrieval`, and make the plan checkable against CI so it cannot drift again.**

1. **`retrieval` builds and gates every vendored corpus, and runs the agent-task suite** —
   what CI's `eval` job does at that mode. These are the sets gate G3 actually *enforces*
   on (ADR-0053); a retrieval change that did not gate them was a retrieval change nobody
   measured where it counts.
2. **`full` keeps the benchmarks, alone.** Widening the corpora downward would otherwise
   have left `full` running exactly what `retrieval` runs — a mode whose name promises a
   gate it does not run, which is the failure 4.35's own last sentence names. The suite
   already executes the benchmarks, but it executes them beside four hundred other tests on
   a loaded machine, which is the same numbers taken badly; AGENTS.md §10 wants a
   performance claim backed by a reproducible measurement, and that means the benchmarks by
   themselves. It is also the one job CI gates on `full` alone.
3. **The corpus exception is retired.** `eval/corpora/` derived `full` only because
   `retrieval` was too narrow to gate it (roadmap 4.26). `retrieval` gates it now, so the
   rule has nothing left to except: one line covers the judged sets, the baselines and the
   corpora alike. **The ladder gets simpler by being made correct**, which is the shape of
   a good fix.
4. **`src/mycelium/eval/` is a tuning path**, replacing the two files it used to name.
   `harness.py` was outside the list and it decides every gate. A directory is the right
   unit for the same reason `store/` and `embedding/` are: the question is not which file
   holds the scoring today.
5. **`tests/test_verify_ladder.py` reads both and fails when they disagree.** It extracts
   each CI job's mode condition and the verification commands it runs, and asserts that
   everything CI gates at a mode is in the local plan for that mode. Superset, not equality:
   CI legitimately runs *more jobs* — a three-OS build matrix, determinism by name — and
   those are the same `pytest` the local plan already runs. What must not happen is CI
   gating something the local loop never touches. The check was written against the broken
   tree first and fails on it.

## Alternatives Considered

- **Option B from the item: state the gap in ADR-0055 as a deliberate economy.** Rejected
  once the measurement showed there is no economy to state. The corpora cost the runners
  nothing extra — CI already runs them at `retrieval` — and 36 s of a 750 s local run does
  not buy an exception to "the local loop covers what CI gates". Documenting a divergence
  as a decision, when it was a drift nobody chose, would have written the wrong ADR.
- **Narrow CI instead: stop running the `eval` job at `retrieval`.** This would also make
  the two agree, at half the cost. Rejected outright: it removes verification from the two
  sets G3 enforces on, which is exactly backwards from what a retrieval change needs.
- **Collapse the ladder to three rungs** (`docs`, `code`, `retrieval`), since `full`'s only
  remaining content was the corpora. Rejected: `full` is still the right answer for a change
  to the verification itself, an unclassifiable file, and every non-PR event, and it now has
  distinct content. Renaming a mode used by the workflow, the tool and every PR body is a
  cost with no matching benefit.
- **Put the ladder check in `tools/consistency_lint.py`.** It is a cross-artifact congruence
  check and that is where such checks live. Rejected on a concrete constraint: the
  `consistency` job runs `python tools/consistency_lint.py` on a bare interpreter with no
  dependency install, so the lint is stdlib-only and cannot parse YAML. Parsing a workflow
  with regular expressions to avoid a dependency would make the check less trustworthy than
  the thing it checks. As a test it gets a real YAML parser, and a change to either file
  runs it.
- **Have CI call `tools/verify.py` directly**, making the plan literally one implementation.
  Rejected: CI's value is that its jobs run in *parallel* and are legible by name in the
  checks list — ADR-0055's whole argument for a scoped local loop is that CI already does
  the full thing quickly. Serialising CI into one script would trade minutes of wall time
  and every named check for a purity the test buys more cheaply.

## Consequences

- **A local `retrieval` run gains 36 s and stops under-reporting.** The gates on the two
  enforcing sets now run for the change most likely to move them, without anyone remembering
  `--mode full`.
- **CI is unchanged.** No workflow job was added, removed or re-keyed; the only edit to
  `ci.yml` is the comment that now says what is true of the plan as well as of the mode.
- **One classification rule fewer**, and one more path classified. The `eval/corpora/`
  exception is gone; `src/mycelium/eval/` is a tuning path, so a change to the harness runs
  the gates it decides.
- **`check_frozen_release_sets.py` also widens**, because it reads the same `TUNING_PATHS`.
  A change under `src/mycelium/eval/` may no longer land together with a re-judged release
  set — correctly: if the scorer and the judgments move at once, nobody can say which moved
  the number, which is the conjunction that script exists to refuse.
- **The duplication is now checked rather than coincidental.** A job added to `ci.yml` that
  gates a corpus the local plan does not know about fails the suite, with the job's name in
  the message.
- **What this does not fix**: the local loop still runs the suite serially and still costs
  ~750 s at `retrieval`. ADR-0055 measured that and refused `pytest-xdist`; nothing here
  changes it, and roadmap 4.32 remains open as the recorded limit that parallelism would
  hit first.

## References

- Measured this session: `retrieval`'s gates 19.2 s, the four corpora steps 26.2 s, the
  agent-task suite 9.9 s, the benchmarks alone 93.1 s; the suite 730 s (the `--mode full`
  run of PR #81). CI's `eval` job condition and steps read from `.github/workflows/ci.yml`.
- The drift itself, reproducible: `verify.derive` and `verify.plan` before this change gave
  `retrieval` a plan gating one corpus, against a CI job gating three.
- [ADR-0055](0055-run-the-gates-the-change-implicates.md) — the ladder this refines, and
  the measurements that chose it.
- [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) — why the
  vendored corpora are the sets that enforce.
