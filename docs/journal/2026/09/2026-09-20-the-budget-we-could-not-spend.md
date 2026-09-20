# 2026-09-20 — the budget we could not spend (roadmap 6.28)

- **Session scope:** roadmap 6.28 — our own side of the agent-task comparison cannot spend
  the budget it is given, and the fix moves a number in our favour.
- **PR:** #PRNUM (`feat/spend-the-budget`). Follows #177, merged as `e00d33e`.
- **Milestone 6:** 6.28 closed. Open: 6.29–6.36.
- **Decision it records:**
  [ADR-0143](../../../adr/0143-take-the-result-count-from-the-contract-and-sweep-it-like-the-incumbents.md).
  Report: [the budget we could not spend](../../../benchmarks/2026-09-20-the-budget-we-could-not-spend.md).

## Ten modelled no caller

`_mycelium_context` asked `search` for ten results whatever the budget said. The item
frames that as a constant that stopped being right when a parameter moved, which is true
and understates it: `mycelium_search` defaults `k` to **8** and caps it at **50**. Ten is
neither. It was not a model of a default caller or of a budget-aware one — it was a
literal nobody had revisited, in the one place where our side of a published comparison
gets its number.

`MAX_SEARCH_K = 50` is the cap the contract states, and the budget is what bounds the
answer. That is how the tool is built: `k` caps, `budget_tokens` limits. Asking for more
cannot cost more than the budget — it can only stop leaving the budget unspent.

## The second defect, found while fixing the first

The packing loop **stopped** at the first result that would not fit:

```python
if tokens + cost > budget:
    break
```

`handle_search` *skips* it into `omitted` and keeps filling from the rest of the ranking
(spec 05 §3.1). So one large passage early in a ranking cost our arm everything behind it.
Same family as the first: the harness disagreeing with the tool it claims to model.

Both corrections move the number our way, and that is exactly why the argument has to be
that neither is a tuning choice. Each one makes the harness agree with the tool — the cap
it states, and the packing it performs. D-010 asks for that argument and the band is the
evidence.

## The band, re-published

At the **shipped** 4 000-token budget the verdict barely moves: 16/22 unchanged here,
18 → 19 on `uv-docs`, 17 → 18 on the twin. At the top of the band it does:

| budget | this repository | `uv-docs` | ingested |
|---:|---|---|---|
| 4 000 | 16/22 | 19/22 | 18/22 |
| 8 000 | 18/22 | 21/22 | 19/22 |
| 16 000 | **19/22** | **22/22** | **21/22** |

against grep's 15/22, 13/22 and 11/22 there, for two to three times the context.

## The part worth keeping

Our constant is now swept beside the incumbent's two, and the sweep says something the fix
alone would have hidden: **at `k = 8`, the tool's own default, the arm still stops** — 16,
18, 17 of 22, however large the budget. The saturation was never only our literal. It is a
property of the tool's defaults, and it is now published rather than buried in a number
that happened to move.

That is the ADR-0131 rule applied to ourselves. The incumbent's two constants were swept
and published a week ago; ours was a literal, and an asymmetry in what gets audited is how
a measurement drifts in the direction nobody is watching.

## What it does not do

Documents read rises sharply — 9.27 at the shipped budget here against about five, 25.55
at 16 000. Whether two dozen documents is context or dilution is **6.29**'s question, and
this change does not prejudge it. The incumbent is untouched and its file band is
reproduced as a control. And nothing is armed: the verdict gate is still 7.3's, and
`--tasks --gate` still gates the suite's integrity rather than its rate. A better number
that nothing gates on is a better number, not a passed gate.
