# 2026-09-20 — the spec asked, nobody built it, and the evidence says don't (roadmap 6.29)

- **Session scope:** roadmap 6.29 — one document takes half the slots a search returns;
  measure the alternative instead of leaving the behaviour an accident of RRF.
- **PR:** #PRNUM (`feat/per-document-slot-cap`). Follows #178, merged as `b44d3e2`.
- **Milestone 6:** 6.29 closed, 6.37 filed. 6.30–6.36 remain open.
- **Decision it records:**
  [ADR-0144](../../../adr/0144-measure-the-whole-diversity-family-and-refuse-it.md).

## The item's premise was wrong in the useful direction

6.29 says *"nothing has ever asked whether it should"*. Something did: **spec 04 §4**
asks, in a flat sentence about the pipeline — *"MMR across documents so one document
cannot monopolize the result set unless it uniquely holds the answer"* — and nothing in
`src/mycelium` implements it.

The only diversity rule in the codebase is one chunk per document **inside the graph leg**,
and its own docstring called itself "the diversity guard spec 04 §4 asks of the result set,
applied where it is cheapest". That leg ships off. So the shipped result set had no guard,
and a comment in the source said the opposite.

That is the third requirement this project has found written once and honoured nowhere, and
the common cause is the same each time: nothing reads the specification back against the
code.

## Both families, because they are the family

A cap refuses slots; a decay discounts them. `cap 1` and `λ → 0` are both round robin,
`cap ≥ 10` and `λ = 1` are both the shipped ranking, and everything else interpolates. So
sweeping both across their range is a measurement of the *family*, not of two guesses —
which matters, because "we tried a cap of 3 and it lost" is an anecdote and this is not.

**No arm gains on any release set.** Four gain on dev sets by +0.2 % to +1.6 %, moving one
or two cases each, which is precisely the *proposable, not earned* ADR-0070 exists to
refuse. The slices the arms cost are `relationship` and `conceptual` — cap 2 costs
`ours/dev`'s relationship slice **−65.2 %** — and that is the mechanism in one number: a
diversity rule takes slots from exactly the questions whose answer really is spread through
one document.

## The arithmetic knew first

A 50-deep RRF pool spans `110/61 = 1.80x` between its best and worst candidate. So a
multiplicative discount is **inert or total**: above ~0.95 it changes nothing, below 0.55 it
pushes a document's second chunk beneath *every* other candidate. `λ = 0.5` and `λ = 0.7`
score identically on three of the six sets, which is that saturation showing up in the data.

This is ADR-0075's *no operating point under RRF* for the second time, by a different
mechanism, and it deserves to be stated generally: **RRF's score range is too narrow to
host a multiplicative preference.** Anything that wants to say "somewhat less wanted"
cannot say it in these scores.

## Reading the ceiling first is what made the session short

Per ADR-0094, the oracles went first. The best cap *chosen per query with hindsight* — an
upper bound no fixed policy can reach, and incidentally exactly what §4's *"unless it
uniquely holds the answer"* clause requires — is worth **+1.4 % to +4.2 %**. Re-ordering
the **same 50 candidates** by their judged grade is worth **+36 % to +86 %**.

Two hours of tuning were available and unnecessary: the ceiling said the whole family was
worth a twentieth of the available headroom before any arm was run. The concentration is
real, larger on the judged sets than on the agent tasks that found it (42 % of
`ours/release`, and one query where a single document takes all ten slots), and it is not
where the loss is.

## What shipped, and what did not

No mechanism and no knob (D-011 — and here the evidence is stronger than *unproven*: there
is no operating point to configure). Spec 04 §4's bullet is amended to record the
measurement rather than quietly deleted, `_expand`'s docstring stops implying §4 is
satisfied, and `tools/measure_document_diversity.py` joins `verify.py`'s `retrieval` rung.

It guards the **opposite** of its three siblings. The hybrid, graph and symbol runners
watch a shipped default for a measurement that no longer supports it; this one watches a
*refusal* for a measurement that has started to. `--check` is red only when an arm earns a
release-set gain with no set regressing — the day that happens, ADR-0144 is stale and
should be re-opened rather than rediscovered.

## The follow-up is the real one

6.37: a perfect re-ranking of the candidates we **already have** is worth +36 % to +86 %,
and nothing knows which ones they are. Every ranking item this project has shipped has been
worth single digits against that. Characterising the gap — where the judged passage sits
when it is not in the top ten, whether the pool contains it at all — is the honest next
question, and it is also the first half of spec 06's own trigger for reconsidering a
learned reranker. Establishing that trigger rather than assuming it is the point.
