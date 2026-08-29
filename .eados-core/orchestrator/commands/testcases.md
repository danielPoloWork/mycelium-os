# `/eados testcases` — governed unit/integration test generation (QA-owned)

Generates tests that **prove a requirement**, against the spec's §6 verification strategy.
**Cross-cutting** (ADR-0019 class 3 — run it in any phase, like `/eados status`): advisory and
**non-state-advancing** — it never writes `delivery_state.phase` and never proposes a transition.
It is the **first cross-cutting code command owned by the `qa-engineer`** (#245), not the
tech-lead: the `qa-engineer` authors the suite under `src/test/**` (the ownership record it
already holds), and the **reviewer** enforces the coverage bar the new tests move. It follows the
shape [`debug.md`](debug.md) set for the Wave-2 cross-cutting code commands — what distinguishes
`testcases` is that its deliverable **is** the tests: a suite that runs **green** against today's
code, or is deliberately **`xfail`** with a linked defect.

## Preconditions

- **A manifest is required (ADR-0019 boundary).** The command runs only against an initialized
  project — a repository whose manifest carries `delivery_state`. Pasted or standalone code is
  **refused and routed**: greenfield → [`/eados init`](init.md); an existing ungoverned repository
  → [`/eados adopt`](adopt.md) (#247 — the brownfield intake). A plain *question*
  about code stays the Step-0 triage question route (`0-question` in
  [`../triage.yaml`](../triage.yaml) — answered directly, no command run).
- **A testable target.** One unit or behavior per run, tied to a **spec §6** verification claim
  (or a §2–§3 requirement the tests will prove). A vague or untestable target ("add some tests",
  "improve coverage" with no named behavior) is **refused** exactly as interview Phase 5 refuses
  an untestable requirement: name the unit and the property it must satisfy first, and do not
  generate against an adjective.

## Procedure

1. **Intake** — state the target unit/behavior and the **spec §6** verification strategy it
   falls under (unit, integration, property, edge/error-path). Confirm the acting role may write
   the surface before authoring:
   ```bash
   python .eados-core/tools/authority_check.py qa-engineer src/test/<path>
   ```
2. **Generate** — author unit and/or integration tests against §6 using the **project profile's
   test toolchain** (the profile's `commands.test`; e.g. the reference fixture runs
   `ctest --preset debug`). Tests land under **`src/test/**`** (the `qa-engineer`'s ownership,
   #245), named for the behavior they prove, each asserting the expected result — not merely
   exercising the code path. A property that generalizes better than an example becomes a
   property-based test.
3. **Verify & record** — run the generated suite against the current code and record the outcome:
   - **green** — the suite passes against today's behavior; it enters the coverage the **reviewer**
     enforces (`AGENTS.md` §10) and stands as a regression guard;
   - **`xfail`** — a test that *should* pass but does not has found a **defect**: mark it `xfail`
     and hand the defect to [`/eados debug`](debug.md) (#242), linking the resulting bug-ledger
     record — a generated test never silently documents a bug as "expected".
   Then draft the gated PR with the standard cross-links. **The human opens and merges**
   (`AGENTS.md` §6) — one logical change, one PR.

## Worked example — a fixture spec §6, end-to-end

The reference fixture (`pbr-cpp-memory-pool`, profile test command `ctest --preset debug`) has a
spec §6 claim: *"every `acquire()` returns a distinct, correctly-aligned block; a double
`release()` is rejected."* The run:

1. **Intake** — target: `Pool::acquire()` distinctness + alignment, and `release()`
   double-free rejection (spec §6, unit + edge/error-path). Authority check passes for
   `qa-engineer`.
2. **Generate** — `src/test/cpp/.../pool_acquire_distinctness_test.cpp` (N acquires are pairwise
   distinct and aligned) and `pool_double_release_test.cpp` (the second `release()` is rejected),
   authored against the `ctest` harness.
3. **Verify & record** — distinctness/alignment run **green** and enter the coverage the reviewer
   gates. The double-release test **fails** — a real defect: it is marked `xfail`, and the defect
   is handed to `/eados debug`, which produces `BUG-0001` (the free-list corruption) with the
   `xfail` test as its reproduction. The drafted PR carries the green tests plus the
   defect-linked `xfail`; the human merges it.

## Boundary

Test authorship and a governed record — nothing else. The command **never advances state** (no
`delivery_state.phase` write, no proposed transition — it is not a phase); it **never fixes the
code under test** (a failing generated test that reveals a defect is handed to
[`/eados debug`](debug.md), never "fixed" here — the code change is a different PR with a different
owner); it **never restructures** (that is [`/eados refactor`](refactor.md)) or **optimizes**
(that is [`/eados optimize`](optimize.md)); and it **never records a bug as an expected pass** — a
genuine failure is `xfail` + a linked ledger entry, not a green test that enshrines wrong
behavior. It refuses untestable targets and manifest-less code, routing rather than guessing
(ADR-0019). The `qa-engineer` intakes, generates, verifies, and **drafts**; the human opens,
reviews, and merges the PR (`AGENTS.md` §6).
