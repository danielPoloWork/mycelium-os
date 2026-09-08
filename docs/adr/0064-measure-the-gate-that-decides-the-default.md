# ADR-0064: Measure the gate that decides the default, and find it cannot decide

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.33 (this item), 4.26 (where it was filed), 4.39, 4.40, 4.41; RFC-0001;
  spec 04 §§2, 3, 7.1, 7.3, 7.6; D-009, D-010, D-011, D-013;
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md),
  [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md)

## Context

Roadmap 4.33 was filed from two judged cases that score **0.0000**:

- `u-1023` (`conceptual`) — *"can I adopt part of uv without adopting all of it"*, judged
  against the features overview's clause *"uv's interface can be broken down into sections,
  which are usable independently or together"*.
- `u-1024` (`relationship`) — *"where do I record which Python a project needs, and what
  reads that"*, judged against the `.python-version` section.

The item made three claims, and read case by case **two of them are wrong**. It is the same
lesson as ADR-0058, which is why this ADR exists in the shape it does: the instruction to
*read the cases before proposing a ranking* has to be followed even when the item that says
it is the one being closed.

**Claim 1 — "both score 0.0000 under both shipped profiles."** Measured now, hybrid serves
`u-1024` on `uv/release` at **rank 5**, nDCG@10 **0.3549**. Only `u-1023` is unserved by
everything.

**Claim 2 — "points at ADR-0025's precondition… a vector leg that only re-ranks what the
lexical leg found cannot introduce a document the lexical leg missed."** The precondition
withholds the vector leg *only when the lexical leg returns nothing*, and ADR-0025
explicitly **rejected** the per-hit form for exactly the reason the item attributes to it.
For these two queries the lexical leg returns **538** and **517** candidates, so the
precondition never fires and the vector leg runs in full. It is not implicated, and that is
checkable in one command.

**Claim 3 — "not 4.23's inflection failure: every word appears as spelled."** Not in the
*answers*. Against the judged chunks:

| case | terms the lexical leg searches | present in the judged chunk |
|---|---|---|
| `u-1023` | `can adopt part uv without adopting all` | `can`, `uv`, `all` — and nothing else |
| `u-1024` | `record python project needs reads` | `python`, `project` — and nothing else |

The words that match are the corpus's least discriminating (`uv` reaches 88 % of its
chunks); every content word of both questions — `adopt`, `part`, `record`, `needs`, `reads`
— appears nowhere in the answer, which says *"usable independently or together"* and
*"can be used to create a default Python version request"*. These are vocabulary-gap cases,
the class ADR-0025 named as forgone in writing.

## Decision

**Close 4.33 with the measurement, not with a fix, and make the measurement re-runnable.**

`tools/measure_hybrid_gate.py` is added: it runs gate G2 across every corpus and both sets,
and prints, for any case id, where each judged anchor sits in the **lexical**, the **vector**
and the **fused** list. Those three numbers are what the item needed, and they separate three
different failures the item had merged into one:

| case | corpus | lexical | vector | fused | what it is |
|---|---|---|---:|---:|---|
| `u-1023` | uv | 421/538 | 276/568 | — | **reach**: no leg finds it |
| `u-1023` | uv-ingested | 403/582 | 286/618 | — | the same, on the projection |
| `u-1024` | uv | 227/517 | **3**/568 | **5** | **served, by hybrid** |
| `u-1024` | uv-ingested | 120/535 | 39/618 | — | **fusion depth**: inside the fused 50, still short of the top ten |

And **gate G2 is re-measured**, because it turns out nothing had re-measured it. G2 is a
comparison — hybrid against lexical on the same cases, ≥ +5 % nDCG@10 with no slice worse
than −2 % (spec 04 §7.3) — and it runs only when a human passes `--retriever hybrid`.
Neither CI nor `tools/verify.py` has ever done so, because CI has no embedding model (D-013:
nothing is downloaded unless configured). So G2's verdict has been carried as prose since
ADR-0017, three milestones and **four** lexical changes ago: packing (4.15), stemming (4.19),
function-word stripping (4.28) and the heading split (4.36).

Re-measured on the current index, on six judged sets:

| set | lexical | hybrid | overall | slice regressions past −2 % | G2 |
|---|---:|---:|---:|---|---|
| ours/dev | 0.5404 | 0.5795 | +7.2 % | `fact` −3.8 % (4 cases) | **FAIL** |
| ours/release | 0.5051 | 0.6112 | +21.0 % | none | **pass** |
| uv/dev | 0.6727 | 0.8271 | +23.0 % | none | **pass** |
| uv/release | 0.6035 | 0.6680 | +10.7 % | `conceptual` −13.1 % (4), `symbol` −4.5 % (4) | **FAIL** |
| uv-ingested/dev | 0.6344 | 0.7732 | +21.9 % | none | **pass** |
| uv-ingested/release | 0.6306 | 0.6194 | −1.8 % | `conceptual` −7.5 %, `exact` −6.7 %, `relationship` −8.3 %, `symbol` −3.6 % | **FAIL** |

**The finding is that G2 does not currently decide anything.** Three pass, three fail, and it
is not a dev/release story — `ours/release` passes while `ours/dev` fails. The **overall**
condition is met on five of six sets; every failure but one is a *per-slice* regression on a
slice of four to seven cases, which is one or two cases moving. ADR-0044 and ADR-0052 said a
slice that small cannot carry a gate; this is that finding arriving on the gate that picks the
product's default retrieval profile.

**So the lexical default stands, and it stands on the burden of proof rather than on a
measurement.** Spec 04 §7.3 puts the burden on hybrid — it must *earn* the default — and a
candidate that fails on three of six judged sets has not earned it. That is a different and
weaker statement than "hybrid was measured and refused", and it is the honest one.

**Nothing in the product changes.** No retrieval change is proposed, because none of the
measured ones reaches these cases: `u-1023` is missed by both legs, and bridging `record` to
*request* is lexical expansion, refused at ADR-0048 for failing G3 and G4.

## Alternatives Considered

- **Flip the default to hybrid, so `u-1024` is served.** Rejected: it fails G2 on both frozen
  uv sets, and on the ingested projection it is *behind* lexical overall (−1.8 %). Shipping it
  on the strength of the dev sets — where it gains +22 % to +23 % — is precisely the fit
  ADR-0027's split exists to prevent, and the dev/release gap under hybrid widens from +0.069
  to +0.159, which the harness itself flags.
- **Re-judge `u-1023`.** The cheapest exit, and it was checked before being rejected rather
  than after. The embedder's own second choice is
  `docs/concepts/projects/sync.md#partial-installations` — and that section is about
  `--no-install-project` flags for Docker layer caching, not about adopting part of uv's
  toolchain. The judgment is right and the question is genuinely hard; the case stays
  conceded. (It is also not refiled as an item: one case is not a roadmap item, ADR-0058.)
- **Loosen G2's per-slice condition so hybrid passes.** Rejected outright, and the shape of
  the rejection matters: the measurement says the *gate* is underpowered, and the response to
  an underpowered gate is more cases (4.39, spec 04 §7.6), never a wider bar. Moving a bar
  because a candidate you like fails it is how a project stops being able to refuse anything.
  What the gate's *statement* should be at these set sizes is filed as 4.41 — a question about
  the gate's design, to be answered on its own and not while a candidate is pending.
- **A per-hit precondition, similarity floor, or score-gap abstention.** All three refused by
  ADR-0025 on measured grounds, and nothing here is new evidence against those refusals — the
  precondition does not fire on either case.
- **Weight the vector leg higher in RRF so `u-1024` surfaces on the ingested projection too.**
  Rejected: spec 04 §3 fixes RRF at k=60 with per-profile weights deferred to Phase 3, and a
  fusion weight tuned to lift one case on one corpus is a parameter with a sample size of one.
  The observation is recorded above instead.
- **Add G2 to CI.** Rejected *here* — it needs the 133 MB model, which CI deliberately does
  not have, so it is a real design question rather than a line to add. Filed as 4.40, whose
  likely shape is `verify.py`'s `retrieval` mode running it when the model is present and
  saying so when it is not.

## Consequences

- **G2's answer is now re-runnable rather than remembered.** `python
  tools/measure_hybrid_gate.py` reproduces the table above; `--cases <id>…` reproduces the
  per-leg view. The precedent this follows is `measure_vector_index.py`'s: if the tool ever
  stops agreeing with the ADR, the ADR is the one that cannot be re-run.
- **The tool prints no latency, deliberately.** It did for one revision, and the figures moved
  by 10× between two runs of the same tree on this machine (lexical p95 15 ms, then 141 ms)
  while every nDCG stayed identical to four decimals. A number that unstable printed beside
  "budget 150 ms" invites a conclusion it cannot support; G5 stays with the harness, which
  measures it where the product runs.
- **Two follow-ups are filed, and they are the item's real content**: 4.40 (G2 has no runner)
  and 4.41 (G2's per-slice condition cannot discriminate at four-to-seven cases a slice).
  4.39's case for growing `uv/dev` gains a second, independent argument: hybrid reads +23 %
  there and fails on the 25-case release set beside it.
- **`u-1024` is evidence *for* the vector leg, not against the precondition.** Its answer sits
  at vector rank 3 of 568 and lexical rank 227 — the clearest single demonstration in the
  project that the embedder reaches passages BM25 cannot. That argument now has a number
  attached to it for whenever hybrid is reconsidered.
- **`u-1023` stays at 0.0000 on both corpora, and is expected to.** No shipped or measured
  candidate reaches it, the judgment is correct, and the honest record is a conceded case
  rather than a refiled item.
- **The two claims this ADR corrects are corrected where they were written**, in 4.33's own
  line, so a reader following the reference does not re-inherit them.

## References

- Spec 04 §7.3 (gates G2, G4), §7.1 (the dev/release split), §7.6 (set sizes), §3 (fusion),
  §2 (candidate generation); D-009, D-010, D-011, D-013.
- Reproducible with `python tools/measure_hybrid_gate.py --cases u-1023 u-1024`, and for the
  gate line as the product reports it,
  `mycelium eval eval/corpora/uv-docs --set eval/release.jsonl --retriever hybrid`.
- [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) — the precondition
  the item named, the per-hit form it rejected, and the forgone class it wrote down, which is
  the class both these cases belong to.
- [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) — what a slice this size can and
  cannot say, now applied to G2.
- [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md) — the method: decompose
  before believing, including when the thing to decompose is the item's own framing.
