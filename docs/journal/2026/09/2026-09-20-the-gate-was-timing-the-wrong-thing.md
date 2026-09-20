# 2026-09-20 — the gate was timing the wrong thing (roadmap 6.24)

- **Session scope:** roadmap 6.24 — arm gate G5 on the number spec 04 §1 actually states,
  now that 6.18 has removed the constant that made it unreachable.
- **PR:** #174 (`feat/gate-g5-on-the-tool-call`). Follows #173, merged as `c262269`.
- **Milestone 6:** 6.24 closed, 6.35 filed. Open: 6.25–6.35.
- **Decision it records:**
  [ADR-0139](../../../adr/0139-time-the-tool-call-in-the-harness-and-keep-the-retriever-as-a-floor.md).

## The decision came before the timer, because the item said so

*"The question is whether it may import `mycelium.mcp.tools` — a serving surface reaching
into an evaluation one — or whether the sample belongs in the run manifest instead, written
by whoever built the snapshot. Decide that before writing the timer."*

It resolves against the manifest, and the argument is the defect itself. A sample written
elsewhere puts the measurement in one place and the gate in another, with a hand-off in
between — which is exactly how G5 spent five milestones reading a number produced for a
different purpose. **A gate that measures its own subject cannot drift from it.**

The reach turned out to be cheaper than the item feared. `mycelium.mcp` does not import
`mycelium.eval`, so there is no cycle. The harness already imports `build.publish`,
`config`, `store` and `retrieval` — precisely the set `mcp.tools` sits on, so no layer is
added. And the `mcp` SDK is a *dev* dependency that `mycelium.mcp.server` does not use: it
implements the stdio transport itself, so a wheel-only install is untouched. The import
sits at the call site rather than at module scope, so the one place evaluation reaches into
serving is the place a reader is standing when they ask why.

## Two numbers, not one, and neither of them optional

| verdict | why |
|---|---|
| tool call p95 > 150 ms | the number the NFR names |
| retriever p95 > 150 ms | the floor — the only number that moves with the arm |
| tool call not measurable | **fails**, and says it was not measured |

The floor is kept rather than replaced because the handler uses the *shipped* configuration
whatever arm a run scored: without it, an ablation that was pathologically slow would sail
through. The grep incumbent reads 426 ms in CI and must keep saying so.

The third row is this item's own lesson applied one level up. G5 stayed green for five
milestones partly because its output politely said it was *"a floor, not the measurement
spec 04 §1 asks for"* — ADR-0053's point exactly: a caveat in the output is a caveat nobody
reads. Treating *nobody could measure it* as a pass is the same mistake with a different
subject.

## Measured before arming

Clean worktree, 226 documents, a hundred calls after a discarded warm-up — measured first
by hand, then read back out of the armed gate:

| corpus | chunks | p50 | p95 | retriever p95 |
|---|---:|---:|---:|---:|
| this repository | 1 670 | 58 ms | **98 ms** | 58 ms |
| `eval/corpora/uv-docs` | 568 | 35 ms | **40 ms** | 24 ms |
| `eval/corpora/uv-docs-ingested` | 526 | 33 ms | **37 ms** | 18 ms |

The number moves with the machine and the record says so: a quieter pass, taken before the
ladder ran, read 84 / 45 / 45. Worst observed is **98 ms**, 1.5× headroom, and that is the
number to hold this gate against — not the best reading. It is also the honest figure to set
against the flake risk a wall-clock bar in CI carries — 6.18's own guards deliberately count mechanisms rather than
milliseconds for that reason. Two things make it acceptable here. The sample is **a hundred
rather than fifty**: at fifty the p95 is the third-slowest call, so one garbage collection
sets the verdict, while at a hundred it takes six. And CI is *faster* than this machine, not
slower — the same gate's retriever number reads **13 / 5 / 5 ms** on `ubuntu-24.04` against
58 / 24 / 18 here. The first CI run of this change is the real measurement.

## What else the budget table says

Spec 04 §1 has five rows and only the last one is gated by anything: plan + candidates
60 ms, fusion 20 ms, graph expansion 30 ms, stitch + pack 40 ms have never been measured
against. That is the same defect one level down, and it matters in the direction 6.21
already pointed — at 10⁵ chunks the warm query alone is 1 816 ms p95, and a total cannot say
which stage spent it. Filed as **6.35** with its own open question: whether to time the
stages on the query path or in a bench that reconstructs them, and whether four more gates
is the right answer at all before that path is answered.

The limit this does not lift: the budget is defined at the reference profile, and gating a
1 670-chunk corpus at 150 ms is still a floor. It is now a floor on the right subject, which
is all this change claims.
