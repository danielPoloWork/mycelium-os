# `/eados debug` — governed defect investigation (reproduce → root-cause → fix → ledger)

Walks a defect from report to closed, governed record. **Cross-cutting** (ADR-0019 class 3 — run
it in any phase, like `/eados status`): advisory and **non-state-advancing** — it never writes
`delivery_state.phase` and never proposes a transition. Everything it *does* write is fully
governed: the **tech-lead** authors the fix (owns `src/**`, drafts the ledger record), the
**reviewer** verifies red → green, and the record lands in the **bug ledger**
(`docs/bugs/**` — scaffolded into every generated repo from
[`templates/docs/bugs/`](../../templates/docs/bugs/README.md.tmpl); its structural integrity is
the generated `tools/consistency_lint.py` `bugs` check). This file is the **shape the Wave-2
cross-cutting code commands share** — `refactor` (#243), `optimize` (#244), and `testcases`
(#246) follow it.

## Preconditions

- **A manifest is required (ADR-0019 boundary).** The command runs only against an initialized
  project — a repository whose manifest carries `delivery_state`. Pasted or standalone code is
  **refused and routed**: greenfield → [`/eados init`](init.md); an existing ungoverned repository
  → [`/eados adopt`](adopt.md) (#247 — the brownfield intake). A plain *question*
  about code stays the Step-0 triage question route (`0-question` in
  [`../triage.yaml`](../triage.yaml) — answered directly, no command run).
- **Falsifiable intake.** The observed failing behavior — a bug report, a failing CI job, or the
  user's description — must state (or be restatable as) **expected vs. actual plus the trigger**.
  Vague intake ("sometimes crashes", "feels slow lately") is **refused** the same way interview
  Phase 5 refuses an untestable requirement: name the missing observation (the input, the
  environment, the expected result) and stop until it arrives.

## Procedure

1. **Intake** — restate the defect as *expected vs. actual + trigger*; classify `severity`
   (`low`/`medium`/`high`/`critical`) and `reporter` (`internal`/`third-party`) per the ledger
   vocabulary. Before touching anything, confirm the acting role may write the surfaces the run
   will touch:
   ```bash
   python .eados-core/tools/authority_check.py tech-lead src/<path> docs/bugs/<record> CHANGELOG.md
   ```
2. **Reproduce first** — encode the failure as a **failing test** *before* any fix work (the
   generated repo's `AGENTS.md` §7 bug-ledger discipline, applied as a gate): the smallest test
   that fails *for the reported reason* — assert the expected behavior, watch it fail, keep the
   failure output. A defect that cannot be reproduced is **still recorded** — as
   `cannot-reproduce` / `rejected` / `duplicate`, so the triage trail is preserved — and the run
   **stops there: no fix ships without a red reproduction.**
3. **Isolate & root-cause** — narrate the hypothesis chain, each link falsifiable:
   *observation → hypothesis → experiment → verdict*, repeated until the mechanism is pinned.
   What is recorded is the **root cause** (the defective assumption or code path), never just the
   symptom; for a third-party report, this is where the report is substantiated or downgraded.
4. **Fix** — **one logical change**, authored by the tech-lead inside its authority (`src/**`).
   The reproduction test flips green **and stays in the suite** as the regression guard. No
   drive-by cleanup or opportunistic refactoring rides along — that is `/eados refactor` (#243).
   The **reviewer** verifies: the red → green evidence, the fix's scope, and structured findings
   the author resolves.
5. **Record & close** — draft the governed record and the PR, then hand off to the human:
   - the **ledger entry** `docs/bugs/<YYYY>/<MM>/BUG-NNNN-<slug>.md` (next free monotonic id) from
     [`templates/docs/bugs/template.md`](../../templates/docs/bugs/template.md) — id, root cause,
     the fix PR, the regression-test reference — plus its index row in `docs/bugs/README.md`;
     `status: fixed` and `fixed-in` flip in the same PR as the fix;
   - the `CHANGELOG` **`Fixed`** line, same PR;
   - the pre-PR congruence gate — the ledger's structural integrity is mechanical:
     ```bash
     python tools/consistency_lint.py        # the `bugs` check, in the generated repo
     ```
   - the **draft PR** with the standard cross-links (`{pr, rfc, milestone, commit, release}` per
     the `git` spec). **The human opens and merges** (`AGENTS.md` §6) — one logical change, one PR.

## Worked example — a fixture defect, end-to-end

The reference fixture (`pbr-cpp-memory-pool`, `orchestrator/examples/reference.yaml`) reports:
*"releasing the same block twice corrupts the free list — later acquires return overlapping
blocks"*. The run, step by step:

1. **Intake** — expected: a double `release()` is rejected (or a no-op per spec §error-model);
   actual: the free list links the block twice and two `acquire()` calls hand out the same
   address. Trigger: `release(p); release(p); acquire(); acquire()`. `severity: high`
   (memory corruption), `reporter: internal`. Authority check passes for `tech-lead`.
2. **Reproduce** — `test/pool_double_release_test.cpp` asserts the second `release(p)` is
   rejected and subsequent acquires are distinct — it **fails** on the corrupted free list.
3. **Root-cause** — hypothesis chain lands on: `release()` pushes the block onto the free list
   without checking membership; the root cause is the **missing already-free guard**, not the
   overlapping acquires (the symptom).
4. **Fix** — one change in `src/pool.cpp` (guard + the spec's error return); the reproduction
   test flips green and stays as the regression guard; the reviewer confirms red → green.
5. **Record** — `docs/bugs/2026/07/BUG-0001-double-release-corrupts-free-list.md`
   (`status: fixed`, `fixed-in: v1.0.1`, root cause + PR + test all cross-linked), index row
   added, `CHANGELOG` `Fixed` line, `tools/consistency_lint.py` green — the drafted PR carries
   the ledger record, the regression test, and the fix as **one** logical change; the human
   merges it.

## Boundary

Investigation, one fix, and a governed record — nothing else. The command **never advances
state** (no `delivery_state.phase` write, no proposed transition — it is not a phase and does not
become one); it **never fixes without a red reproduction**, never records an unsubstantiated
report as a real defect (`cannot-reproduce`/`rejected`/`duplicate` keep the trail honest), and
never lets the fix grow past one logical change. The agent reproduces, root-causes, fixes, and
**drafts**; the human opens, reviews, and merges the PR (`AGENTS.md` §6). Refusals are part of
the contract: vague intake and manifest-less code are routed, not guessed at (ADR-0019).
