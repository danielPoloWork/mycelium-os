# 2026-09-07 — the plan was written twice (roadmap 4.35)

- **Session scope:** roadmap 4.35 — should every retrieval change gate the vendored
  corpora? (RFC-0001; ADR-0053/0055).
- **PR:** #82 (`ci/retrieval-gates-the-corpora`). Follows #81 (4.25), merged as `ae46f74`.
- **Milestone 4:** 4.35 done; 4.29, 4.32, 4.33, 4.34, 4.36 open.

## The item asked me to measure first, and the measurement moved the question

4.35 offered two answers — widen `retrieval` and pay, or write the gap into ADR-0055 as a
deliberate economy — and told me to measure the cost on the runners before choosing.

The cost on the runners is **zero**. CI's `eval` job fires when the mode is `retrieval`
*or* `full`, and it builds and gates all three corpora. The item's premise — "invisible to
both the local loop and CI" — is wrong about CI, and once that is out of the way the
question is not "should we pay for this" but "why do the two disagree at all".

## What was actually broken

`ci.yml` states the guarantee in its own comment: *"`tools/verify.py` is the same
derivation a contributor runs locally, so what CI decided and what they saw cannot drift:
one implementation, two callers."*

True of the **mode**. Never true of the **plan**. What a mode *runs* lived in `plan()` and
again in job conditions and shell steps, and nothing compared them:

| mode | CI | `verify.py` |
|---|---|---|
| `retrieval` | gates three corpora, runs the agent-task suite | gated one corpus |
| `full` | the above plus the benchmarks alone | gated three; no benchmarks |
| `src/mycelium/eval/harness.py` | **no gate at all** | no gate at all |

That third row is my own PR from this morning. I changed the module that drives the
retriever over the cases, averages the results and decides every gate, and CI reported
`eval / gates G1-G6` as *skipping*. The gates ran because I widened by hand and said so in
the PR body. Nothing made me.

This is the failure this project already has a name for. `mycelium.corpus` exists because
discovery and watch mode "agreed by having the same rule written twice, which is agreement
by coincidence". One implementation with two callers is the fix; two implementations with
one name is the bug, and the comment was describing the half that had been fixed.

## The numbers

| step | time |
|---|---:|
| `retrieval`'s gates as they stood | 19.2 s |
| the four corpora steps | 26.2 s |
| the agent-task suite | 9.9 s |
| **after** | **55.3 s** |
| the benchmarks, alone (`full` only) | 93.1 s |

A `retrieval` run is 730 s of suite and ~20 s of everything else. The widening is **+36 s,
or 4.8 %** — and nothing at all on the runners.

## The consequence I did not expect, and what it forced

Moving the corpora down into `retrieval` leaves `full` running *exactly* what `retrieval`
runs. A mode that adds nothing is a mode whose name promises a gate it does not run, which
is the sentence 4.35 itself ends on. So `full` had to gain something true.

It gained the benchmarks, alone. The suite already executes them — but beside four hundred
other tests on a loaded machine, which is the same numbers taken badly, and AGENTS.md §10
asks for a performance claim backed by a *reproducible* measurement. It is also the one job
CI gates on `full` and nothing else. So the rung is honest in both places at once, which is
the test I wanted for whether I had invented the content or found it.

The other consequence was better: the `eval/corpora/` classification exception, which
existed only because `retrieval` was too narrow to gate a corpus, has nothing left to
except. One rule now covers the judged sets, the baselines and the corpora. **The ladder got
simpler by being made correct** — which is usually the sign that the fix is the right shape
rather than a patch over the symptom.

## What keeps it fixed

`tests/test_verify_ladder.py` reads the workflow and the plan, extracts each job's mode
condition and the verification commands it runs, and asserts that everything CI gates at a
mode is in the local plan for that mode. Superset rather than equality — CI legitimately
runs more *jobs*, and those are the same `pytest` the plan already runs; what must not
happen is CI gating something the local loop never touches.

I wrote it against the broken tree first: with the corpora put back behind `full`, two of
its nine assertions fail and name the job and the command. A congruence test that has never
been seen to fail is a claim, not a check.

It lives in `tests/` rather than in `consistency_lint.py`, which is where cross-artifact
congruence belongs, for a concrete reason: the `consistency` job runs the lint on a bare
interpreter with no dependency install, so it is stdlib-only and cannot parse YAML. Parsing
a workflow with regular expressions to avoid a dependency would make the check less
trustworthy than the thing it checks.

## What I would tell the next reader

The item was filed as a question about economy. It was a question about whether two files
that describe the same thing are ever compared. When a comment in one of them claims they
cannot drift, that claim is the thing to test — the comment is where someone already
noticed the risk and reasoned it away.
