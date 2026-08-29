# `/eados refactor` — behavior-preserving code-quality refactoring (pattern-guided)

Restructures application code for **readability, modularity, and idiom without changing
behavior**. **Cross-cutting** (ADR-0019 class 3 — run it in any phase, like `/eados status`):
advisory and **non-state-advancing** — it never writes `delivery_state.phase` and never proposes
a transition. Everything it *does* write is fully governed: the **tech-lead** authors the change
(owns `src/**`, drafts the patterns-catalogue row), the **reviewer** holds the **quality-bar
verdict** (`AGENTS.md` §10), and any *structural* pattern introduction earns its ADR exactly as
every generated repo requires (`AGENTS.md` §8). It follows the shape
[`debug.md`](debug.md) set for the Wave-2 cross-cutting code commands — the guarantee that
distinguishes `refactor` is **behavior preservation**, proven by a green test suite on both
sides of the change.

## Preconditions

- **A manifest is required (ADR-0019 boundary).** The command runs only against an initialized
  project — a repository whose manifest carries `delivery_state`. Pasted or standalone code is
  **refused and routed**: greenfield → [`/eados init`](init.md); an existing ungoverned repository
  → [`/eados adopt`](adopt.md) (#247 — the brownfield intake). A plain *question*
  about code stays the Step-0 triage question route (`0-question` in
  [`../triage.yaml`](../triage.yaml) — answered directly, no command run).
- **A named target.** One smell/target per run — a module, a pattern violation, a duplication
  cluster, a naming/idiom drift. Open-ended "clean everything" scope is **refused** the same way
  `/eados debug` refuses vague intake: name the one target and stop until it is stated.

## Procedure

1. **Scope** — state the single target and the intended end-shape (the pattern or idiom the code
   moves *toward*), plus the surface it touches. Confirm the acting role may write it before
   editing:
   ```bash
   python .eados-core/tools/authority_check.py tech-lead src/<path> docs/patterns/README.md
   ```
2. **Behavior-preservation gate** — the affected surface must be **test-covered before**
   restructuring. Run the suite green; where coverage is missing, add **characterization tests**
   that pin the *current* behavior first. No restructuring begins over untested code — this is the
   gate that makes "behavior-preserving" a checkable claim, not an assertion.
3. **Restructure** — **one logical change**, guided by the committed **architecture style** and
   the **patterns catalogue** (`docs/patterns/`, taxonomy in `design-patterns.md`). Names match
   the canonical taxonomy. A *structural* pattern introduction earns its **ADR** (problem,
   alternatives, why this pattern) — the same rule the generated repos live under (`AGENTS.md`
   §8); with `spec.pattern_discipline: enforced`, conformance to the committed style is a review
   expectation, not merely advice. No behavior change rides along — a defect found mid-refactor is
   handed to [`/eados debug`](debug.md), a hot path to [`/eados optimize`](../commands/README.md).
4. **Prove** — the suite is **green after** (same tests, same outcomes — the behavior-preservation
   proof); the profile's **formatter/linter** gates pass (warnings-as-errors on the diff); and
   **no public-API change** ships without the SemVer + ADR path (a signature change is a different
   kind of PR, not a cleanup).
5. **Record & close** — update the **patterns-catalogue row** when a planned pattern lands
   (`Planned → Implemented`, with the ADR link and the real `src/` code location; a rejection goes
   to *Rejected* with its reason, never silently dropped); run the pre-PR congruence gate
   (`python tools/consistency_lint.py` — the catalogue-vs-ADR check, in the generated repo); draft
   the gated PR with the standard cross-links. **The human opens and merges** (`AGENTS.md` §6) —
   one logical change, one PR.

## Worked example — a fixture module, end-to-end

The reference fixture (`pbr-cpp-memory-pool`) has a `Pool::acquire()` that branches inline over
three allocation strategies (fixed / growth / fallback) in one 40-line function — a readability
and modularity smell, and a textbook **Strategy** candidate from the catalogue's *Behavioral*
category. The run:

1. **Scope** — target: the inline strategy switch in `src/pool.cpp`; end-shape: extract a
   `AllocationStrategy` interface (Strategy pattern). Authority check passes for `tech-lead`.
2. **Behavior-preservation gate** — the existing `pool_acquire_test` covers fixed + growth but
   not the fallback path; add a characterization test pinning fallback's current behavior. Suite
   green.
3. **Restructure** — extract the three branches into strategy types behind the interface; one
   logical change, no behavior touched. Strategy is a *structural/behavioral* pattern
   introduction → `docs/adr/NNNN-strategy-for-allocation.md` (drafted here, approved by the
   `enterprise-architect` who owns `docs/adr/**`).
4. **Prove** — the same suite (now including the fallback characterization test) is green;
   `clang-format`/`clang-tidy` clean on the diff; `Pool`'s public signature is unchanged (no
   SemVer bump).
5. **Record** — the catalogue's *Strategy* row flips `Planned → Implemented` with the ADR link
   and `src/pool.cpp` as the code location; `tools/consistency_lint.py` green; the drafted PR
   carries the restructure, the characterization test, the ADR, and the catalogue row as **one**
   logical change; the human merges it.

## Boundary

Behavior-preserving restructuring of one target, and a governed record — nothing else. The
command **never advances state** (no `delivery_state.phase` write, no proposed transition — it is
not a phase); it **never changes behavior** (a green suite on both sides is the contract; a
defect belongs to [`/eados debug`](debug.md)), **never optimizes** (measure-first performance work
is [`/eados optimize`](../commands/README.md), #244), and **never brings an ungoverned repo to
standard** (that is the [`migrate`](migrate.md) phase). It refuses open-ended scope and
manifest-less code, routing rather than guessing (ADR-0019). The agent scopes, proves, restructures,
and **drafts**; the human opens, reviews, and merges the PR (`AGENTS.md` §6).
