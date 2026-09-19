# 2026-09-19 — a corpus we did not write (roadmap 6.23)

- **Session scope:** roadmap 6.23 — give the agent-task suite the half ADR-0053 has required
  of a gating measurement since Milestone 4, and carry it to the ingested twin.
- **PR:** #170 (`feat/uv-docs-agent-tasks`). Follows #169, merged as `fa6757d`.
- **Milestone 6:** 6.23 closed — the last of the three preconditions the reference profile
  states for arming the verdict gate. 7.3 filed, and it is where the second question goes.
- **Decision it records:** [ADR-0135](../../../adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md).

## The work was reading, not coding

Twenty-two tasks over `uv`'s documentation, each judged by opening the document and deciding
what a correct answer has to rest on. That is most of the session, and it is the part no tool
checks: the generator validates that an anchor *exists* and warns when it is a heading stub,
and nothing can tell it whether the passage actually answers the question. What makes the
judgements trustworthy is the same thing that makes the second corpus worth vendoring —
nobody here wrote these documents, so a prompt cannot be phrased in the words their author
chose. *"Where is it written which directory uv puts executables in, the one that should be
on my PATH?"* had to be guessed the way a reader would guess it.

The shape was copied from the suite we already had: ten `answer`, six `locate`, six `relate`,
which is spec 04 §7.4's vocabulary and twenty is its floor.

## Three decisions, and the one that is not shared with the case carry

**The twin's suite is carried, not judged.** `build_ingested_cases.py` already knows where a
judged passage landed in the projection; a second tool would be a second answer to that
question. The mapping is now one function used by both carries, and the case receipt's bytes
did not move — which is the check that the refactor changed nothing.

**A task that loses a required anchor is dropped whole.** A case is graded per anchor, so it
keeps whatever survived. A task is `found` only when *every* required anchor reached the
agent, so carrying it one anchor lighter would hand the twin an easier task and raise its rate
for a reason that is not retrieval. Nothing is dropped today — all twenty-two carry — which
is precisely when a rule stops being exercised, so it is unit-tested with the mapping stubbed
rather than left to the corpus to exercise some day.

**The new suite is not added to `check_frozen_release_sets.py`.** That script refuses a change
that tunes retrieval *and* re-judges a frozen set at once. But the integrity gate fails the
build when a chunker change moves an anchor, so the re-anchoring has to land in the same
change as the chunker move — the exact conjunction the script would refuse. Arming it would
deadlock a legitimate change rather than catch an illegitimate one. Written down in the ADR,
because "we did not do this" is invisible otherwise.

## What it measured, and the number I did not expect

| Corpus | Mycelium | grep | Lead |
|---|---:|---:|---:|
| `uv-docs` | **18 / 22** | 13 / 22 | **+5** |
| its ingested twin | **17 / 22** | 11 / 22 | **+6** |
| this repository, at `fa6757d` | 16 / 22 | 15 / 22 | **+1** |

The third row is the one worth sitting with. On 2026-09-18 the same suite on the same
instrument read 16/22 against 14/22 — a lead of +2. One day and three merges later it reads
+1. No retrieval changed; we wrote documentation, and the incumbent found another task. A
verdict gate on that number would be a gate on our own writing habits, which is what ADR-0053
says in one sentence and what this measures in one day.

And the measurement had to be taken in a clean checkout of `fa6757d` to say even that much,
because the working tree held this report and the corpus is self-hosting. The manifest records
`root: "."` and the commit; the report says where the tree was.

## What I refused to do

Re-cut the bar. Condition (a) — *more than two tasks* — passes on both corpora we did not
write and fails on the one we do, and the temptation to read that as *"so the rule is fine"*
is exactly the direction D-010 forbids moving in. The question is whose corpus the rule is
read on, and that is a decision for whoever arms the gate: roadmap 7.3, with both reports in
front of them, before the tag rather than in the act of failing it.

## Filed on the way

Nothing new. Both findings this turned up already have items: our evidence rate is flat from
4 000 tokens upward because `_mycelium_context` asks for ten hits whatever the budget says
(6.28), and every task either side loses needs two passages, which is one document eating
slots (6.29). Both were filed at 6.22 and both showed up again here, on documents nobody here
wrote — which is the strongest thing that can be said for them.
