# ADR-0083: Route the query — and report that routing cannot save a lost ablation

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §2
- **Related:** [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (the graph leg, its ablation, and the follow-up this answers),
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (the symbol leg, which deferred its half of the same question here),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (gate G2, and the
  vector leg's default this must not overturn), [ADR-0064](0064-measure-the-gate-that-decides-the-default.md)
  (a verdict is about the configuration it was measured under),
  [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md) (a gate needs a runner,
  and losing is not failing), [ADR-0024](0024-serve-what-the-configuration-admits.md)
  (narrow, never widen — the same direction of safety), [ADR-0055](0055-run-the-gates-the-change-implicates.md)
  (a scope that may only move in the safe direction), [ADR-0031](0031-refuse-three-rerankings.md)
  / [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md) (the refused
  re-rankings this joins); spec 04 §§2–5, §7.3, spec 05 §§3.1, 3.4; D-009, D-010; roadmap
  5.3, 5.9, 5.11

## Context

Spec 04 §2 has described a planner since the specification was frozen, and the query path
has never had one:

> The planner is a small, deterministic, logged rule set — not a model call (v1) … Every
> response's `explain` includes the chosen plan and why (matched rule), so planner behavior
> is auditable and debuggable rather than folkloric.

Its table routes an identifier-like token to *"FTS exact/phrase + symbol lookup first; vector
as backfill"*, a natural-language question to hybrid, and *"relationship phrasing ('what
depends on…', 'related to…') or `--related`"* to *"Hybrid + graph expansion"*. What shipped
instead was: every enabled leg runs on every query, and the field `mycelium_explain` calls
`plan` holds the name of the configured profile — which names no rule and explains no choice.

Two ablations have since been lost with that reading in place. Roadmap 5.3 measured graph
expansion on every query and it regressed overall on all six judged sets (ADR-0075); 5.9
measured the symbol leg the same way and it was inert on all six (ADR-0080). Both ADRs filed
the same follow-up, and 5.11 states its reasoning: expansion *"pays its cost on all cases and
its benefit is available on few, so a router that spent the budget only where the shape of
the question predicts a relationship would change the arithmetic the gate is decided on"*.
Both items also asked for the decision to be taken **once**, with both legs in hand.

Four things were measured before anything was built, and each of them decided part of the
answer. `tools/measure_routing.py` is the runner; every number below is one of its rows.

**A phrase list cannot find the relationship queries.** Scored as a classifier against the
judged `relationship` slice across all 133 judged case-instances:

| rule set | fires on | precision | recall |
|---|---:|---:|---:|
| spec 04 §2's two phrasings, literally | 1 | 100 % | 5 % (1/22) |
| those two, generalised to their verb family (**shipped**) | 3 | 100 % | 14 % (3/22) |
| a list written by reading the queries it had to catch | 18 | 72 % | 59 % (13/22) |

The slice is judged by *where the answer lives* — two documents holding two halves of it —
not by how the question is worded. `can an agent keep querying while a build is running` is
the case expansion was filed to rescue and there is no relationship phrase in it, nor in
`why does a single lockfile cover every package in a workspace`, nor in sixteen others.

**Routing cannot change the number the gate is decided on, and an oracle proves it.** Route
by the judged slice itself — no deterministic rule set can beat a router that reads the
answers — and the `relationship` column does not move by one digit on any set:

| set | routed (shipped) | oracle | every query (5.3) |
|---|---|---|---|
| | overall / `relationship` | overall / `relationship` | overall / `relationship` |
| ours/dev | +0.0 % / **+0.0 %** | −0.1 % / **−1.2 %** | −3.7 % / **−1.2 %** |
| ours/release | +0.0 % / **+0.0 %** | −0.6 % / **−4.2 %** | −0.7 % / **−4.2 %** |
| uv/dev | +0.0 % / **+0.0 %** | −1.6 % / **−43.1 %** | −1.6 % / **−43.1 %** |
| uv/release | +0.0 % / **+0.0 %** | +0.0 % / **+0.0 %** | −0.7 % / **+0.0 %** |
| uv-ingested/dev | +0.0 % / **+0.0 %** | −0.9 % / **−21.0 %** | −0.9 % / **−21.0 %** |
| uv-ingested/release | +0.0 % / **+0.0 %** | −0.7 % / **−3.8 %** | −3.2 % / **−3.8 %** |

The oracle and the unrouted arm are **identical on the `relationship` slice on all six
sets**, exactly and not approximately. The reason is arithmetic rather than empirical: the
bar is stated on that slice, routing only decides whether a leg runs on queries *outside* it,
and the leg already ran on the slice's cases in the unrouted arm. Whatever routing does, it
cannot do it there. Roadmap 5.11's hypothesis — that the losses were cases expansion should
never have touched — is half right and the wrong half is decisive: of the thirteen cases
expansion loses unrouted, **six are relationship cases**, which is where a perfect router
sends it on purpose.

**Routing is worth what it does to the collateral damage.** The same table read down the
overall column: unrouted the leg costs an operator 0.0–4.1 %, oracle-routed 0.0–1.6 %, and
with the shipped rules 0.0 % on every set — because the rules fire on three judged queries
and none of those three moves. That is a real improvement to an opt-in feature and it is not
a change of verdict.

**The symbol leg was already routed, and the vector leg must not be.** All three arms score
+0.0 % on every set for the symbol leg, because the leg has always tested each query token
for identifier-likeness before touching the store — the routing existed, in the leg, where a
plan could not report it. And spec 04 §2's *"vector as backfill"* reads as a licence to
withhold the vector leg from identifier queries, which is tempting because hybrid's one
losing slice at gate G2 was `exact` (ADR-0017) and that is where identifier queries live.
Measured, it is the wrong way round: withholding costs uv/dev 5.2 points of hybrid's gain
and turns its `exact` slice from +9.7 % to −0.5 %, and uv/release's from −1.6 % to −9.0 %.
The vector leg *helps* identifier queries on these corpora.

## Decision

**The planner is built, as spec 04 §2 words it, and its obligation is met.**
`mycelium.planner.plan_query` classifies a query into rules and the generators those rules
ask for; `mycelium search --explain`, `--json`, `mycelium_search`'s explain block and
`mycelium_explain` all carry the rules that matched, the generators requested, and a sentence
saying what was recognised. The field that held the profile name now holds a plan.

**The plan narrows; the configuration decides.** A plan may *withhold* a generator the
configuration enabled; it may never *enable* one the configuration disabled. This is the
load-bearing rule. Gate G2 set the vector leg's default and two ablations set the derived
legs' (ADR-0017, ADR-0075, ADR-0080) — a router able to switch a leg on would overturn three
measured verdicts with a regex, and the first symptom would be a benchmark moving for no
reason anyone could name. It is the same direction of safety `_serve_only` applies to the
serving policy (ADR-0024) and `--mode` to the verification ladder (ADR-0055): the narrow
direction is the one a mistake can be survived in.

**The graph leg is routed; the symbol leg's own gate moves into the planner; the vector leg
is not routed.** Each is the measurement above rather than a reading of the sentence. The
symbol move is a refactor with identical behaviour by construction — the predicate is the
same predicate — and it is worth making because a routing decision a plan cannot report is
not auditable, which is the whole of spec 04 §2's obligation.

**Signals are independent; every matched rule is reported, in the spec's order.** The table
reads as first-match-wins, and first-match-wins would mean a query that both names an
identifier and asks a relationship question silently loses its symbol lookup. So the
generators a plan asks for are the union of what its matched rules ask for. On the 133 judged
case-instances no query matches two rules, so this is a choice made in the safe direction
rather than a measured one, and it is recorded as such.

**`RELATIONSHIP_PHRASES` is the spec's two phrasings generalised to their verb family and no
further** — the dependency verbs in both voices, and the inverse-dependency form *"what
uses/reads/writes/calls X"*, which is *"what depends on"* with the arrow turned round. Its
membership is an English fact about a phrasing, in the same sense `STOPWORDS` is an English
fact about function words (ADR-0057), and its recall against the judged slice is **14 %**,
stated here and in the module rather than improved. The list that reaches 59 % was written by
reading the queries it had to catch, and adopting it would be fitting the router to the
benchmark, which D-010 forbids and this project has now refused sixteen times.

**`--related` is the reliable half of that cell, and it is a configuration signal rather than
a plan signal.** `mycelium search --related` and `mycelium_search`'s `related: true` enable
the graph leg for that one call — exactly as `--hybrid` enables the vector leg — and then
satisfy the routing rule. The planner itself still enables nothing. This is what makes the
mechanism coherent despite the weak phrase list: the caller knows what kind of question they
are asking, and spec 04 §2 puts their flag in the same cell as the phrasing for that reason.

**And the verdict: routing changes neither ablation, and both legs stay opt-in.** The
oracle's column is the proof that this is not a result about the rules chosen but about the
mechanism. What routing does change is the price of the flag, and that is stated where an
operator reads it.

## Alternatives Considered

- **Adopt the wider phrase list, which clears the gate on one set.** It does: on
  ours/release it reaches `relationship` +19.7 % and overall +2.6 %, rescuing `r-0018` and
  avoiding `r-0011`'s loss. It also loses 43.1 % on uv/dev and 21.0 % on uv-ingested/dev, and
  it was written by reading the queries. Rejected as textbook fitting: it helps exactly on the
  corpus whose queries were read and nowhere else, which is the shape ADR-0031 and ADR-0041
  refused fifteen times before this.
- **Let the planner enable a leg the configuration disabled**, so `--related` needs no
  config edit and relationship phrasing switches expansion on for the queries that want it.
  Rejected: it makes a regex the arbiter of three measured defaults. A user who typed
  "related to" would get a different ranking from one who did not, with no flag set and
  nothing in the configuration to explain it, and every benchmark in the project would move
  for reasons its own manifest could not record.
- **Withhold the vector leg from identifier queries**, spec 04 §2's *"vector as backfill"*.
  Rejected on the numbers above: the `exact` slice it would protect gets worse, not better.
  Recorded rather than skipped, because the sentence is in the specification and the next
  reader will look for it in the code.
- **First-match-wins, as the table's shape implies.** Rejected for a behaviour nobody
  measured: an identifier query with relationship phrasing would silently lose the symbol
  leg. The union is strictly more conservative and the corpora cannot tell the two apart.
- **Route the symbol leg by slice rather than by token.** Rejected — measured identical, and
  a router that reads a judged slice is not a router, it is an oracle. The oracle is reported
  as the upper bound it is and shipped as nothing.
- **Extend the phrase list until the slice is covered, then re-run.** Rejected as the
  previous bullet's mechanism, one iteration at a time. Any list reaching the whole slice on
  these corpora would be a list of these corpora's queries.
- **Teach the planner a model.** Refused by the specification itself — *"a small,
  deterministic, logged rule set — not a model call (v1)"* — and, after the oracle
  measurement, pointless: a perfect classifier does not move the gate's number.
- **Drop graph expansion now that routing cannot save it.** Genuinely arguable, and closer
  than it was at ADR-0075. Rejected for the reason that ADR held: the conditions under which
  expansion would matter are named and open (roadmap 5.7's barely-connected ingested corpora;
  documentation *about a tool* rather than about an API), the mechanism is behind a
  measured-off flag, and it now costs 0.0 % on the judged sets when enabled rather than up to
  4.1 %. Removing a mechanism that is both explainable and free is worse than keeping it.
- **Report the plan only on `--explain`.** Rejected: it is one small object built by a
  substring scan, and `mycelium_explain` exists precisely to be cheap enough to call whenever
  an answer looks wrong.

## Consequences

- **Spec 04 §2's obligation is met for the first time.** A response that explains itself
  carries the rules that matched, the generators they asked for, and why — on the CLI, in
  `--json`, and over MCP. `mycelium_explain`'s `plan` gains `rules`, `requested` and `why`
  beside the profile it used to hold alone.
- **The shipped ranking does not move, and that is checkable rather than claimed.** Both
  derived legs are off by default, so a default search plans exactly the legs it always ran —
  asserted directly in `tests/test_planner.py`. No baseline is re-blessed, no judged set is
  touched, gate G3 has nothing to re-run and `tools/check_frozen_release_sets.py` has no
  conjunction to refuse.
- **`retrieval_identity()` gains the routing rules**, because they decide whether a leg runs
  and are therefore part of a ranking exactly as the leg's own constants are (ADR-0064's
  rule). Gate G2's verdict is re-recorded in this change; the shipped ranking is unchanged,
  and the check that proves it is that the numbers reproduce.
- **The cost of turning expansion on falls to zero on the judged sets** — 0.0 % overall on
  all six, against 0.0–4.1 % before — and `[retrieval] graph_expansion`'s docstring says so
  beside the ablation it still loses.
- **`tools/measure_routing.py` joins the `retrieval` rung and CI**, with the same `--check`
  contract the other two ablations have: it fails when the code and the measurement disagree,
  never because an ablation was lost (ADR-0068). `--rules` scores the rule set as a
  classifier, because a router reported without its recall is reported by half.
- **`tools/measure_graph_expansion.py` gains `--every-query`**, so ADR-0075's arm stays
  reproducible after the leg became routed. Its default arm is now the leg as it ships.
- **The expansion tests ask for the leg the way a caller does.** They test the mechanism, so
  they pass `related=True`; the routing is `tests/test_planner.py`'s subject. Splitting them
  is what keeps a routing change from looking like a mechanism regression.
- **Latency is unchanged in any way worth measuring**: one casefold and one substring scan of
  a seventeen-entry tuple, plus the token regex the symbol leg already ran. No store access,
  no model, no I/O.
- **A limitation, stated rather than buried.** With the shipped rules the graph leg fires on
  three of 133 judged queries and on none of the nineteen the slice holds that a human would
  call a relationship question. The honest description of what ships is *an explainable
  opt-in mechanism the caller must ask for*, not an automatic one — and the follow-up is not
  a better regex but a corpus where the mechanism pays, which roadmap 5.7 and 5.19 are both
  about.
- **Threat model: no new boundary.** The planner reads the query string, which crosses B6
  (the MCP serving edge) and is already modelled there; it performs substring and token
  matching and reaches no store, no file and no network. A crafted query can at most ask for
  a leg the configuration must then permit — which is the narrowing rule's whole point.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §2 (the rule table and the explain
  obligation), §3 (the generators), §5 (the expansion and its gate), §7.3 (gate G2's shape);
  `.draft-specs/05-interfaces-and-plugins.md` §§3.1, 3.4 (the tool surfaces that report it).
- Decision log: D-009 (hybrid retrieval, transparent planner), D-010 (measure before
  believing; fix the product, not the benchmark).
- Re-runnable: `python tools/measure_routing.py`, `--rules`, `--leg symbol`, and
  `python tools/measure_graph_expansion.py --every-query` for ADR-0075's arm.
- Tests: `tests/test_planner.py`; the mechanism in `tests/test_expansion.py` and
  `tests/test_symbol_leg.py`.
