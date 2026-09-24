# ADR-0156: Read the agent-task verdict where we did not write the corpus, and ask it for significance

- **Status:** Accepted
- **Date:** 2026-09-24
- **Deciders:** the maintainer (D-031, four questions put on 2026-09-24, each answered with the
  recommended course) with the tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.4
- **Related:**
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the rule this settles, quantified before it bound),
  [ADR-0131](0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-along.md)
  (the bounded incumbent that took the lead from +15 to +2),
  [ADR-0135](0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md)
  (the suite on `uv-docs` and its twin),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) (the rule
  applied here), [ADR-0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md)
  (1.0 at Milestone 7); D-010, D-031; spec 04 §7.4; roadmap 6.4, 6.22, 6.23, 7.3

## Context

Spec 04 §7.4 scores the agent-task comparison qualitatively before 1.0 and makes it a gate at
1.0. ADR-0120 quantified the rule so it could be argued before it bound: **(a)** Mycelium finds
the evidence on more than two tasks beyond grep, and **(b)** its median context is at most half
grep's, with zero unresolved anchors. Two things happened to it before it ever bound — bounding
the incumbent's read took the lead from +15 to +2 (ADR-0131), and on the corpora we did not
write it passed at +5 and +6 (ADR-0135) — and roadmap 7.3 owed three answers before the tag:
which corpus the rule is read on, whether (a) and (b) are one comparison or two, and whether a
twenty-two-task denominator can carry a two-task bar at all.

Measured at `6334571`, paired per task:

| Corpus | Found (Mycelium / grep) | Lead | Only one found (ours / grep) | Sign test p, one-sided | Median context, grep / ours |
|---|---|---:|---:|---:|---:|
| `uv-docs` | 19 / 13 | +6 | 7 / 1 | 0.035 | 3.8× |
| `uv-docs-ingested` | 18 / 11 | +7 | 8 / 1 | 0.020 | 3.8× |
| this repository (clean export) | 16 / 14 | +2 | 6 / 4 | 0.377 | 3.8× |

**The third question has a sharper answer than the item expected.** The lead is a *difference*
of two counts, and on a paired binary outcome the only tasks that carry information about which
strategy is better are the ones on which they disagree. A lead of three can be three to nothing
(p = 0.125) or thirteen to ten; *more than two* passes both, and neither is a result a
twenty-two-task suite can tell from chance. The count is not wrong — one task is the suite's
granularity, and ADR-0120's reason for two survives — but it cannot be the whole of (a).

## Decision

**Read the verdict on the corpora we did not write, keep it two conditions, add a significance
test to the first, and arm it now** (D-031, owner decision).

- **Corpus.** Gate on `eval/corpora/uv-docs` **and** its ingested twin; both must pass. Report,
  never gate, on this repository's own corpus. This is ADR-0053's rule for the judged sets,
  applied to the suite: our corpus grows with every merge, and a verdict read on it would move
  with our documentation rather than with the product. The twin is not an independent sample —
  it carries the same tasks — but it is the ingestion lane, which the product's claims cover.
- **Two conditions.** Effectiveness and cost are different claims that point the same way; the
  5.7× cost difference the item worried about *is* condition (b), not a reason to fold (a) into
  it. (b) is unchanged: median context ≤ half grep's.
- **Condition (a) is a conjunction:** a lead of more than **two** tasks (`VERDICT_LEAD_TASKS`)
  **and** a one-sided exact sign test over the discordant tasks below **0.05**
  (`VERDICT_SIGN_ALPHA`). Stricter than the rule it amends, so it cannot be the re-cut-to-pass
  D-010 forbids — both vendored corpora already cleared the count.
- **Armed now.** `mycelium eval <corpus> --tasks --gate --verdict` fails when the verdict does
  not hold, and CI and `tools/verify.py` run it on the two vendored corpora beside the integrity
  gate they already ran. The item's words: armed before the tag, not discovered in the act of
  failing it.

`mycelium.eval.tasks.task_verdict` reads the verdict off a suite run: paired per task, over the
scorable tasks only, voided by any unresolved anchor. `--verdict` also prints the verdict on any
corpus without gating, so this repository's own reading stays visible.

## Alternatives Considered

- **Gate on uv-docs alone.** Offered; not chosen. It drops the ingestion lane from the verdict
  for no gain in independence.
- **Gate on all three corpora.** Offered; not chosen. It fails today (+2, p = 0.38), and it
  would fail or pass with our own writing — the reason ADR-0053 exists.
- **One combined index** (evidence per token). Offered; not chosen: it mixes two scales, reads
  worse, and would be a new rule rather than a settled one.
- **Replace the count with the sign test.** Offered; not chosen. Cleaner statistically, but it
  would discard a bar ADR-0120 argued for and the suite's granularity still justifies.
- **Keep the count alone.** Offered; not chosen: it passes 3-to-0.
- **Arm only in the release procedure.** Offered; not chosen: the surprise the item exists to
  prevent.

## Consequences

- **A retrieval change that loses the comparison on a corpus we did not write now fails CI.**
  That is spec 04 §7.4's own instruction — fix the product, not the benchmark — made executable.
- **Margins today:** on `uv-docs` removing two of the seven tasks only Mycelium finds would take
  p to about 0.11 and fail; the verdict is armed with room, not with slack.
- **The rule is pinned** by `tests/test_agent_task_verdict.py`; moving a number is a decision
  beside D-031, not an edit.
- **What it still does not say.** The suite measures what each strategy puts in front of a
  model, not what a model then does with it (ADR-0022). Twenty-two tasks is still small; the
  sign test makes the bar honest about that rather than removing it.

## References

- `src/mycelium/eval/tasks.py` (`task_verdict`, `sign_test_p`, the three constants);
  `src/mycelium/cli/app.py` (`--verdict`); `.github/workflows/ci.yml`; `tools/verify.py`.
- `tests/test_agent_task_verdict.py`.
- Spec 04 §7.4; `docs/benchmarks/2026-09-17-reference-profile.md` § *The agent-task verdict
  gate, quantified*.
