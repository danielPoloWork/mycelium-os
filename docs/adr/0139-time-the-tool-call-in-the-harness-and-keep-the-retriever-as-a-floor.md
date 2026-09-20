# ADR-0139: Time the tool call in the harness, and keep the retriever as a floor

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§1, 7.3
- **Related:**
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the reference profile that found this, and the three budgets it missed),
  [ADR-0128](0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md)
  (which removed the constant that made arming this impossible),
  [ADR-0022](0022-measure-the-agent-loop-without-an-agent.md)
  (the precedent for measuring a substrate and naming what the measurement leaves out),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (gate on what the claim is about),
  [ADR-0049](0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md) (the incumbent is
  reported, never gated); spec 04 §§1, 7.3, 7.5; NFR-2; roadmap 6.4, 6.18, 6.21, 6.24

## Context

Spec 04 §1 states one end-to-end budget — **`mycelium_search` p95 ≤ 150 ms** — and gate G5
is *"budgets in §1 … measured on the reference profile"*. What `_gate_g5` actually read was
`overall.latency_p95_ms`, which `_evaluate_case` times around the **retriever**, inside the
harness.

The tool call is not the retriever. It also resolves the published snapshot, reads the
configuration, opens the store and packs the answer to a token budget. Those wrappers were
**274 ms of constant** — more than the entire budget, on any corpus — until roadmap 6.18
cached the worst of them (ADR-0128). So for five milestones the gate ran green over a call
that missed its own budget on **every corpus measured**, and it took a separate instrument,
6.4's reference profile, to see it at all.

Nothing was hidden. The gate said in its own output that it was *"a floor, not the
measurement spec 04 §1 asks for"* — which is precisely the property ADR-0053 says selects
for being ignored.

6.18 removed the constant, and that is what makes this worth arming rather than merely
noting: **the gate passes today**, so arming it is not a change that fails CI on arrival.

The filing item named the decision to take first: may an *evaluation* surface import a
*serving* one, or does the sample belong in the run manifest, written by whoever built the
snapshot?

## Decision

**The harness times `mycelium_search` itself, and gate G5 reads that number.** The
retriever's p95 is kept beside it as a floor, and **both** must be within budget.

### Why not the manifest

A sample written by whoever built the snapshot puts the measurement in one place and the
gate in another, with a hand-off in between. That is the shape of the defect being fixed:
G5 already read a number somebody else produced for a different purpose, and nobody noticed
for five milestones because the two were never the same artifact. A gate that measures its
own subject cannot drift from it.

### Why the import is sound

- **No cycle**: `mycelium.mcp` does not import `mycelium.eval`, and never will — the
  dependency runs one way.
- **No new layer**: the harness already imports `mycelium.build.publish`,
  `mycelium.config`, `mycelium.store` and `mycelium.retrieval`. `mycelium.mcp.tools` sits on
  exactly that set and adds none of its own.
- **No new dependency**: the `mcp` SDK is a *dev* dependency, and
  `mycelium.mcp.server` implements the stdio JSON-RPC transport itself rather than
  importing it, so a wheel-only install is unaffected.
- The import is made **at the call site rather than at module scope**, so the one place the
  evaluation surface reaches into the serving one is the place a reader is standing when
  they ask why.

### What is measured

A hundred of the run's own queries, **spread across the case set by stride** rather than
taken from its front — cases are ordered by id, ids cluster by slice, and the first hundred
of a release set are one kind of question, which is one kind of query plan. The handler is
called as a client calls it (default `k`, `include_text` full, no filters). **One warm-up
call is discarded**, because §1 states the budget for a *warm store* and the first call in a
process pays imports and a cold page cache that no steady-state caller pays.

A hundred rather than fifty is a decision about **flake, not precision**: at fifty the p95
is the third-slowest call, so one garbage collection or one noisy neighbour on a shared
runner sets the number the gate reads. At a hundred it takes six.

The result is cached per repository and snapshot for the life of the process. The tool call
is a property of the **repository**, not of the arm: `handle_search` uses the shipped
configuration whatever retriever a run scored, and the ablation tools score one root a dozen
times in a single process.

### What the gate does with it

| condition | verdict |
|---|---|
| tool call p95 ≤ 150 ms **and** retriever p95 ≤ 150 ms | pass |
| tool call over budget | **fail** — the number the NFR names |
| retriever over budget | **fail** — the floor, and the only number that moves with the arm |
| tool call not measurable | **fail**, reported as *not measured* |

The last row is the item's own lesson applied one level up: a gate that reads *nobody could
measure it* as a pass is how this one stayed green.

The retriever floor is kept rather than replaced because it is the only number that responds
to the arm under test, so a change making an *ablation* pathologically slow still trips G5 —
the grep incumbent already reads 426 ms in CI, and it must keep saying so.

## Consequences

**Measured before arming**, then read back out of the armed gate itself (clean worktree,
226 documents, sample of 100 after a discarded warm-up):

| corpus | chunks | `mycelium_search` p50 | p95 | retriever p95 |
|---|---:|---:|---:|---:|
| this repository | 1 670 | 58 ms | **98 ms** | 58 ms |
| `eval/corpora/uv-docs` | 568 | 35 ms | **40 ms** | 24 ms |
| `eval/corpora/uv-docs-ingested` | 526 | 33 ms | **37 ms** | 18 ms |

All three pass. **The number moves with the machine, and saying so is part of the record**:
a quieter pass of the same corpora, taken before the gate ladder ran, read 84 / 45 / 45 ms
against the 98 / 40 / 37 above. Worst observed is **98 ms**, which is 1.5× headroom — the
honest margin to hold this gate against, not the best reading.

The margin in CI is wider, not narrower. The same gate's *retriever* number reads
**13 ms / 5 ms / 5 ms** on `ubuntu-24.04` against 58 / 24 / 18 here, so the Linux runners
are several times faster than this Windows machine at the work being timed. The first CI
run of this change is the real measurement, and it is the one to quote afterwards.

**Cost**: about five seconds per repository and snapshot, once per process — six gated
invocations in the ladder and in CI, each paying it once.

**The manifest records it.** `EvalRunManifest.tool_call` carries the calls and both
percentiles, so spec 04 §7.5's rule holds for the number the gate now reads: a reader can
check the verdict instead of trusting it. The field is optional, so manifests written before
today still load, and a gate never reads an absence as a pass.

**What this does not fix, and is filed rather than absorbed.** Spec 04 §1's budget table has
five rows — plan + candidates 60 ms, fusion 20 ms, graph expansion 30 ms, stitch + pack
40 ms, end-to-end 150 ms — and only the last is gated by anything. The four stage budgets
have never been measured against, which is the same defect one level down: roadmap **6.35**.

**The honest limit is unchanged.** The budget is defined against the 10⁵-chunk reference
profile, where the warm query *alone* is 1 816 ms p95 (roadmap 6.21). Gating a 1 662-chunk
corpus at 150 ms remains a floor — it is now a floor on the right subject, which is the
whole of what this ADR claims.
