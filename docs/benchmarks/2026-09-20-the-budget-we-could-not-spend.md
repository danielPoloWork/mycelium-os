# Benchmark Report: the budget we could not spend

- **Date:** 2026-09-20
- **Version / commit:** v0.5.0 @ `e00d33e` **plus the change this report is about** (roadmap 6.28)
- **Environment:** see the three manifests — the machine of record, as in the
  [reference-profile report](2026-09-17-reference-profile.md):
  [this repository](manifests/2026-09-20-the-budget-we-could-not-spend-this-repository.json),
  [`uv-docs`](manifests/2026-09-20-the-budget-we-could-not-spend-uv-docs.json),
  [the ingested twin](manifests/2026-09-20-the-budget-we-could-not-spend-uv-docs-ingested.json)
- **Command:** `python tools/measure_agent_task_band.py <root> --manifest <path>`
- **Roadmap:** 6.28 · **Decision:** [ADR-0143](../adr/0143-take-the-result-count-from-the-contract-and-sweep-it-like-the-incumbents.md)

## Scenario

[The incumbent reads a window](2026-09-18-the-incumbent-reads-a-window.md) published the
comparison as a *band* over the two constants of the incumbent's model — how much one read
costs, and how many files the loop opens — because a verdict that depends on a number
nobody varied is a verdict nobody can check (ADR-0131).

Our side of the comparison has one constant too, and it was not in the band. It was a
literal `limit=10` inside `_mycelium_context`, so the Mycelium arm asked for ten results
whatever budget the caller declared. Roadmap 6.22 found it and filed it rather than fixing
it in passing, because it moves a number in our favour and D-010 holds that to a higher
standard.

This report is the re-published band, with our constant swept beside theirs.

## Results

### Both strategies as the caller's budget moves

The budget is also the incumbent's read window. `mycelium` now asks for
`MAX_SEARCH_K = 50` — the cap `mycelium_search` states — and lets the budget truncate.

**This repository** — 22 tasks, all scorable:

| budget | mycelium | tokens (mean) | grep | tokens (mean) |
|---:|---:|---:|---:|---:|
| 1 000 | 10/22 | 985 | 9/22 | 4 491 |
| 2 000 | 15/22 | 1 979 | 14/22 | 8 998 |
| **4 000** (shipped) | **16/22** | **3 977** | **15/22** | **15 157** |
| 8 000 | 18/22 | 7 978 | 14/22 | 24 155 |
| 16 000 | **19/22** | 14 914 | 15/22 | 34 215 |

**`uv-docs`** — the corpus the verdict gates on (ADR-0135):

| budget | mycelium | tokens (mean) | grep | tokens (mean) |
|---:|---:|---:|---:|---:|
| 1 000 | 14/22 | 987 | 10/22 | 4 100 |
| 2 000 | 16/22 | 1 984 | 12/22 | 8 571 |
| **4 000** (shipped) | **19/22** | **3 983** | **13/22** | **14 653** |
| 8 000 | 21/22 | 7 967 | 13/22 | 18 282 |
| 16 000 | **22/22** | 12 369 | 13/22 | 18 282 |

**The ingested twin:**

| budget | mycelium | tokens (mean) | grep | tokens (mean) |
|---:|---:|---:|---:|---:|
| 1 000 | 15/22 | 991 | 9/22 | 4 209 |
| 2 000 | 16/22 | 1 989 | 11/22 | 8 755 |
| **4 000** (shipped) | **18/22** | **3 988** | **11/22** | **15 253** |
| 8 000 | 19/22 | 7 986 | 11/22 | 19 008 |
| 16 000 | **21/22** | 14 020 | 11/22 | 19 008 |

### Our own constant, at the widest budget

`k` binds before the budget does, which is the finding rather than a footnote: **a caller
that leaves `k` at the tool's default cannot spend a large budget either.**

| `k` | this repository | `uv-docs` | ingested |
|---:|---:|---:|---:|
| 8 (the tool's default) | 16/22 @ 2 620 | 18/22 @ 2 000 | 17/22 @ 2 202 |
| 10 (the literal this suite carried) | 16/22 @ 3 234 | 18/22 @ 2 466 | 17/22 @ 2 816 |
| 20 | 17/22 @ 6 540 | 19/22 @ 4 934 | 18/22 @ 5 738 |
| **50** (the contract's cap) | **19/22 @ 14 914** | **22/22 @ 12 369** | **21/22 @ 14 020** |

## What moved, and what did not

**At the shipped 4 000-token budget the verdict barely moves**: 16/22 unchanged on this
repository, 18 → 19 on `uv-docs`, 17 → 18 on the ingested twin. The change is at the top
of the band, which is exactly what the item said — the arm could not spend a budget it was
given.

**The incumbent's numbers are unchanged.** Nothing in this change touches `_grep_context`,
and the file band is reproduced here as a control: 1/22, 4/22, 9/22, 15/22 on this
repository, the same shape ADR-0131 published.

**Documents read rises sharply** — 9.27 at the shipped budget on this repository against
about five before, and 25.55 at 16 000. Asking for fifty results and spending a large
budget means handing the model passages from two dozen documents. Whether that is context
or dilution is roadmap **6.29**'s subject, and this report does not settle it.

## Limits

- **One machine, one run per corpus**, and the token figures are medians over 22 tasks: a
  single task's passage sizes move a mean here more than they would on a judged set of
  four hundred.
- **The suite measures the substrate, not a model** (ADR-0022). *Evidence found* means the
  required passages were in what the agent received; whether a model would have used them
  is a question this instrument does not ask and 7.3 owns.
- **`k = 50` models a budget-aware caller**, not the default one. The table above is
  published precisely so that the difference is visible rather than assumed.

## Reproduce

```bash
python tools/measure_agent_task_band.py . \
  --manifest docs/benchmarks/manifests/2026-09-20-the-budget-we-could-not-spend-this-repository.json
python tools/measure_agent_task_band.py eval/corpora/uv-docs \
  --manifest docs/benchmarks/manifests/2026-09-20-the-budget-we-could-not-spend-uv-docs.json
python tools/measure_agent_task_band.py eval/corpora/uv-docs-ingested \
  --manifest docs/benchmarks/manifests/2026-09-20-the-budget-we-could-not-spend-uv-docs-ingested.json
```
