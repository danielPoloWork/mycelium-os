# ADR-0069: Read G2's slices case by case, and keep the bar they trip

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.41 (this item), 4.33 (where it was filed), 4.40, 6.8 (filed here);
  RFC-0001; spec 04 §§7.1, 7.3, 7.6; D-010;
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md),
  [ADR-0064](0064-measure-the-gate-that-decides-the-default.md),
  [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md)

## Context

Roadmap 4.41 was filed from ADR-0064's measurement: gate G2's overall bar (+5 % nDCG@10) is
cleared on five of six judged sets, and three sets still fail — every one of them on the
*second* condition, "no slice worse than −2 %", over a slice of four to seven cases. The
item's reading was that this is **one or two cases moving**, that ADR-0044 and ADR-0052 had
already said what a slice that thin can and cannot carry, and that G2 was therefore "a coin
flip on the decision that picks the default retrieval profile".

It also carried a second question, added by ADR-0068: G2's boolean is `passed = hybrid earns
the default`, so `passed=False` is the *shipped* configuration and
`mycelium eval --retriever hybrid --gate` exits non-zero on a correct build.

Two conditions, two questions, and the item was explicit that neither is a licence to widen
a bar so a candidate passes.

**The first question was answered by decomposing, and the item's premise did not survive
it.** ADR-0058's method — read the cases before believing the slice — applied to G2 for the
first time. Every slice that trips the −2 % bar, on the current tree:

| set | slice | n | Δ | cases worse | what actually happened |
|---|---|---|---:|---:|---|
| ours/dev | `fact` | 4 | −5.7 % | 2 | `q-0005` 0.631 → 0.500, `q-0008` 0.041 → 0.000 |
| uv/release | `conceptual` | 4 | −13.1 % | **1** | `u-1016` 0.635 → **0.289** |
| uv/release | `symbol` | 4 | −4.5 % | 2 | `u-1019` 0.710 → 0.590, `u-1025` 0.631 → 0.500 |
| uv-ingested/release | `conceptual` | 4 | −7.5 % | **1** | `u-1016` 0.635 → 0.438 |
| uv-ingested/release | `exact` | 5 | −7.3 % | **1** | `u-1021` 0.316 → **0.000** |
| uv-ingested/release | `relationship` | 4 | −11.2 % | **1** | `u-1022` 0.885 → **0.426** |
| uv-ingested/release | `symbol` | 4 | −3.6 % | **1** | `u-1019` 0.396 → **0.131** |

The `ours` rows move with this repository's own documents — this ADR is one of them — so
`eval/g2-verdict.json` is the authority for their exact values; the five `uv` rows are on
vendored corpora and do not move. Six of the seven trips are **one case**. The item was right about that and wrong about what it
means: these are not cases wobbling inside the noise a thin slice cannot resolve. They are
large, real losses — a median losing case gives up **0.126** nDCG, the worst gives up 0.459,
and `u-1021` is hybrid losing the answer *entirely*. G2 compares two retrievers on the same
cases, the same snapshot, the same instant; unlike G3 there is no corpus drift, no re-cut
boundary, no confounder. Every point of the movement is the retriever.

**But the second half of the measurement says something the item did not ask for.** Across
the six sets there are 119 answerable cases. Hybrid moves **55 %** of them and makes **15 %**
worse. And the bar's own arithmetic: a slice of `n` cases with lexical mean `m` trips when a
single case loses more than `0.02 · n · m`. Measured per slice, that threshold runs from
0.007 to 0.089 nDCG, median **0.053** — against a median losing case of **0.126**.

So a *typical* losing case trips its slice on its own. At four to seven cases a slice, "no
slice worse than −2 %" is not a statement about a category of question at all: it is a
**per-case veto** wearing a percentage's clothes. For it to require more than one case to
move, at the losses actually observed, a slice would need **n ≥ 35** — five to nine times
what these sets have, and in the direction spec 04 §7.6 already points (≥ 1 000 cases at 1.0).

Both things are true at once, and that is the finding: the condition is **catching real harm
and is simultaneously unmeetable** by any change large enough to be worth making.

## Decision

**Keep the bar. Name the cases it fires on. Stop calling a legitimate outcome a failure.**

**The bar is not moved, and the reason is the decomposition, not deference.** Every trip is a
real regression a reader can go and look at. Loosening a condition that is doing its job,
in a change whose stated purpose is that the condition cannot do its job, would be the
fitted parameter this project has refused thirteen times over. What is wrong is the
*denominator*, and the denominator is not a bar to be edited — it is cases to be written,
filed here as **roadmap 6.8** with the arithmetic above.

**Its meaning at these sizes is written down** rather than left for the next reader to
rediscover: at n = 4–7 the second condition says "no single judged question may lose more
than about 0.05 nDCG", which is a far stricter demand than the category-level statement spec
04 §7.3 intends, and it is why hybrid cannot currently pass G2 on any set with a losing case
in it.

**Both conditions now report the cases behind them.** `g2_regressions()` names every case
that got worse inside a tripped slice, in the form ADR-0052 already gave G3: `conceptual
-13.1% (u-1016 0.6352->0.2894)`. It takes plain floats and lives in the harness, and
`tools/measure_hybrid_gate.py` calls it rather than restating it — the same reason ADR-0068
moved G2's two thresholds there. A rule with two implementations drifts, and this one would
drift about what a gate says. Roadmap 4.41 was filed with the wrong premise *because it could
be*: the verdict printed a percentage and no case, and a percentage over four cases cannot
tell a reader whether it is noise or a destroyed answer. A gate that cannot be checked is a
gate that gets argued about from memory.

**Gate G2 becomes a report, in the vocabulary G6 already uses.** `_gate_g2` computes both of
spec 04 §7.3's conditions and states the reading — *earns the default here* / *does not earn
the default here* — with `passed=True` either way, for two reasons that are separate and both
sufficient:

1. "Ship lexical-only" is a legitimate outcome (Milestone 3's exit gate says so in as many
   words). A boolean that calls it a failure is red on every correct build, which is why
   nothing was ever wired to G2 and why for three milestones nothing ran it (ADR-0068).
2. **One set cannot decide the default.** The decision is over every frozen release set
   together, and they disagree: `ours/release` clears both conditions at +20.9 % while both
   `uv` release sets fail. A per-set boolean would have to be either wrong or silent.

The decision stays where ADR-0068 put it: `tools/measure_hybrid_gate.py --check` computes
what the *release rows together* support and fails when it disagrees with the shipped
`[retrieval] profile`. That is the form 4.41 asked for — "the measurement and the shipped
default agree" rather than "hybrid won" — and it is enforced across corpora because that is
the only place the question is well posed.

**And the standing consequence is stated rather than discovered later:** with the bar kept,
G2 cannot promote hybrid at these set sizes. That is a coherent conservative position — spec
04 §7.3 puts the burden on hybrid, and a burden that cannot currently be discharged leaves
the default where it is — but it must be on the record, so that nobody reads the lexical
default as a question being re-weighed each release when it is a question the sets cannot
currently answer.

## Alternatives Considered

- **Arm the per-slice condition by case count, as G3 does** (`MIN_ENFORCEABLE_SLICE_CASES`,
  ADR-0052) — the item's own first suggestion, and the obvious transfer. Rejected on the
  measurement: **every** tripping slice already has four or more cases, so G3's rule changes
  nothing here. Worth stating because the two gates look alike and are not: G3 compares one
  retriever across time, where a slice can move for reasons that are not retrieval at all
  (ADR-0044 measured exactly that); G2 compares two retrievers at one instant, where it
  cannot.
- **An n-aware per-slice bar** — scale the −2 % with the slice's size. Rejected: the scaling
  function is a parameter, nobody has evidence for one, and at these sizes any function
  steep enough to stop the veto would be indistinguishable from switching the condition off.
  The item said this had to be argued "while no candidate is pending"; it also has to be
  argued from data, and the data says the problem is n, not the function of n.
- **Report the per-slice condition and enforce only the overall bar.** The tempting one, and
  it would not even have flipped the default today — `uv-ingested/release` fails the overall
  bar at −3.1 %, so the decision would still read `lexical`. Rejected precisely because of
  how close that is: the default would then rest on one set's overall number, with the
  condition that catches destroyed answers switched off, and `u-1021` going 0.316 → 0.000
  would be invisible. A gate one set away from promoting hybrid on a silenced harm check is
  worse than a gate that cannot promote it at all.
- **Make the harm condition per-case explicitly** ("no judged case may lose more than X").
  Rejected: that is what the bar already says at these sizes, and writing it out would
  introduce X as a chosen number where 0.02·n·m is at least derived from the spec.
- **Re-judge `u-1016`, `u-1021`, `u-1022`.** Not done, and deliberately not: they are the
  cases *against* the candidate, and re-reading a case only when it embarrasses the option
  you prefer is how a judged set stops being evidence (ADR-0067's lesson, from the other
  direction). If they are wrong they are wrong for the lexical leg too, and nothing here
  turns on them individually.
- **Leave `_gate_g2` as a pass/fail and simply document that it fails by design.** Rejected:
  it is the state that made G2 unrunnable, and "documented as red" is how every other gate in
  this table would be if the doctrine allowed it. G6 already has the right vocabulary for a
  gate enforced elsewhere.

## Consequences

- **`mycelium eval --retriever hybrid --gate` is runnable.** G2 no longer contributes a
  failure on the shipped configuration, so the flag means what it says for the other gates.
- **Every G2 verdict now names its cases**, in the harness's gate line, in the tool's table,
  and in `eval/g2-verdict.json`'s `regressions`. The committed record is re-taken so it
  carries them; no measured value moves.
- **The lexical default is unchanged, and now stands on a stated position rather than an
  open one:** hybrid clears the overall bar on five of six sets and cannot clear the harm
  condition on any set where it loses a case, so it cannot be promoted until the sets are
  large enough for that condition to mean what spec 04 §7.3 intends.
- **What this gives up.** Between now and 6.8, G2's second condition cannot distinguish "this
  kind of question got worse" from "this one question got worse". The mitigation is that it
  now says *which* question, so a human can make the distinction the arithmetic cannot.
- **A number for 6.8 that did not exist before**: ~35 cases a slice at these means, against
  four to seven today; six slices a set puts it near 200 answerable cases per set, and spec
  04 §7.6's ≥ 1 000 at 1.0 is the same direction with more room.
- **Nothing in the query path changes**, so no baseline is re-blessed and no retrieval
  measurement moves. `tests/test_eval.py` gains eight tests over the gate's semantics, which
  had **none** — G2's boolean had never been asserted anywhere, which is part of why its
  polarity survived three milestones unexamined — and `tests/test_g2_verdict.py` gains one
  that reads the committed record and fails if a tripped slice does not name its cases. That
  last one is model-free, so CI holds the naming even though CI cannot re-measure G2.
- **A note on ADR-0068's `ours/dev` figure**, made here rather than by editing a merged
  record: it reads +6.8 %, and the committed record has read +6.7 % and now +6.6 %. Nothing
  is wrong with any of them — this repository is its own corpus, so its numbers move every
  time a PR adds an ADR, and each was true when it was taken. `eval/g2-verdict.json` is the
  authority, which is exactly the job the record was given at 4.40.

## References

- Spec 04 §7.3 (G2's two conditions), §7.1 (the dev/release split), §7.6 (set sizes);
  D-010.
- Reproducible with `python tools/measure_hybrid_gate.py`, whose per-slice rows now carry the
  cases; the per-case arithmetic behind the ~35 figure is `0.02 · n · m` against the observed
  single-case losses, both printed by that run.
- [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md) — the method, and the
  third item in a row whose premise did not survive it (4.25, 4.33, 4.38, now 4.41).
- [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) — what a thin slice can
  say for G3, and why the same answer does not transfer to G2.
- [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md) — the runner, and the
  polarity finding this ADR acts on.
