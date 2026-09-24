# 2026-09-24 — the count could not carry the bar (roadmap 7.3)

- **Session scope:** roadmap 7.3 — settle the agent-task verdict rule, then arm it before the
  v1.0.0 tag. Three questions: which corpus the rule is read on, one comparison or two, and
  whether twenty-two tasks can carry a two-task bar.
- **PR:** #197 (`feat/settle-the-agent-task-verdict-rule`). Follows #196, merged as `6334571`.
- **Milestone 7:** 7.3 closed.
- **Decisions it records:** D-031;
  [ADR-0156](../../../adr/0156-read-the-agent-task-verdict-where-we-did-not-write-and-ask-it-for-significance.md).

## Measure before asking

The three questions are the maintainer's, but a question put without numbers is a question
answered by taste. So the suite was run first on all three corpora and read *paired* — each
task scored for both strategies — rather than as two rates: `uv-docs` +6 with the
disagreements 7 to 1, its twin +7 with 8 to 1, this repository +2 with 6 to 4. This
repository was built from a clean `git archive` of `HEAD`, not the working tree, for the
reason the memory already held: the working tree carries the maintainer's untracked files.

## The third question answered the first two

The lead is a difference between two counts. On a paired outcome only the tasks where the
strategies disagree say which one is better, so the same lead of three can be three to
nothing or thirteen to ten — and *more than two* passes both. A 3-to-0 is p = 0.125. That is
why a count alone cannot carry the bar on twenty-two tasks, and it is also why the fix could be
**stricter** rather than different: keep the count ADR-0120 argued for, and add the exact sign
test in conjunction. Stricter matters here, because D-010 forbids moving a bar to whichever
number passes, and both vendored corpora had already cleared the count.

## What the maintainer chose

Four questions, four recommended answers: gate on `uv-docs` and its twin, report on ours;
two conditions, (b) unchanged; the count *and* the sign test; armed now. The gate is a flag on
the command CI already ran on those corpora, `--verdict`, so arming it was two lines of
workflow and two of the ladder — and `tests/test_verify_ladder.py` would have failed had they
disagreed.

## What the next session should know

- **The verdict now fails CI** if a retrieval change loses the comparison on a corpus we did
  not write. That is spec 04 §7.4's *fix the product, not the benchmark*, made executable.
- **The margin is real but not wide:** on `uv-docs`, losing two of the seven tasks only
  Mycelium finds would put p near 0.11.
- **`--verdict` on this repository prints and never gates.** Its +2 is expected to move with
  every merge; that is the reason it is not the gate.
