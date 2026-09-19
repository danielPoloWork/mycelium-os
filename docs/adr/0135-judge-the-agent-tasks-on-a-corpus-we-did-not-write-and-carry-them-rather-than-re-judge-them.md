# ADR-0135: Judge the agent tasks on a corpus we did not write, and carry them rather than re-judge them

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.4
- **Related:** [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (the principle this applies), [ADR-0022](0022-measure-the-agent-loop-without-an-agent.md)
  (the suite and what it leaves out),
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the verdict rule, quantified, and its three preconditions),
  [ADR-0131](0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-along.md)
  (the bounded read that took our lead to +2),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) (who judged
  the documents, and the bias a second corpus does and does not remove),
  [ADR-0039](0039-measure-what-projection-costs.md)
  (the carry this reuses), [ADR-0102](0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md)
  (`whole`, and the refusal to choose an anchor with it),
  [ADR-0056](0056-make-the-format-assignment-append-only.md) (the regeneration check that
  replaced a rule about which commit a file arrived in),
  [BUG-0026](../bugs/2026/09/BUG-0026-the-uv-judged-sets-do-not-reproduce-from-their-generator.md);
  spec 04 §§7.1, 7.4, 7.6; D-010; roadmap 6.4, 6.22, **6.23**, 6.28

## Context

ADR-0053 settled a principle for the judged sets and named the reason in its title:
*report* on the corpus we author, *gate* on the one we do not. A gate whose corpus its own
authors edit is a gate that can be made to pass by editing the corpus, and — worse, because
it is silent — a gate whose number moves for reasons that have nothing to do with the
product.

**The agent-task suite has only ever had the first half.** All twenty-two tasks in
`eval/tasks.jsonl` are anchored into this repository's own README, SECURITY, CONTRIBUTING and
ADRs. That was the right shape while spec 04 §7.4 scored the comparison qualitatively
pre-1.0, and it is the blocker the moment the verdict is meant to gate at 1.0, because every
property that makes the comparison move is ours to change: which documents exist, how large
they are, where the chunker puts a boundary under an anchor, and — as roadmap 6.22
measured — the single file that supplied 93 % of the incumbent's entire measured cost.

Two findings from roadmap 6.4 and 6.22 say how that goes wrong in practice rather than in
principle. A chunker change (ADR-0047) moved four required anchors and the suite went on
scoring them as *retrieval misses* for both strategies, capping its own rate at 18/22 with
nothing saying so. And `ROADMAP.md` grew until the incumbent read it on 13 of 22 tasks, which
made the headline ratio mostly a fact about our roadmap file. Neither is a retrieval fact;
both are facts about a corpus we write.

`docs/benchmarks/2026-09-17-reference-profile.md` states three preconditions for arming the
verdict gate. Two were closed by 6.4 and 6.22. **This is the third, and it was the only one
no item owned.**

### The second question this item inherits

Bounding the incumbent's read (ADR-0131) took our lead on evidence from **+15 tasks to +2**,
and the rule ADR-0120 quantified asks for *more than two*. So the rule no longer passes its
own first condition on this repository's corpus. ADR-0131 refused to re-cut the bar in the
act of discovering we no longer clear it — that is the benchmark-fixing D-010 forbids — and
carried the question here. This ADR does not settle it either, for the same reason, and says
below where it goes.

## Decision

**A second agent-task suite is authored over `eval/corpora/uv-docs`, judged by reading the
documents, and committed before anything is scored on it.** Twenty-two tasks —
`tools/build_uv_docs_tasks.py`, ten `answer`, six `locate`, six `relate`, spec 04 §7.4's
floor is twenty — each with the anchors an answer must rest on, every one validated against a
clean build before the file can be written. The prompts are phrased as a reader would ask
them, which on this corpus is not a stylistic preference: nobody here wrote these documents,
so a prompt *cannot* be phrased in the words their author happened to choose (ADR-0027).

**The twin's suite is carried, never re-judged.** `tools/build_ingested_cases.py` already
carries the judged sets onto the ingested corpus by computing where each judged passage
landed; it now carries the task suite the same way, through the same coverage and `whole`
floors, into `eval/corpora/uv-docs-ingested/eval/tasks.jsonl` with a receipt beside it
(`tasks-carry.json`). Re-judging the twin would answer *"can this agent find passages in
these documents"* — the trap ADR-0027 exists to name — instead of letting retrieval be the
only thing that varies.

**A task that loses one required anchor in the carry is dropped whole, where a case keeps the
anchors that survived.** The two are scored differently and that is the entire reason: a case
is graded per anchor, so losing one costs it the grade it held; a task is `found` only when
*every* required anchor reached the agent, so carrying it one anchor lighter would weaken the
conjunction and hand the twin an easier task than the one it claims to be. The twin's rate
would then rise for a reason that has nothing to do with retrieval. On the current corpus
nothing is dropped — all 22 carry, and no two required passages collapse onto one twin
chunk — but the rule has to be right before the projection changes, not after.

**Both suites are gated for integrity, on all three corpora.** `mycelium eval <corpus>
--tasks --gate` already fails when a required passage the snapshot no longer holds is named;
the ladder and CI now run it on the two vendored corpora as well as on this one, and
`tools/build_uv_docs_tasks.py --check` joins its sibling generators so a task hand-edited
into the committed file cannot survive ([BUG-0026]).

**The verdict stays reported, not armed.** Spec 04 §7.4 conditions the gate on 1.0 and
ADR-0113 places 1.0 at Milestone 7. What changes here is that the third precondition is met
and the reading can finally be taken on a corpus we do not control —
`docs/benchmarks/2026-09-19-the-suite-on-a-corpus-we-did-not-write.md`, with its manifests.

**The open question travels to M7 as a roadmap item, with its evidence, and is settled before
the tag rather than in the act of failing it.** Roadmap 7.3 owns it: *is the rule the right
rule?* The measurement this item adds is the strongest thing anyone has to argue it with, and
it cuts both ways — on the corpus nobody here wrote, the lead is **+5 tasks** and the median
context ratio **6.7×**, so both of ADR-0120's conditions pass comfortably; on our own corpus
the lead is +2 and condition (a) fails. That is a fact about which corpus the rule is read
on, and it is exactly the fact ADR-0053 predicts. It is *not* a licence to quote the
favourable number: the two corpora are different measurements and the report says so.

## Alternatives Considered

- **Re-anchor the existing twenty-two tasks onto the uv corpus instead of writing new ones.**
  Rejected: the tasks were written *about* this repository — the publication order, the
  injection doctrine, why chunking has no overlap — and a question about a decision this
  project took has no counterpart in uv's documentation. Translating them would produce
  prompts shaped by our documents and answered by somebody else's, which is the worst of
  both.
- **Retire `eval/tasks.jsonl` and keep only the new suite.** Rejected. The self-hosted suite
  is the one that measures the product *on the documents its authors know*, which is what
  makes a regression legible: when a task fails there, whoever broke it can read the passage.
  ADR-0053's rule is report *and* gate, not gate instead of report.
- **Re-judge the ingested twin's tasks by reading the projected documents.** Rejected on
  ADR-0039's argument, which has not weakened: the twin exists to measure what the projection
  costs, and a judgement written against the projection cannot measure that. Deriving the
  anchor mechanically keeps the judgement fixed.
- **Carry a task with the anchors that survived, like a case.** Rejected — see the Decision.
  It is the one way this carry could quietly make the twin easier, and `found` being a
  conjunction is what makes it quiet.
- **A second tool for the task carry.** Rejected: it would be a second answer to the question
  `build_ingested_cases.py` already answers — where did this passage land — and the two could
  disagree. The mapping is now one function (`map_anchor`) used by both carries. The file
  keeps its name because renaming a generator that CI, the ladder and four ADRs call by name
  changes everything about it except what it does.
- **Extend `carry.json` to a `v3` schema holding both carries.** Rejected: that receipt is
  read by `tools/measure_projection_cost.py` and pinned by tests, so a schema bump there
  would be a change to the *case* carry's record taken in a change that touches no judged
  case. The task carry gets its own file.
- **Add the new suite to `check_frozen_release_sets.py`'s `RELEASE_SETS`.** Rejected, and the
  reason is mechanical rather than philosophical. That script refuses a change that tunes
  retrieval *and* re-judges a frozen set in one commit. But the task suite's integrity gate
  **fails the build** when a chunker change moves an anchor (ADR-0120), so the re-anchoring
  has to happen in the same change as the chunker move — which is precisely the conjunction
  the script would refuse. Arming it would deadlock a legitimate change rather than catch an
  illegitimate one; the reproduction check plus the integrity gate is the pair that actually
  holds here, which is the argument ADR-0056 already made for the derived sets.
- **Arm the verdict gate now that the third precondition is met.** Rejected: spec 04 §7.4
  conditions it on 1.0, and the rule's own first condition is under question (ADR-0131). A
  gate armed on a rule nobody has re-argued would be armed on the number that happened to
  pass.
- **Re-cut the rule to `more than one task`, which every corpus here would pass.** Rejected
  outright. It is the benchmark-fixing D-010 forbids, and the arithmetic it would discard is
  sound: one task is 4.5 % of a 22-task suite, so a bar one task can flip is a coin toss.

## Consequences

- **The verdict can be read on a corpus we do not control**, which is what the third
  precondition asked for. On `uv-docs`: **18/22 against 13/22** with a median context of
  2 274 tokens against 15 251. On its ingested twin: **17/22 against 11/22**. Both are wider
  margins than this repository's own corpus gives, and neither is quotable alone.
- **A finding that is not about retrieval, and belongs to another item.** Mycelium's evidence
  rate on the new suite is flat from a 4 000-token budget upward — 18/22 at 4 000, at 8 000
  and at 16 000 — because `_mycelium_context` asks for ten hits whatever the budget says. The
  incumbent keeps climbing across the same band. That is roadmap 6.28, found independently
  here, and it means every number above is taken with our side of the comparison unable to
  spend what it is given.
- **Three corpora now fail the build when a chunker change moves a required anchor**, where
  one did. That is the correct bill — moving an anchor invalidates a judgement, and a
  benchmark that reports through it is worse than one that stops — but it is a bill that now
  arrives twice as often, and on corpora whose documents cannot be edited to make it go away.
  That is the point.
- **The ladder and CI grow four steps** (`build_uv_docs_tasks.py --check`, plus the integrity
  gate on each vendored corpus). The generator's check costs a clean build of the uv corpus,
  about ten seconds; the carry check costs nothing new, because the tool it joined was
  already building both corpora.
- **A limit, stated.** The tasks are ours even though the documents are not: which questions
  get asked, and which passage counts as the evidence, were both decided by the agent that
  builds the retriever. ADR-0027 says what a second corpus removes — the phrasing advantage —
  and this removes no more than that. A model in the loop and a scorer that reads answers
  rather than anchors remain 1.0's own question (ADR-0022).
- **The suite is frozen the way a release set is, by convention rather than by the script.**
  `build_uv_docs_tasks.py --check` refuses a hand edit and the integrity gate refuses a rotted
  anchor, but nothing mechanically refuses *re-judging a task in the same change that tunes
  retrieval*. The reason is in the Alternatives; the consequence is that a reviewer has to
  look, and the ADR says so rather than implying a machine is watching.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (the freeze), §7.4 (the grep
  baseline, the ≥ 20-task floor, the gate at 1.0), §7.6 (the second corpus);
  `.draft-specs/06-roadmap-and-governance.md` §Phase 4.
- The report: `docs/benchmarks/2026-09-19-the-suite-on-a-corpus-we-did-not-write.md` and its
  two manifests under `docs/benchmarks/manifests/`.
- Assets: `eval/corpora/uv-docs/eval/tasks.jsonl`,
  `eval/corpora/uv-docs-ingested/eval/{tasks.jsonl,tasks-carry.json}`;
  `tools/build_uv_docs_tasks.py`, `tools/build_ingested_cases.py`,
  `tools/measure_agent_task_band.py`; tests: `tests/test_agent_tasks.py`,
  `tests/test_eval_ingested_corpus.py`.
- Re-runnable: `python tools/build_uv_docs_tasks.py --check`,
  `python tools/build_ingested_cases.py --check`,
  `mycelium eval eval/corpora/uv-docs --tasks --gate`,
  `python tools/measure_agent_task_band.py eval/corpora/uv-docs`.
