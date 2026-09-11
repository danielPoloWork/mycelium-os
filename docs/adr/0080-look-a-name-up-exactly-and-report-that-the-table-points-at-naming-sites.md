# ADR-0080: Look a name up exactly — and report that the table points at naming sites, not documenting ones

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§2-3
- **Related:** [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)
  (the table this reads, and the heading rule this shares), [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (the leg contract, the discount's derivation, and the ablation's shape),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) (what a `symbol`
  judgment names — the rule this measurement collides with),
  [ADR-0065](0065-one-section-cannot-document-two-commands.md) (the same rule, narrowed),
  [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md) (tail
  resolution, which is right for an edge and wrong here), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (RRF, and the first default decided by measurement), [ADR-0064](0064-measure-the-gate-that-decides-the-default.md)
  and [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md) (a verdict is about the
  configuration it was measured under, and needs a runner),
  [ADR-0031](0031-refuse-three-rerankings.md) / [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md)
  (the refused re-rankings this joins), [ADR-0024](0024-serve-what-the-configuration-admits.md)
  (the serving policy's one seam); spec 04 §§2-3, §7.1, §7.3, spec 05 §§2, 3.4; D-009, D-010;
  roadmap 5.1, 5.9, 5.11, 5.19

## Context

Spec 04 §3 lists three candidate generators and the third has never existed:

> **Symbol:** exact lookup in `symbols` for identifier-like tokens.

Spec 04 §2 routes to it — an identifier-like token (`CamelCase`, `snake_case`, dotted path)
plans as *"FTS exact/phrase + symbol lookup first; vector as backfill"*. Roadmap 5.1 filled
the table the lookup would read; 5.9 is the leg, and it was filed with the expectation
written down in advance: *"the yields measured at 5.1 (3 symbols on our docs, 14 on uv) say
the honest expectation is a small or zero move on these corpora … and the ablation must be
allowed to say not yet."*

**The spec states no bar for this leg.** It gates graph expansion in §5 (≥ +3 % on the
`relationship` slice, no overall regression) and hybrid in §7.3 (≥ +5 % overall, no slice
past −2 %), and says nothing about this one. So the bar here is adopted by analogy and
stated rather than implied: **≥ +3 % nDCG@10 on the `symbol` slice with no overall
regression** — §5's shape, on the slice this leg exists for.

Four things were measured before the verdict, and each of them changed what the decision is
about.

**What the corpora define.** Ours: **3** symbols, all headings (`AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`). uv: **14** — seven `doc` terms (`uv.lock`, `pyproject.toml`,
`.python-version`, `.venv`, `PyPI`, `WinGet`, `MacPorts`), five Python functions, a Rust
module and its method. The ingested twin: **12**, the same set less two fences projection
dropped.

**What the judged queries ask for.** The `symbol` slice holds nineteen case-instances across
the six sets. They ask for `SqliteStore`, `UlidFactory`, `BEGIN IMMEDIATE transaction`,
`uvx`, `uv build`, `uv venv`, `uv init`, `uv tool install`, `uv lock --check`,
`uv python pin`, `uv export`. **Not one of them names a symbol any corpus defines**: our
documentation discusses classes in prose without fencing their definitions, and uv's
documents commands, which are not symbols. The leg can fire on **4 of 133** judged
case-instances and on **0 of 19** in the slice it exists for.

**Where a definition site already ranks.** On all four firings the symbol's `doc_refs`
chunk is *already inside the lexical leg's fifty candidates* — at ranks 11 and 49 on uv, 10
and 44 on the ingested twin. This is not a coincidence and it is the load-bearing
measurement: **a definition site contains the name that makes it a definition**, so BM25
retrieves it for any query naming it, and normally first. Under ADR-0075's rule that a leg
*adds and never promotes*, a leg with nothing to add carries nothing.

**Whether the definition site is the answer.** On all four firings it is **not judged
relevant at all**. `uv lock --check` names `uv.lock`, whose definition site is
`docs/guides/projects.md#project-structure/uv-lock/0` — a line in a directory listing —
while the judged anchor is `docs/concepts/projects/sync.md#checking-the-lockfile/0`. This is
ADR-0062's rule meeting ADR-0073's from the other side. ADR-0062 decided that a `symbol`
judgment names *the section that documents the named thing*, and that a page which merely
*names* it is a lesser grade or none. ADR-0073's extractor takes `defined_in` from exactly
that kind of page: the heading that spells the name. **The table points at naming sites; a
`symbol` query wants documenting sites.**

## Decision

**The leg is built, exactly as spec 04 §3 words it, and it ships off.**

**Exact lookup, and only exact.** The query is cut into tokens, the identifier-like ones are
crossed with the known languages, and the resulting `sym:<language>:<name>` ids are asked of
the store in one round trip. `pyproject.toml` finds `sym:doc:pyproject.toml`; `lock` does
not find `uv.lock` and `venv` does not find `.venv`. Tail matching was measured and
rejected: it is what produced three of the four firings before the rule was tightened, and
every one of them matched *a different thing from the one the query asked about*. Resolving
a use by its last segment is right for an edge, where ambiguity can be refused and the claim
is only that two names are related (ADR-0074), and wrong for a ranking, where the claim is
"read this passage".

**One rule decides what a name looks like.** `identifier_like` is spec 04 §2's test, and it
is now the single implementation shared by the heading rule that *creates* a symbol
(ADR-0073) and the query rule that *finds* one. Two copies would drift, and the drift would
make the leg unable to reach precisely the symbols the extractor wrote.

**The table proposes; BM25 disposes** — ADR-0075's shape, reused rather than reinvented. The
lookup answers *which passages define this name*, which is membership; `rank_anchors` orders
them, which is relevance. A symbol whose defining chunks hold none of the query's words
contributes nothing.

**The leg adds and never promotes, and `SYMBOL_PROMOTE` is a named constant rather than a
hard-coded rule**, because spec 04 §2 says *"symbol lookup **first**"* — which reads as a
licence to promote — and ADR-0075 says a leg that promotes makes RRF pay one piece of
evidence twice. The two readings could not both be obeyed and were not worth arguing about,
so the runner scores both and this ADR reports both.

**The discount is not re-derived.** ADR-0075 established that RRF at k=60 leaves any added
leg an operating window of roughly `0.87 < d < 1` for a served window of ten. `0.9` is the
same round value inside it; choosing a *different* number for this leg would have been a
second unmeasured constant with no argument behind it.

**Every offered passage is labelled** `defines <symbol id>` in `--explain`, in `--json` and
in `mycelium_explain` — the counterpart of `via_edge` for the other derived leg. Where one
chunk defines the same name twice over (a `## RetryPolicy` heading above the fence declaring
`class RetryPolicy`), the label names **both** symbols rather than whichever sorted first,
which would have been an arbitrary tie-break presented as a fact.

**And the verdict: the leg does not earn the default, so it stays opt-in.** Measured on six
case sets across three corpora, at the shipped constants.

*Add-only — the shipped reading:*

| set | lexical | with the leg | overall | `symbol` slice |
|---|---:|---:|---:|---:|
| ours/dev | 0.5435 | 0.5435 | +0.0 % | +0.0 % |
| ours/release | 0.5278 | 0.5278 | +0.0 % | +0.0 % |
| uv/dev | 0.6143 | 0.6143 | +0.0 % | +0.0 % |
| uv/release | 0.6109 | 0.6109 | +0.0 % | +0.0 % |
| uv-ingested/dev | 0.5505 | 0.5505 | +0.0 % | +0.0 % |
| uv-ingested/release | 0.6370 | 0.6370 | +0.0 % | +0.0 % |

**Every case on every set is identical to the baseline**, and that is the honest shape of
this result: not "the leg lost by a little" but "the leg had nothing to carry". Its
candidates were already in the ranking.

The `ours/*` absolutes move as this change's own documents enter the corpus — a self-hosting
corpus is reported and never gated for exactly that reason (ADR-0053) — so the column that
means something here is the delta, and it is zero by construction rather than by rounding.

*Promote — spec 04 §2's other reading:*

| set | lexical | with the leg | overall | `symbol` slice | the case that moved |
|---|---:|---:|---:|---:|---|
| ours/dev | 0.5435 | 0.5435 | +0.0 % | +0.0 % | — |
| ours/release | 0.5278 | 0.5278 | +0.0 % | +0.0 % | — |
| uv/dev | 0.6143 | 0.6141 | −0.0 % | +0.0 % | `u-0021` 0.1016 → 0.0975 (`relationship` −0.9 %) |
| uv/release | 0.6109 | 0.6039 | **−1.1 %** | +0.0 % | `u-1001` 0.6764 → 0.5174 (`fact` −5.2 %) |
| uv-ingested/dev | 0.5505 | 0.5501 | −0.1 % | +0.0 % | `u-0021` 0.1202 → 0.1125 (`relationship` −1.6 %) |
| uv-ingested/release | 0.6370 | 0.6301 | **−1.1 %** | +0.0 % | `u-1001` 0.6764 → 0.5174 (`fact` −4.5 %) |

**The `symbol` slice moves +0.0 % under both readings, on all six sets.** The leg cannot
reach the slice it exists for; all promotion does is cost two cases in two other slices, by
lifting a directory listing over the section that answers the question.

`tools/measure_symbol_leg.py` is the runner. `--check` fails when the shipped flag disagrees
with the measurement, never when the ablation is lost — losing it is a legitimate outcome
that would otherwise turn CI red on every correct build (ADR-0068's distinction). It runs
from the `retrieval` rung of `tools/verify.py` and in CI, where like the graph ablation and
unlike gate G2 it can re-measure rather than merely re-date, because it needs no model.
`--coverage` prints the three measurements above, because a leg scoring +0.0 % *because it
never ran* and a leg scoring +0.0 % *because it ran and changed nothing* are different
findings with different follow-ups.

## Alternatives Considered

- **Ship it on, because spec 04 §3 prescribes it.** Rejected on the numbers. The spec
  prescribes the *mechanism*; it does not promise the mechanism helps on every corpus, and
  D-010's discipline is to measure before believing. Shipping a leg that is provably inert
  on every corpus we can measure would add a candidate generator to the query path in
  exchange for nothing.
- **Ship the promoting reading, because §2 says "first".** Rejected on the numbers *and* on
  the mechanism. It costs 1.1 % overall on both release sets, and the reason is not
  tuneable: the passage it promotes is a naming site, and the judged answer is elsewhere.
- **Match a name by its last segment**, so `lock` finds `uv.lock` and `delay` finds
  `RetryPolicy.delay`. Rejected: measured, it *is* three of the four firings on the uv
  corpora, and each one matches a different thing from the one asked about — `uv venv` finds
  `.venv`, `uv lock --check` finds `uv.lock`. ADR-0074 resolves a *use* that way and should:
  an ambiguous edge can be refused and its claim is weak. A ranking's claim is not.
- **Tune the discount, or the candidate budget.** Rejected before it was run, on ADR-0075's
  arithmetic: under add-only the leg carries *nothing*, so no discount changes a single
  result; under promote the leg's candidate is wrong, so no discount makes it right. This is
  the rare case where a sweep is not merely fitting but arithmetically pointless, and saying
  so is cheaper than a curve nobody can act on.
- **Make it a boost rather than a leg** — score a passage higher because it defines a name
  the query used (spec 04 §4's multiplicative boosts). Genuinely arguable, and the form the
  evidence points at: the leg's candidates are already retrieved, and re-ranking what is
  already retrieved is what a boost is for. Rejected *here* because it would promote the
  same wrong passage: on all four firings the definition site is not the judged answer, so a
  boost would cost exactly what the promoting arm costs. It becomes worth building when the
  table points at documenting sites, which is roadmap 5.19.
- **Route it through the planner** — run the lookup only for queries spec 04 §2 classifies as
  identifier-like, rather than on every query. Partly done and partly deferred: the leg
  *does* test each token, so a query with no identifier-like token costs one regex and no
  store access. Making the *plan* an explicit, logged routing decision is roadmap 5.11, which
  already asks the same question of graph expansion; answering it for one leg and not the
  other would leave the planner half-built.
- **Refuse the leg outright and record the refusal**, as with the fifteen re-rankings.
  Closest call here, as it was at ADR-0075. Rejected for the same reason: spec 04 §3 defines
  the generator, the ablation is the deliverable rather than the feature, and the condition
  under which it would matter is *named, open and measurable* — a corpus whose reference
  pages define what they document. Shipping the mechanism behind a measured-off flag keeps
  the ablation re-runnable on such a corpus; refusing it would mean rebuilding it to find
  out.
- **Judge new `symbol` cases that the leg could serve.** Rejected outright: writing cases a
  feature can win is the definition of fitting the benchmark to the product, and D-010 says
  the opposite. If the `symbol` slice is unrepresentative, that is a judgment question to
  settle from the documents in a change that touches no retrieval code (the shape ADR-0062
  and ADR-0065 both took).

## Consequences

- **`[retrieval] symbol_lookup` is real and defaults to `false`**, with the numbers in its
  docstring. An operator who turns it on gets a labelled, budgeted, explainable leg that on
  a documentation corpus does nothing, and on a corpus with a real API reference surfaces
  definition sites the ranking buried.
- **A test asserts the default and the constants**, so flipping either without re-running the
  ablation fails the suite as well as `--check`.
- **The leg's silence is demonstrable, not assumed.** `tests/test_symbol_leg.py` builds the
  one corpus shape that produces an addition — fifty-five documents that mention a name more
  often than the one document defining it — and shows the definition at lexical rank 56
  entering a ten-deep window at position 8. A null result is only worth reporting if the
  thing measured demonstrably runs.
- **`retrieval_identity()` gains the symbol constants**, so gate G2's verdict was re-recorded
  in this change (ADR-0064's rule). The shipped ranking is unchanged, and the check that
  proves it: the four `uv` and `uv-ingested` numbers reproduced **byte-identically**, and
  only `ours/*` moved, by the corpus growth that a self-hosting corpus reports rather than
  gates (ADR-0053).
- **No baseline moved and no judged set was touched.** The shipped configuration is
  unchanged, so gate G3 has nothing to re-bless and `tools/check_frozen_release_sets.py` has
  no conjunction to refuse.
- **Gate G6's golden moves by one line, and only one.** `config_digest` covers *resolved
  settings* rather than file bytes (ADR-0014), so adding a key to `[retrieval]` changes it
  even though nothing about compilation moved — every document, chunk and symbol in the
  golden is byte-identical and `counts` is unchanged. That is the shape a config-only change
  should have, and it is worth checking rather than assuming: a golden that moved more than
  this line would have meant the leg had reached the compiler, which it must not.
- **`src/mycelium/symbols/` joins `TUNING_PATHS`**, for the reason `graph.py` joined at 5.3:
  with the flag on, what the extractor decides a document defines is what a query can be
  answered with, so the package is a candidate generator and not only a compiler stage.
- **One store method joins the protocol**: `symbols_by_id`, an exact primary-key lookup. The
  caller composes the ids because only it knows which languages a bare token might name.
- **Latency is negligible and measured.** The leg's p95 is **0 ms** on all three corpora —
  the common case is one regex and no store access — with a maximum of 9 ms on the queries
  where it fires and runs a BM25 pass. End-to-end p95 stays 18–28 ms against gate G5's
  150 ms budget.
- **The finding that outlives the flag is filed as roadmap 5.19.** `defined_in` names where a
  thing is *named*; a `symbol` judgment names where it is *documented* (ADR-0062); and on
  four measured firings those are different chunks. Until they agree, no amount of retrieval
  work makes this leg useful — which is a more useful thing to know than a tuned constant.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §2 (the planner's routing rules and the
  identifier-like test), §3 (the symbol generator, and RRF), §7.1 (the `symbol` slice),
  §7.3 (the gates whose shape this bar borrows); `.draft-specs/05-interfaces-and-plugins.md`
  §2 (`[retrieval]`), §3.4 (`explain`).
- Decision log: D-009 (hybrid + RRF), D-010 (fix the product, not the benchmark).
- Re-runnable: `python tools/measure_symbol_leg.py`, `--coverage`, `--promote`.
- Tests: `tests/test_symbol_leg.py`.
