# ADR-0143: Take the result count from the contract, and sweep it like the incumbent's

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.4
- **Related:**
  [ADR-0022](0022-measure-the-agent-loop-without-an-agent.md) (the comparison, and what it
  measures instead of a model),
  [ADR-0131](0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-along.md)
  (the band, and the rule that a constant the verdict depends on is swept and published),
  [ADR-0135](0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md)
  (the corpus the verdict gates on),
  [ADR-0128](0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md)
  (declare a constant and pin it against its source, rather than importing a subsystem to
  read it); spec 04 §7.4, spec 05 §3.1; D-010; roadmap 6.22, 6.28; report
  `docs/benchmarks/2026-09-20-the-budget-we-could-not-spend.md`

## Context

`_mycelium_context` is our side of the agent-task comparison: what `mycelium_search` would
hand an agent, for one task, under a token budget. It called
`search(store, task.prompt, limit=10)` — **ten results, whatever the budget said**.

Two things follow, and only the first was filed.

**The arm could not spend its budget.** Ten results is about 3 100 tokens on this corpus,
so from a 4 000-token budget upward the arm stopped improving while the incumbent went on
scaling with the budget it was given. At 16 000 tokens the comparison reported 17/22 at
2 957 median for us against grep's 16/22 at 35 504 — a lead, and a *smaller* one than the
truth, which is the direction D-010 holds to a higher standard.

**Ten models no caller.** `mycelium_search` defaults `k` to **8** and caps it at **50**.
Ten is neither. The number was not a model of a default caller, or of a budget-aware one;
it was a literal nobody had revisited.

A third thing was found while fixing the first, and it is the same kind of infidelity: the
packing loop **stopped** at the first result that would not fit, where the tool *skips* it
and keeps filling from the rest of the ranking (`omitted`, spec 05 §3.1). One large passage
early in a ranking cost the arm everything behind it.

## Decision

**Take the count from the contract, make it a parameter, and sweep it in the published
band.**

- `MAX_SEARCH_K = 50` — the cap `mycelium_search` states — is what the arm asks for. The
  budget is what bounds the answer, which is how the tool is designed: `k` is a cap,
  `budget_tokens` is the limit. Asking for more cannot cost more than the budget; it can
  only stop leaving the budget unspent.
- `run_task_suite(..., search_k=...)` makes it a parameter, as the incumbent's two already
  were, and `tools/measure_agent_task_band.py` sweeps it at the widest budget.
- The packing loop **skips** an over-budget result instead of stopping, mirroring
  `handle_search`.
- `MAX_SEARCH_K` is **declared** in `mycelium.eval.tasks` and pinned against
  `mycelium.mcp.tools._MAX_K` by a test, rather than imported: the suite must not pull the
  serving surface into its import graph to read one integer (the shape roadmap 6.18
  removed from the configuration path), and a declaration that can drift silently is worse
  than either.

**Both corrections move the number in our favour, and neither is a tuning choice.** Each
one makes the harness agree with the tool it claims to model: the cap it states, and the
packing it performs. That is the argument D-010 requires — fidelity, not favour — and the
band below is the evidence rather than the assertion.

## Consequences

**At the shipped 4 000-token budget the verdict barely moves**: 16/22 unchanged on this
repository, 18 → 19 on `uv-docs`, 17 → 18 on the ingested twin. The change is at the top
of the band:

| budget | this repository | `uv-docs` | ingested |
|---:|---|---|---|
| 4 000 (shipped) | 16/22 | 19/22 | 18/22 |
| 8 000 | 18/22 | 21/22 | 19/22 |
| 16 000 | **19/22** | **22/22** | **21/22** |

against grep at 15/22, 13/22 and 11/22 at that budget, for two to three times the context.

**The saturation was never only the literal, and the band now says so.** Swept at the
widest budget, `k = 8` — the tool's *default* — reaches 16/22, 18/22, 17/22 and stops. A
caller that does not raise `k` cannot spend a large budget either, which is a fact about
the tool's defaults rather than about this harness, and it is published rather than
buried.

**Documents read rises sharply**: 9.27 at the shipped budget on this repository against
about five before, and 25.55 at 16 000. Handing a model passages from two dozen documents
may be context or may be dilution; roadmap **6.29** owns that question and this change does
not prejudge it.

**The incumbent is untouched.** Nothing here changes `_grep_context`, and the file band is
reproduced in the report as a control.

**What this does not do.** It does not arm anything: the agent-task *verdict* gate is still
unarmed and still 7.3's, and `mycelium eval --tasks --gate` continues to gate the suite's
*integrity* rather than its rate (ADR-0120). A better number that nothing gates on is a
better number, not a passed gate.
