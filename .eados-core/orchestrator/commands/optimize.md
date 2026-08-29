# `/eados optimize` — measure-first performance optimization (against a numeric NFR budget)

Moves a measured performance number toward a **declared numeric budget** — never "make it
faster" on a hunch. **Cross-cutting** (ADR-0019 class 3 — run it in any phase, like
`/eados status`): advisory and **non-state-advancing** — it never writes `delivery_state.phase`
and never proposes a transition. Everything it *does* write is fully governed: the **tech-lead**
authors the change (owns `src/**`, drafts the `docs/benchmarks/` record), the **reviewer** returns
the verdict on the readability/complexity cost the speed-up buys. It follows the shape
[`debug.md`](debug.md) set for the Wave-2 cross-cutting code commands — the discipline that
distinguishes `optimize` is **measure-first**: a number before the change and a number after, both
recorded, or the run does not proceed.

## Preconditions

- **A manifest is required (ADR-0019 boundary).** The command runs only against an initialized
  project — a repository whose manifest carries `delivery_state`. Pasted or standalone code is
  **refused and routed**: greenfield → [`/eados init`](init.md); an existing ungoverned repository
  → [`/eados adopt`](adopt.md) (#247 — the brownfield intake). A plain *question*
  about code stays the Step-0 triage question route (`0-question` in
  [`../triage.yaml`](../triage.yaml) — answered directly, no command run).
- **A numeric target.** The goal is a **number** from spec §3's non-functional budgets or the
  domain's hard `nfr_axes` — `p99 < 5 ms`, `cold-start < 2 s`, `LCP < 2.5 s`, `60 fps sustained`,
  `RAM < 512 MB`. "Make it faster" / "it feels slow" with no number is **refused** exactly as the
  interview's Phase 5 refuses an untestable requirement: elicit the numeric target first (the
  Phase-5 testability follow-up), and do not proceed on an adjective.

## Procedure

1. **Target** — state the single numeric goal and the axis it belongs to (spec §3 or the domain's
   `nfr_axes`), and the current distance from it. Confirm the acting role may write what the run
   will touch:
   ```bash
   python .eados-core/tools/authority_check.py tech-lead src/<path> docs/benchmarks/<report>
   ```
2. **Baseline** — run the **benchmark suite** and record the configuration to the
   `docs/benchmarks/` discipline (machine, toolchain, build config, commit SHA; warm-up,
   iterations, median **and** spread). The baseline is the number the change is judged against —
   no baseline, no accepted optimization. If `capabilities.bench` is **off**, enabling it (the CI
   bench job + `docs/benchmarks/`) is **step zero** — an optimization with no reproducible harness
   is a claim, not evidence.
3. **Profile → change** — locate the hotspot **with evidence** (a profile, not a guess), then
   apply **one** targeted change. No speculative rewrites, no bundle of unrelated tweaks: one
   change whose effect the re-measure can attribute.
4. **Re-measure** — re-run the suite on comparable hardware and **accept the change only if** the
   number moves toward budget **with no regression**: the test suite stays green (correctness
   preserved), and the `reviewer` judges the readability/complexity cost worth the gain. A change
   that hits the number but tangles the code, or that wins on noisy hardware only, is **rejected**
   — record the negative result and stop.
5. **Record & close** — write the **before/after numbers** (with the environment) to a
   `docs/benchmarks/` report and its index row, and restate them in the PR body; draft the gated
   PR with the standard cross-links. **The human opens and merges** (`AGENTS.md` §6) — one logical
   change, one PR.

## Worked example — a fixture with a bench suite, end-to-end

The reference fixture (`pbr-cpp-memory-pool`, `capabilities.bench: true`) has spec §3 budget
**`acquire() p99 < 200 ns`**; the recorded baseline sits at `p99 = 310 ns`. The run:

1. **Target** — axis `performance`, numeric goal `p99 < 200 ns`, current `310 ns` (55% over).
   Authority check passes for `tech-lead`.
2. **Baseline** — `cmake --build --preset bench` on the recorded machine; the
   `docs/benchmarks/` report pins CPU/RAM/OS/toolchain/commit, median + p99 over N warm
   iterations.
3. **Profile → change** — the profile shows `p99` dominated by a per-`acquire()` free-list scan;
   the one change replaces the linear scan with an intrusive free-list head (O(1) pop).
4. **Re-measure** — `p99 = 150 ns` (under budget), the correctness suite stays green, and the
   reviewer judges the intrusive-list change a net readability win. Accepted.
5. **Record** — `docs/benchmarks/2026/07/acquire-p99-intrusive-freelist.md` carries
   `310 ns → 150 ns` with the full environment; the index row is added; the PR body restates the
   before/after; the human merges the one-change PR.

**Refusal path.** "the pool feels slow, make `acquire()` faster" with no number is refused: the
command elicits the axis + numeric budget (spec §3 / `nfr_axes`) and does not profile or change
anything until a target like `p99 < 200 ns` exists.

## Boundary

Measure-first movement of one number toward one budget, and a governed record — nothing else.
The command **never advances state** (no `delivery_state.phase` write, no proposed transition — it
is not a phase); it **never optimizes without a numeric target** (an adjective is refused and
routed to elicitation); it **never accepts a change without a before/after measurement** on
comparable hardware; and it **never changes behavior** (a green suite is the correctness contract —
a defect belongs to [`/eados debug`](debug.md), a pure structure/readability change with no number
to [`/eados refactor`](refactor.md)). It refuses manifest-less code, routing rather than guessing
(ADR-0019). The agent targets, measures, profiles, changes, re-measures, and **drafts**; the human
opens, reviews, and merges the PR (`AGENTS.md` §6).
