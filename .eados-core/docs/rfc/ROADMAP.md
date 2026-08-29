# Roadmap — EADOS

The **single source of truth** for EADOS's own delivery plan, from start to finish.
[RFC-0001](0001-eados-delivery-os.md) ratifies the design and points here for the schedule.

- **Living & checkbox-driven.** When an item completes in a PR, flip its checkbox
  (`- [ ]` → `- [x]`) **in the same PR**. New work goes at the bottom of its milestone with a
  fresh `<milestone>.<task>` number; never renumber.
- **Versioning:** pre-1.0, milestone-driven (`AGENTS.md` §6).
- **Invariant:** the factory keeps working unchanged throughout; every phase is opt-in, so a
  user who only wants `scaffold` (today's generation) sees no behavior change.
- **Foundation:** [RFC-0001](0001-eados-delivery-os.md) + the machine-readable specs under
  [`orchestrator/os/`](../../orchestrator/os/README.md).

## Status

| Item | State |
|------|-------|
| Rename EAAO → EADOS | ✅ merged (#33) |
| Design package — RFC-0001 + OS specs + diagrams | ✅ merged (#35) |
| **M1 — Foundation** | ✅ **done** — M1-A..E merged (#37–#41) |
| **M2 — design phase + roles** | ✅ **done** — M2-A..E merged (#42–#46) |
| **M3 — plan phase + traceability** | ✅ **done** — M3-A..C merged (#47–#49) |
| **M4 — audit phase + risk** | ✅ **done** — M4-A..C merged (#50–#52) |
| **M5 — refactor (brownfield)** | ✅ **done** — M5-A..D merged (#53–#56) |
| **v2.0.0 release** | ✅ published 2026-06-23 |
| **M6 — hardening & UX** | ✅ **done** — items 6.1–6.9 (#63–#69, #72, #76) |
| **v2.1.0 release** | ✅ published 2026-06-27 — M6 hardening & UX (bundles attached; Latest) |
| **M7 — onboarding & docs** | ✅ **done** — items 7.1–7.5 (#97–#101) |
| **M8 — inbound contribution review** | ✅ **done** — items 8.1–8.6 (#105–#110) |
| **v2.2.0 release** | ✅ published 2026-06-28 — M7 onboarding + contributor-safety hardening + M8 inbound review (bundles attached; Latest) |
| **M9 — guided installer** | ✅ **done** — items 9.1–9.7 (`setup/` guided installer: download + SHA256-verify + additive extract; release integrity; static gate; docs) |
| **v2.3.0 release** | ✅ published 2026-06-28 — M9 guided cross-platform installer (co-authored @AlexMnrs; bundles + `SHA256SUMS` attached) |
| **M10 — post-audit hardening** | ✅ **done** — items 10.1–10.5 (#128–#132) |
| **v2.4.0 release** | ✅ published 2026-06-28 — M10 post-v2.3.0 audit remediation |
| **M11 — delivery-workflow automation** | ✅ **done** — items 11.1–11.4 (#141–#144) |
| **M12 — interview completeness** | ✅ **done** — items 12.1–12.6 (#149–#154) |
| **v2.5.0 release** | ✅ published 2026-07-01 — M11 delivery-workflow automation + M12 interview completeness |
| **M13 — audit remediation & learning loop** | ✅ **done** — items 13.1–13.14 (#163–#176) |
| **v2.6.0 release** | ✅ published 2026-07-05 — M13 audit remediation & learning loop |
| **v2.7.0 release** | ✅ published 2026-07-07 — post-v2.6.0 hardening: the #203 audit-trail epic (#213–#215) + the #194–#202 defect-backlog fixes (no GitHub milestone; see the un-numbered write-up below) |
| **M14 — agent-contract hardening & runtime re-grounding** | ✅ **done** — items 14.1–14.5 (#221–#225) |
| **v2.8.0 release** | ✅ published 2026-07-08 — M14 agent-contract hardening & runtime re-grounding |
| **M15 — command surface & governed assistants** | ✅ **done** — items 15.0–15.x (#233 plan; Waves 0–3, milestone #15 closed) |
| **M16 — model & effort routing** | ✅ **done** — items 16.1–16.x (#256 plan; advisory routing-as-data, ADR-0017, milestone #16 closed) |
| **M17 — interaction contract & confidence calibration** | ✅ **done** — items 17.1–17.5 (#277–#281; ADR-0022, `os/interaction/`, milestone #17 closed) |
| **v2.9.0 release** | ✅ published 2026-07-11 — M15 command surface + M16 model/effort routing + M17 interaction contract |
| **M18 — consumer-side routing & model checkpoint** | ✅ **done** — items 18.1–18.3 (#296–#298; roadmap routes + advisory `--check` checkpoint, milestone #18 closed) |
| **v2.10.0 release** | ✅ published 2026-07-12 — M18 consumer-side routing & model checkpoint |
| **v2.11.0 release** | ✅ published 2026-07-26 — scaffold routing parity (#306/#307, ADR-0023): the generated ROADMAP carries the routing legend + per-item advisory routes |

Legend: ⏳ not started · 🚧 in progress · ✅ done.

---

## Milestone 1 — Foundation: domain axis, persistent manifest, role authority, `/eados init`

**Goal.** Lay the data foundation the whole pipeline reads from, and the entry command — without
changing how generation behaves today.

- [x] 1.1 Add the **domain/target axis** as data: `orchestrator/domains/_schema.md` +
      `_template.yaml`, and seeds `software.yaml`, `game.yaml`, `mobile.yaml` (each declaring its
      roles, artifacts — GDD vs PRD, NFR axes — RAM/GPU/framerate for `game`, and milestone
      vocabulary — Alpha/Beta/RC vs SemVer).
- [x] 1.2 `eados_lint`: a **`domain-completeness`** gate (every `domains/<d>.yaml` defines every
      schema key), mirroring `profile-completeness`.
- [x] 1.3 Interview: new **`Q0.4 — development target`** loads the domain profile; the manifest
      gains a `domain` field.
- [x] 1.4 Promote the manifest to a **persistent, reference-based `delivery_state`** block
      (current phase, checkpoints, cross-link ids) with a `schema_version` (**resolves OQ1**).
- [x] 1.5 Wire the **authority block** to the existing roles (persona in `agent/*.md` ↔ authority
      in `authority.yaml`), making the persona≠authority separation real.
- [x] 1.6 Ship the **`/eados init`** command surface (entry skill) + a thin state-driven
      phase-runner skeleton that reads `workflow.yaml` and reports the legal next transitions.

**Acceptance gate.** All lints green (incl. `domain-completeness`); render-smoke unchanged; a
chosen domain selects roles/artifacts/NFRs/milestone-vocabulary purely as data.
**Depends on:** RFC-0001, `orchestrator/os/` specs.

---

## Milestone 2 — `design` phase (RFC) + Product/Delivery roles + workflow checker + authority gate

**Goal.** Make the first governance phase real: author/import RFCs under a review protocol, with
the new org-chart roles and the deterministic engine that gates phase transitions.

- [x] 2.1 Add personas `agent/{product-manager,tech-lead,producer}.md` + the **domain-overlay**
      pattern (`agent/domains/<domain>/<role>.md`, e.g. the `game` `product-manager` = Game
      Designer); recursive `agent-registry` + `authority-personas` lints. **OQ4 resolved:** one
      authority role + a domain-specialized persona overlay (not two role IDs).
- [x] 2.2 RFC template + the **RFC-review protocol** under `orchestrator/os/rfc/` (schema +
      config + template + protocol), and `tools/rfc_check.py` enforcing the **`rfc-approved`** gate
      (required sections + a `tech-lead` approval record).
- [x] 2.3 The **deterministic workflow checker**: `phase_runner.py` returns the legal transitions
      and (new `--propose <to>`) validates a proposed transition and **emits the checkpoint** to
      write — read-only; the agent writes it, the human confirms H-gates.
- [x] 2.4 The **authority gate** — `tools/authority_check.py <role> <paths>` enforces the
      `authority.yaml` ownership map: a path the acting role may not write (outside its
      `owns`/`may_draft`) is rejected. Agent-invoked (CI can't know the actor's role), tested.
- [x] 2.5 Ship the **`/eados design`** command surface (`commands/design.md` — authority-check →
      author the RFC from the template → review → `rfc_check` → `phase_runner --propose plan`).

**Acceptance gate.** A sample RFC passes the review gate; an out-of-authority edit is rejected by
the authority gate; the checker computes the correct legal transitions for a given state.
**Depends on:** M1.

---

## Milestone 3 — `plan` phase: roadmap from RFCs + the traceability graph

**Goal.** Co-create the roadmap from RFCs through a real negotiation, and build the lineage graph
that makes delivery auditable.

- [x] 3.1 The **roadmap-negotiation protocol** under `orchestrator/os/plan/` (schema + `plan.yaml`
      config + `negotiation-protocol.md`): PM proposes → `tech-lead` sizes (T-shirt) → `producer`
      reconciles capacity, anchored to artifacts (no "multi-agent theatre").
- [x] 3.2 Ship the **`/eados plan`** command surface (`commands/plan.md` — negotiate via `plan.yaml`
      → write `ROADMAP.md` → `traceability.py` (`roadmap-covers-rfcs`) → `--propose scaffold`).
- [x] 3.3 The **traceability-graph builder** — `tools/traceability.py` builds the design-time
      `RFC → milestone` edges from the roadmap (the Git-side `PR → commit → release` edges land in
      M4, derived from the `git`-spec cross-links).
- [x] 3.4 The **`roadmap-covers-rfcs`** gate — `traceability.py` fails when an RFC is addressed by
      no milestone (every RFC maps to ≥1 milestone; generalizes the spec-coverage-map). Wired into
      `workflow.yaml`.

**Acceptance gate.** Every RFC maps to ≥1 milestone; the graph builds from a sample project's
cross-links.
**Depends on:** M2.

---

## Milestone 4 — `audit` phase: risk scoring + enforced `traceability-lint`

**Goal.** Stand up continuous audit with a real risk model, and turn the traceability graph into
a blocking gate.

- [x] 4.1 A **risk model** — `tools/risk_score.py` + the `risk` OS spec: score = f(security surface
      × change size × blast radius), generalizing the `reviewer` + `security-auditor` roles.
- [x] 4.2 Ship the **`/eados audit`** command surface (`commands/audit.md` — `traceability-lint` +
      `risk_score` → the `security-auditor` gate above threshold → a risk register).
- [x] 4.3 The **`traceability-lint`** gate — `traceability.py --links` extends the graph to the
      Git-side edges (`milestone → PR → commit → release`) and fails on a dangling edge (an RFC with
      no PR, a PR missing its RFC/milestone, a release not tracing to a PR + commit).
- [x] 4.4 Risk-threshold → **mandatory `security-auditor` gate** at/above the level; the threshold
      is **per-domain configurable** in `risk.yaml` (**OQ2 resolved**: a global default + domain override).

**Acceptance gate.** A seeded dangling edge fails `traceability-lint`; a change above the risk
threshold forces the security gate.
**Depends on:** M3.

---

## Milestone 5 — `refactor` (brownfield) — last, sandboxed

**Goal.** Bring an existing repository up to the standard via incremental, gated migrations —
the highest-risk phase (it edits real user code), so it is sequenced last and write-contained.

- [x] 5.1 **Brownfield reader** — `tools/brownfield.py` (READ-ONLY) maps an existing repo against
      the EADOS standard (agent contract, docs system, CI, source tree) and reports the gaps to migrate.
- [x] 5.2 **Migration planner** — `tools/migration_planner.py` (READ-ONLY) orders the brownfield
      gaps into incremental steps (one logical change each), lowest-risk / most-foundational first.
- [x] 5.3 A **write-contained sandbox** — `tools/sandbox.py` (defense-in-depth, on the renderer
      write-guard principle of [ADR-0007](../adr/0007-renderer-write-guards-and-validation-independence.md)):
      a write may only land inside the target repo (traversal/absolute/symlink/`.git`/clobber refused).
- [x] 5.4 Ship the **`/eados refactor`** command surface (`commands/refactor.md` — brownfield read
      → plan → sandboxed, gated, **additive** migration PRs, one logical change each).

**Acceptance gate.** A fixture repo is migrated via gated PRs; no write escapes the sandbox; each
PR passes the standard's gates.
**Depends on:** M4.

---

## Milestone 6 — hardening & UX (post-v2.0.0)

**Goal.** Close the automation/completeness gaps (G2–G4) and feature suggestions (F1–F4) surfaced
by the v2.0.0 enterprise review, plus the one cross-spec scope deferred from #62 — **without
changing the shipped pipeline's behavior**. Each item is one logical change (one PR), tracked as a
GitHub issue under the `M6 — hardening & UX` milestone (#6).

- [x] 6.1 (G4, #65) **End-to-end phase smoke test** — a fixture that runs a complete *phase flow*
      (`design → plan → audit`) over the real tool CLIs to catch tool-integration bugs the per-tool
      unit tests miss: each gate passes on a coherent fixture and fails on a broken one, and
      `phase_runner --propose` matches every transition declared in `workflow.yaml`
      (`tools/tests/test_phase_smoke.py`).
- [x] 6.2 (F3, #68) **Risk-model weights as data** — the factor weights, blast-radius threshold, and
      points→level cutoffs move from `risk_score.py` into `risk.yaml`, each **per-domain overridable**
      like `mandatory_gate_level`; the scorer reads them via `resolve(cfg, domain)` with built-in
      fallbacks (back-compat, default scores unchanged). Full "knowledge as data"; `risk/_schema.md` updated.
- [x] 6.3 (G2, #63) **Single-artifact render for `refactor`** — `tools/render_artifact.py` renders
      one template with the manifest context (the same gates as a full render) and places it via
      `sandbox.safe_write`; the "render the missing artifact → sandbox" step in `refactor.md` now
      invokes it (no longer manual).
- [x] 6.4 (F1, #66) **`/eados status` (doctor)** — a read-only `tools/doctor.py` (+ the
      `commands/status.md` surface) reports current phase, legal transitions (+ gates/human-gating),
      refs, and traceability coverage at a glance — composing `phase_runner` + `traceability`; exits
      non-zero on an actionable problem (undeclared phase, uncovered RFC, dangling edge).
- [x] 6.5 (G3, #64) **Thin CLI phase orchestrator** — `tools/eados.py <phase> <manifest>` runs a
      phase's deterministic outgoing gates (data-driven from `workflow.yaml`), marking render-time /
      human gates `[manual]`, then reports the legal next moves; `eados.py status` is the doctor. The
      executable spine beneath the markdown `/eados <phase>` procedures.
- [x] 6.6 (F2, #67) **Auto-derive traceability links from PR bodies** (via `gh`) —
      `tools/derive_links.py` builds the `{pr, rfc, milestone, commit, release}` edges from merged
      PRs (pure parser + a thin `gh` shell that degrades cleanly offline), emitting a `links.yaml`
      `traceability-lint` consumes — no more hand-writing it.
- [x] 6.7 (F4, #69) **Version-lockstep dogfooding** — a new `version-lockstep` gate in `eados_lint`
      asserts every EADOS README release badge (EN + i18n) and the CHANGELOG's "latest is" prose
      match the CHANGELOG's latest released `## [X.Y.Z]` — the factory held to the bar it imposes
      downstream.
- [x] 6.8 (#72) **Cross-spec gate → cross-cutting gates** — `traceability-lint` is now registered in
      `workflow.yaml`'s gate list (cross-cutting, `required_for: []`) and `cross-spec-consistency`
      validates `git.yaml`'s `traceability.gate` against it, so a typo'd cross-cutting gate id is
      caught too (the scope deferred from #62). **Closes M6.**
- [x] 6.9 (#76) **Auto-sync shared action pins into templates** — `tools/sync_action_pins.py`
      (`--check` / `--fix`) rewrites the rendered workflow templates' action pins to the factory CI's,
      so a Dependabot `github-actions` bump needs no manual companion edit to pass the `action-pins`
      lockstep gate (ADR-0009) — and the `dependabot-pin-sync` workflow (`workflow_run`, not
      `pull_request_target`; ADR-0013) applies it automatically on a Dependabot PR (true zero-touch).

**Acceptance gate.** Each item lands as a gated PR with tests; no regression to the v2.0.0 pipeline;
any new data/spec is `_schema`-validated and lint-gated (no special-casing in code — the
anti-fragmentation invariant below).
**Depends on:** v2.0.0 (post-release); incremental — items are independent.

---

## Milestone 7 — onboarding & UX docs (post-v2.1.0)

**Goal.** Close the first-time-user friction a fresh install/usage evaluation surfaced (2026-06-27):
make the phase pipeline followable, the install OS-agnostic, the manifest self-documenting, and a
correct-but-confusing tool output self-explanatory — **without changing any tool behavior** (docs,
inline comments, and at most an optional tool hint). Each item is one PR, tracked under the
`M7 — onboarding & docs` milestone (#7).

- [x] 7.1 (#89) **Prerequisites — getting an AI coding agent** — a short pointer (not a tutorial):
      install links for Claude Code / Gemini Antigravity / ChatGPT Codex, one line on what "open the
      folder" does (auto-loads `AGENTS.md`), and the explicit no-agent fallback to the deterministic
      path — so nobody stalls before starting.
- [x] 7.2 (#88) **Windows/PowerShell install & render variants** — a PowerShell equivalent beside
      every Unix snippet in README/USAGE (download, extract, render), using `$env:TEMP` not `/tmp`,
      so a Windows user reaches `<repo>/.eados-core/` without translation.
- [x] 7.3 (#90) **`project.yaml` documented field-by-field** — inline comments in the template and/or
      a required-fields table (field → meaning → required? → source → placeholder), so a manifest can
      be hand-filled without reverse-engineering `reference.yaml`; `render.py` succeeds on it.
- [x] 7.4 (#87) **End-to-end phase walkthrough** — a narrated `init → design → plan → scaffold →
      audit` run (the headline v2.0.0 feature) with the exact commands, expected output, the human
      gates, and how `delivery_state` evolves; reproducible from the doc alone.
- [x] 7.5 (#91) **Clarify `rfc_check` scope** — a doc note (+ optionally a clearer tool hint) that the
      gate targets generated-project RFCs following `os/rfc/template.md`; EADOS's own RFC-0001 is
      intentionally out of scope, so its FAIL isn't mistaken for a defect (no headings retrofitted).

**Acceptance gate.** A first-time user can, from the docs alone, install on any OS, understand the
agent prerequisite (or take the no-agent path), hand-fill a valid manifest, and follow a full phase
run. **No tool behavior change**; self-lint + render-smoke stay green.
**Depends on:** v2.1.0 (post-release); incremental — items are independent.

---

## Milestone 8 — inbound contribution review: `/eados review` + the `contribution-reviewer` role

**Goal.** Give EADOS (and every generated repo) a governed way to **triage and review pull requests
opened by non-owners** — the inbound-contribution funnel the existing *internal* `reviewer` /
`security-auditor` roles do not cover (those are author-agnostic peer review of a diff). A new
`contribution-reviewer` role **composes** those two and adds the dimensions specific to an untrusted,
non-owner contribution: **provenance / trust tier** (owner · collaborator · external-fork),
**contribution-policy compliance** (sign-off, Conventional Commits, the `git.yaml` PR↔RFC↔milestone
cross-links, one-logical-change), **untrusted-code security posture** (a fork can't reach CI secrets;
a workflow-file change is a poisoned-pipeline surface; new deps are supply-chain), **authority /
scope** (a non-owner holds no authority role, so a touch on an owned path escalates to the
maintainer), and **triage / disposition** (label, route to the owning internal role, recommend one of
three outcomes — `re-implement-in-house` (adopt the idea our way), `close-with-thanks` (decline), or
`needs-maintainer` (escalate); a non-owner's commits are never merged).
It **recommends and drafts; it never merges** — the `pr.merged_by: human` boundary is untouched.
`/eados review` is **cross-cutting** (usable in any phase, like `/eados status`), not a new state in
the workflow machine. Each item is one PR, tracked under the `M8 — inbound contribution review`
milestone.

This milestone **automates the policy the owner already applies by hand** to external PRs: verify the
change, not the person; **never auto-accept** and **never merge a non-owner's commits** — a good idea
is **adopted via an in-house re-implementation** (we author it ourselves, co-author the contributor, a
rationale comment on their PR, and the owner posts the close — the #94 episode); and **always thank**
the contributor. Provenance stays 100% in-house. It is encoded as data the gates validate.

- [x] 8.1 **Contribution policy as data** — `orchestrator/os/contribution/{_schema.md,
      contribution.yaml}`: the owner-identity source (CODEOWNERS / manifest), the trust tiers
      (owner · collaborator · external-fork), the required inbound checks, the disposition + label
      vocabulary, and the "external touches an owned path → escalate" rule. Auto-validated by
      `os-spec-completeness` and the `data-file-validity` / `gate-coverage` gates; its role/gate
      cross-refs validated by `cross-spec-consistency` (anti-fragmentation — no special case in code).
- [x] 8.2 **The `contribution-reviewer` role** — persona `agent/contribution-reviewer.md` (the
      enterprise contribution steward: composes `reviewer` + `security-auditor`, adds
      provenance / policy / triage, never merges) + an `authority.yaml` record (engineering pillar,
      `phases: []`, empty `owns` / `may_approve` like `reviewer`) + a registry row. Enforced by
      `agent-registry` + `authority-personas`.
- [x] 8.3 **`tools/pr_review.py` — the inbound-PR evaluator** — given a PR number, via `gh` and
      degrading cleanly offline (the `derive_links.py` pattern): fetch author + fork status + files +
      commits + check status → **classify non-owner authorship** → run the 8.1 policy checks →
      compose `authority_check.py` (owned-path escalation) + `risk_score.py` (security / size /
      blast) → emit a structured **review report + recommended disposition**. Pure parser + a thin
      `gh` shell, fixture-tested.
- [x] 8.4 **`/eados review <PR#>` command surface** — `commands/review.md` + a `commands/README.md`
      row: run `pr_review.py` → on an owned-path touch or a REQUIRED risk score, invoke the
      `security-auditor` + `reviewer` → **draft** the review comment + labels via `gh` → recommend a
      disposition. Cross-cutting like `/eados status` (not a phase transition). Boundary: drafts only;
      the human requests-changes / approves / merges.
- [x] 8.5 **Wire the inbound checks as a cross-cutting gate** — a `contribution-review` gate in
      `workflow.yaml` (`required_for: []`, like `traceability-lint`), referenced from a new `git.yaml`
      `pr` field + its `_schema.md`, validated by `cross-spec-consistency`. **No change to the shipped
      phase pipeline.** Optional: a rendered CI template `pr-contribution-review.yml` (comment-only —
      never approve / merge) for generated repos.
- [x] 8.6 **Dogfood + docs** — an ADR for the inbound-contribution-trust model, a `/eados review`
      walkthrough in USAGE/README, and the evaluator run against the **#94** external-contribution
      episode (the canonical case) as the worked example — plus the currently-open non-owner PR #96
      as a live secondary case; RFC-0001, this roadmap, the affected specs, and the CHANGELOG kept in
      lockstep (the cross-cutting invariant).

**Acceptance gate.** A PR from a non-owner produces a structured report + a recommended disposition;
an external PR touching an owned path is flagged for maintainer escalation; the human boundary (no
agent merge) is preserved; self-lint (incl. the gate-coverage trilogy) + render-smoke stay green.
**Depends on:** M7 (post-merge); ships to consumers in the bundle → a likely **v2.2.0** release.

---

## Milestone 9 — guided cross-platform installer (onboarding)

**Goal.** Let a newcomer **install EADOS into a repo by running a script and answering a few prompts**
— no copy-pasting the USAGE §6 `curl`/`tar` snippets. A guided, cross-platform installer under
**`setup/`** (Linux/macOS `setup.sh` + a double-clickable macOS `setup.command`, and a Windows
`setup.ps1` with a `setup.bat` shim) downloads the latest release bundle and places it at a target
repo root. **Scope:** "install" = the
**bundle download + placement only** (the consumer step of USAGE §6) — *not* the agentic-OS init
(interview/generate). The interactivity is about *where* to install: **new repo vs existing repo**, and
always the **path + repo name**. Each item is one PR, tracked under the `M9 — guided installer`
milestone.

This milestone **re-implements and elevates @AlexMnrs's PR #96** ("Add Windows PowerShell setup
examples", opened then closed by the author) — the `contribution-reviewer`'s `re-implement-in-house`
path made real: we build it our way and **co-author @AlexMnrs** (credited in the CHANGELOG).

  > **Layout note (9.7).** Items 9.1–9.4 were first built under `install/` with an `install.sh`
  > engine + `setup.sh` wrapper; **9.7 relocated + unified them** to `setup/setup.{sh,command,ps1,bat}`
  > (the POSIX engine + wrapper merged into the single combined `setup/setup.sh`, mirroring
  > `setup.ps1`). The descriptions below name the final files.

- [x] 9.1 **Installer core (POSIX)** — the download → **verify SHA256** (fail-closed — refuses to
      extract an unverified bundle unless `--no-verify`) → **additive** extract (refuse to clobber an
      existing file) engine, with scripting flags (`--path`, `--repo-name`, `--mode new|existing`,
      `--ref`), a pure `--print-plan` (resolve without touching the network or disk), and a
      `--from <file>` local-bundle seam — testable, degrades cleanly offline (the `derive_links.py`
      pattern). Now part of the combined [`setup/setup.sh`](../../../setup/setup.sh); gated by the
      `setup/*.sh` `gate-coverage` class + the `test_setup_sh.py` smoke (CI).
- [x] 9.2 **Interactive layer (POSIX)** — when run bare (or `--interactive`): prompt for
      new-vs-existing repo, path, and repo name; on **new** run `git init` at `<path>/<name>` (offer
      `gh repo create` when `gh` is present); confirm before writing; clear success / next-steps output
      (point at `AGENTS.md` / the deterministic path). In the combined
      [`setup/setup.sh`](../../../setup/setup.sh) + the double-clickable macOS
      [`setup/setup.command`](../../../setup/setup.command) shim; `--dry-run` keeps it testable, gated by
      `test_setup_sh.py`.
- [x] 9.3 **PowerShell installer — `setup.ps1`** (+ a `setup.bat` shim for true double-click) — the
      Windows-native equivalent: same prompts + checksum verify + additive extract (the 7.2
      PowerShell-parity principle). [`setup/setup.ps1`](../../../setup/setup.ps1) is one script
      (scriptable via params, interactive when bare; PS 5.1/7-compatible, ASCII-only, uses `tar.exe`) +
      the [`setup/setup.bat`](../../../setup/setup.bat) double-click shim
      (`powershell -ExecutionPolicy Bypass -File`). Same fail-closed SHA256 + additive no-clobber as the
      POSIX script; gated by `test_setup_ps1.py` (driven via `pwsh`).
- [x] 9.4 **Release publishes integrity + the installers** — `release.yml` attaches `SHA256SUMS` and
      the install scripts as assets, so the installer can verify the bundle and
      `releases/latest/download/setup.{sh,ps1}` are stable links. The `release-bundle` workflow now
      stages the `setup.*` scripts + writes a `sha256sum` `SHA256SUMS` over every asset and uploads them
      all; the installers gained a `--sums-file` / `-SumsFile` seam to verify against a local
      `SHA256SUMS` (offline / air-gapped), which lets `test_setup_{sh,ps1}.py` prove the published
      format is consumed (the producer↔consumer contract).
- [x] 9.5 **Gate the new script file-class** — a CI **static-analysis** step for the installers:
      **shellcheck** for `setup/*.sh` + `setup/*.command` (pre-installed on the runner) and a
      dependency-free **PowerShell parse-check** for `setup/*.ps1` (`Parser::ParseFile`, which avoids a
      network `Install-Module PSScriptAnalyzer` — the roadmap's "or a parse check" branch). The core
      download / verify / extract **smoke** is the existing `test_setup_{sh,ps1}.py` (offline via
      `--from`). The `eados_lint` `gate-coverage` reasons move from "shellcheck in M9.5" to the real
      gate — honoring the gate-EVERY-file-class mandate.
- [x] 9.6 **Docs + dogfood + credit** — README + [`USAGE.md`](../USAGE.md) §6 "Get it" gain the
      one-step installer path beside the manual snippets (README i18n — zh-Hans + ja — refreshed in
      lockstep, source-hash bumped); **@AlexMnrs credited** (co-author + CHANGELOG; their closed PR #96
      re-implemented in-house, owner posts the thank-you/close). RFC-0001 needs no change (no installer
      surface; its §12 defers to this roadmap, which tracks M9). **Closes M9.**
- [x] 9.7 **Relocate + unify the installers under `setup/`** (owner-requested consistency pass) — move
      the guided installer out of `install/` to a top-level **`setup/`** with consistent
      **`setup.{sh,command,ps1,bat}`** naming, and **merge the POSIX engine + interactive wrapper into
      one combined `setup/setup.sh`** (mirroring the already-combined `setup.ps1`). The installer stays
      outside `.eados-core/` (it *delivers* it) and `export-ignore`d from the bundle. Updates
      `release.yml`, `eados_lint` `gate-coverage`, `.gitattributes`, and the tests
      (`test_setup_sh.py` / `test_setup_ps1.py`); no behavior change. Done **before 9.5/9.6** so they —
      and the public `releases/latest/download/setup.{sh,ps1}` links — bake in the final names.

**Acceptance gate.** A newcomer installs the bundle into a new or existing repo from prompts on Linux,
macOS, and Windows; the SHA256 is verified and no existing file is clobbered; self-lint (incl. the new
script-file gate) + render-smoke stay green. **No agentic-OS init in scope.**
**Depends on:** M8 / v2.2.0 (post-release); ships to consumers in the bundle → a later release.

---

## Milestone 10 — post-audit hardening (post-v2.3.0)

**Goal.** Close the gaps a post-v2.3.0 repository audit surfaced — a mojibake/crash risk on
non-UTF-8 consoles, a tar-slip vector in the new installers, stale docs, latent tooling edge
cases, and a re-confirmed action-pinning policy — **without changing the shipped pipeline's
behavior**. Each item is one PR, tracked under the `M10 — post-audit hardening` milestone.

- [x] 10.1 (#128) **UTF-8 stdio guard** — every CLI tool forces UTF-8 on `stdout`/`stderr` at
      `main()` entry, so non-ASCII output (the em-dash, `→`, `✓`) renders correctly instead of
      garbling or raising `UnicodeEncodeError` on a non-UTF-8 console (Windows `cp1252`);
      `test_utf8_stdio.py` proves it end-to-end and statically asserts every CLI tool carries it.
- [x] 10.2 (#129) **Installer tar-slip hardening** — `setup.sh` / `setup.ps1` refuse any
      symlink/hardlink entry in the release bundle *before* extracting (closes a path-escape
      vector), even under `--no-verify`; regression tests in `test_setup_sh.py` / `test_setup_ps1.py`.
- [x] 10.3 (#130) **Documentation accuracy sweep** — SECURITY.md's stale pre-v1.0.0 note, a 404
      USAGE.md link in the zh-Hans/ja READMEs, the missing `contribution` OS-spec index row, and
      RFC-0001's stale "M1 → M5" pipeline description (now M1 → M9) are all corrected.
- [x] 10.4 (#131) **Defensive hardening of latent tooling edge cases** — `risk_score` *requires*
      (never raises on) an out-of-range `mandatory_gate_level`; `cleanup_installer` matches a
      setup-leftover by filesystem entry *type*, not name; `gate-coverage`'s `git ls-files` handles
      a non-ASCII filename; the CLI tools (`doctor`/`eados`/`phase_runner`/`traceability`/
      `rfc_check`) report a missing/invalid path as a clean non-zero exit, not a raw traceback
      (`test_cli_guards.py`); `git.yaml`'s commit `scopes` vocabulary catches up to actual use.
- [x] 10.5 (#132) **ADR-0009 addendum — profile action-pinning reaffirmed** — a dated addendum
      records that `profiles/*.yaml` referencing Actions by floating tag, while the factory
      SHA-pins its own workflows, is the deliberate tiered policy of ADR-0009 §3 — an apparent
      inconsistency re-surfaced by audit, not a design gap.

**Acceptance gate.** Every item lands as a gated PR with a regression test; no change to the
shipped pipeline's behavior; self-lint + render-smoke stay green.
**Depends on:** v2.3.0 (post-release); incremental — items are independent.

---

## Milestone 11 — delivery-workflow automation (post-v2.3.0)

**Goal.** Automate the delivery-workflow hygiene the owner was enforcing by hand on every PR —
complete PR metadata, a green-CI bootstrap gate before milestone delivery starts, every roadmap
milestone seeded on GitHub, and a verbose squash-merge body — closing the last manual steps in
the PR lifecycle. Each item is one PR, tracked under the `M11 — delivery-workflow automation`
milestone.

- [x] 11.1 (#141) **PR-metadata contract as data** — `os/git/git.yaml` gains a `pr.metadata` block
      (`assignee`, one type `label`, `milestone`, `project`-if-present) distinct from
      `required_crosslinks`; new `tools/pr_metadata_check.py --pr N` verifies an open PR carries
      them; the assignee resolves to the **owner**, never `@me`.
- [x] 11.2 (#142) **"CI live & green" bootstrap gate** — `generate.md` Step 8 makes a green,
      configured CI on the bootstrap PR an explicit, hard-stop precondition before per-milestone
      PR delivery opens.
- [x] 11.3 (#143) **`seed_milestones.py`** — reads `ROADMAP.md` and prints (or `--run` executes)
      the exact `gh api …/milestones` calls to create **every** milestone as `MN — <name>` with a
      goal-derived description, so milestone-scoped delivery starts against a complete board.
- [x] 11.4 (#144) **Verbose squash-body policy as data** — `git.yaml`'s `commit.squash_body`
      requires the squash-merge commit to carry the PR's context/change/verification body, never a
      one-line collapse of the title.

**Acceptance gate.** A fresh repo's bootstrap PR cannot proceed to milestone delivery on red or
absent CI; every PR the tooling checks carries complete metadata; the full milestone board seeds
from one command.
**Depends on:** v2.3.0 (post-release); incremental — items are independent.

---

## Milestone 12 — interview completeness (post-v2.3.0)

**Goal.** Close six interview gaps a completeness review surfaced — a first-class web/enterprise
target, an asked (not hidden-behind-a-toggle) authoring language, real architecture-style/pattern
elicitation, an optional layered scaffold, a spec-import path, and an environment preflight —
**without changing the render output for existing defaults**. Each item is one PR, tracked under
the `M12 — interview completeness` milestone.

- [x] 12.1 (#149) **First-class `web` domain + enterprise posture (ADR-0015)** — new
      `orchestrator/domains/web.yaml` (web-vocabulary roles, hard accessibility + Core Web Vitals
      NFR budgets, a `[design, content]` cross-discipline pipeline, an `accessibility-review` +
      `web-vitals-budget` overlay) and a new orthogonal **`Q0.5 — enterprise posture`**
      (`governance.posture: standard | enterprise`) — deliberately not a fourth domain.
- [x] 12.2 (#150) **Unconditional authoring-language question (ADR-0016)** — `Q4.7` states and
      confirms the documentation language, a new code-comment language, and any extra doc
      languages; identifiers/public API/commits/branches/PR text stay **English regardless**, a
      non-English choice becomes a recorded exception rendered into the generated `AGENTS.md` §2.
- [x] 12.3 (#151) **Architecture-style & design-pattern elicitation** — `Q5.4` captures
      `spec.architecture_style`, the expected first-class patterns, and a
      `pattern_discipline: advisory | enforced` posture, seeding the generated
      `docs/patterns/README.md` catalogue instead of shipping an empty one.
- [x] 12.4 (#152) **Optional layered package scaffold** — a `service`/`app`/`web` project can opt
      into a layered internal layout (`controller/service/repository/dto/mapper`); the generator
      seeds each layer under both `src/main/…` and `src/test/…`; a library keeps the flat shape.
- [x] 12.5 (#153) **Phase-5 spec-import branch** — a new `Q5.0 — provenance` (`import` |
      `coauthor`) lets a maintainer with an existing spec import-and-validate it through a gap
      audit instead of always co-authoring from scratch; this work also fixed the loader silently
      truncating `questionnaire.yaml` on the wrapped `Q4.7` prompt — the discovery that motivated
      M13's #166.
- [x] 12.6 (#154) **Environment preflight** — new `tools/preflight.py` detects the Python/git/`gh`
      toolchain (+ `gh auth status`) and prints an OS-specific install/auth hint; `/eados init` and
      `generate.md` Step 0 run it first.

**Acceptance gate.** Each new interview branch is fixture-tested end-to-end; the
`en`/`en`/`standard`/flat-shape defaults render byte-identical to before; self-lint +
render-smoke stay green.
**Depends on:** v2.3.0 (post-release); incremental — items are independent.

---

## Milestone 13 — audit remediation & learning loop (post-v2.4.0/v2.5.0)

**Goal.** Close every gap a self-audit of the deterministic path and the (still-empty) learning
loop surfaced — a namespace-leak fallback, dead gate wiring, unapplied domain overlays, a fragile
loader, module-global lint state, an ungated test suite, unenforced interview provenance, a
hollow-spec floor, a playbook that never touched memory, and the run-recorder + auto-tuner
watchdogs the learning loop needed to have any input at all. Each item is one PR, tracked under
the `M13 — audit remediation & learning loop` milestone.

- [x] 13.1 (#163) **No silent `it/d4np` namespace fallback** — a missing `language.group_path` now
      fails the `{{GROUP_PATH}}` required-field guard instead of stamping the factory owner's
      namespace into a stranger's repo; `it/d4np` survives only as `examples/reference.yaml`'s
      truthful value.
- [x] 13.2 (#164) **`render.py --check` + the `gate-executability` lint** — the `manifest-valid`
      gate command documented in `workflow.yaml` is now real; a new `eados_lint` check guards the
      whole data→code seam (every `python <script>` gate names a real script that knows its
      flags; `wired: in-process` matches `eados.py`'s `GATE_EVALUATORS` exactly).
- [x] 13.3 (#165) **`domain_overlays` actually applied** — `phase_runner.apply_overlay(workflow,
      domain)` wires the web/game/mobile overlay gates + inserted states into the live machine
      (previously read by no engine); `/eados status` surfaces the applied overlay; a bare
      overlay id with no gate-registry entry is now rejected.
- [x] 13.4 (#166) **`yamlmini.py` — the loader is its own module, and the #153 truncation class is
      rejected loudly** — moved out of `render.py`; an unclosed quoted scalar or an open flow
      collection now raises a loud `ValueError` naming the line instead of silently dropping the
      rest of the file; a `SUBSET_REJECTIONS` PyYAML-differential corpus proves each rejection is
      a deliberate subset boundary, never a misparse.
- [x] 13.5 (#167) **`eados_lint` checks are reentrant** — every `check_*(fail)` receives the
      reporting callable; a new `run_checks()` owns the per-run accumulator, removing the
      linter's last module-global mutable state.
- [x] 13.6 (#168) **The test suite is discovered, never enumerated** — `tools/tests/run_all.py`
      globs `test_*.py` so a new test runs in CI with **zero** `ci.yml` edits, replacing the
      hand-maintained unit block + `py_compile` mega-line.
- [x] 13.7 (#169) **Interview provenance recorded — asked vs. defaulted vs. imported** — a new
      `interview:` state block (shape-enforced by `validate_manifest`) makes a considered answer
      distinguishable from a silent assumption, feeding the run-recorder this milestone also ships.
- [x] 13.8 (#170) **A spec-substance floor** — `validate_manifest` rejects an empty
      `spec.objective`/`spec.verification` or zero `functional_reqs`/`milestones` instead of
      producing a hollow repository; presence only, not a taste test.
- [x] 13.9 (#171) **The playbook itself recalls and records** — `generate.md` gains **Step 0.a
      Recall** (apply every matching lesson) and **Step 9 Record** (append the run record); before
      this, an agent following the playbook to the letter never touched memory.
- [x] 13.10 (#172) **`record_run.py` — mechanized run records** — `overrides:` derive
      mechanically from the manifest's `interview:` provenance block against the template
      defaults; the schema gains `outcome`, `lessons_applied`, `failures`, and `rubric`; records
      are facts, never overwritten.
- [x] 13.11 (#173) **`lesson_audit.py` — the learning-loop watchdog** — regression-against-lesson
      detection, a scope-matched dead-lesson report, and rubric-dimension trending, report-only
      like `autotune.py`.
- [x] 13.12 (#174) **Review-time lesson capture** — an optional PR-template `Lesson:` field
      (owner-approved by construction via the squash-merge body) + new `tools/lesson_sweep.py`
      (prints draft ledger entries, never writes); a one-time backfill promotes two prior
      discoveries to L-0003/L-0004.
- [x] 13.13 (#175) **`run-records` self-lint gate** — every `learning/runs/*.yaml` is validated
      against the recorder schema, moving `learning/runs/**` from allow-listed prose to a gated
      file class.
- [x] 13.14 (#176) **README: the tools table, "How EADOS learns", date-stamped model claims** —
      closes the M13 documentation debt; i18n hash refreshed in lockstep.

**Acceptance gate.** A malformed manifest or run record fails loudly with an actionable message
at every one of these seams; the run-recorder produces its first genuine override on
`reference.yaml`; self-lint (all checks) + render-smoke + the discovery-run suite stay green.
**Depends on:** v2.4.0 / v2.5.0 (post-release); incremental — items are independent.

---

**v2.7.0 release (no GitHub milestone) — post-v2.6.0 hardening & the #203 audit-trail epic.**
Three items closed the epic issue [#203](https://github.com/danielPoloWork/pgs-eados/issues/203)
(cross-phase audit trail, manifest concurrency, learning-loop phase coverage), tracked as its own
children rather than a numbered milestone: **#213** — a transition's checkpoint records **live**
`gate_results` (the audit trail becomes the runner's own observation, not a copy of
`workflow.yaml`); **#214** — **optimistic concurrency** for the manifest (`manifest_rev` +
`--expect-rev`, refusing a stale write with `CONFLICT` instead of silently clobbering it); **#215**
— learning-loop coverage (a `migrate`/audit failure channel, a corpus-scaled `autotune` confidence
floor, sensitive-override redaction before the ledger). Alongside the epic, this release also
closed the **#194–#202** defect backlog (`yamlmini` folded-scalar rejection, the renderer's
clobber + `.git`-segment guards, `record_run`'s same-day collision, `autotune`/`lesson_audit`
malformed-record robustness, the phase-skip honor-system gap, fail-open gates under `--strict`,
interview-provenance completeness, and the bidirectional `agent-registry` lint) — fixed here, but
left open as tickets until M15 Wave 0 reconciled the backlog + built its regression index
([#235](https://github.com/danielPoloWork/pgs-eados/issues/235)).

---

## Milestone 14 — agent-contract hardening & runtime re-grounding (post-v2.6.0/v2.7.0)

**Goal.** Close the drift between the deterministic pipeline and the agent actually executing
it, surfaced once multi-step/long-running agent sessions became the norm: re-ground the runtime
invariants at every phase boundary, write down the precedence order across overlapping knowledge
layers, give the agent a pre-flight self-check before opening a PR, promote judgment-laden
guidance to validated few-shot data, and add a Step-0 triage front door so not every request
enters the five-step generation loop. Each item is one PR, tracked under the
`M14 — agent-contract hardening & runtime re-grounding` milestone.

- [x] 14.1 (#221) **Re-ground runtime invariants at phase boundaries** — `phase_runner` emits a
      re-grounding preamble (acting role, human gate, one-PR) at every `report`/`report --propose`
      boundary, plus a compact long-run reminder past `LONG_RUN_CHECKPOINTS` (3) recorded
      transitions — every fact derived from a spec, never a hardcoded copy.
- [x] 14.2 (#222) **Explicit precedence order across knowledge layers** — a new Precedence section
      in `orchestrator/os/README.md` states the canonical order (human decision > blocking
      gate/spec > manifest > profile default > advisory lesson); documentation only.
- [x] 14.3 (#223) **Agent-facing pre-flight self-check** — new `tools/self_check.py` prints an
      advisory checklist (ownership, one-PR, PR metadata, body cross-links, English-on-disk,
      precedence) derived from the specs, front-running the gates before a PR round-trip.
- [x] 14.4 (#224) **Worked-example decision surfaces** — three judgment-laden calls (interview
      ask-vs-default, contribution adopt/decline/escalate, learning apply-vs-skip) become
      `examples:` blocks a new `eados_lint` shape-check validates.
- [x] 14.5 (#225) **Step-0 triage front door** — `orchestrator/triage.yaml`'s ordered,
      stop-at-first-match classification (question/status read → answer directly; bounded
      maintenance edit → one focused PR; generation → the five-step loop), so not every request
      fires the whole pipeline. **Completes M14.**

**Acceptance gate.** A long, multi-transition session still re-states its non-negotiables at each
boundary; a maintenance one-liner no longer forces interview→profile→manifest→render; self-lint
(incl. the new `examples` check) + render-smoke stay green.
**Depends on:** v2.6.0 / v2.7.0 (post-release); incremental — items are independent.

---

## Cross-cutting invariants (every PR, every milestone)

These are **not tasks to complete** but **invariants upheld in every PR** — held across M1–M5 and
the v2.0.0 release, and binding on all future work (M6 included). They are deliberately not checkboxes.

- **English on disk; agent drafts / human merges & publishes; Conventional Commits; one logical
  change per PR; one PR at a time.**
- **Each new spec / role / domain ships `_schema`-validated and lint-gated** — never a special case
  in code (anti-fragmentation), enforced by `eados_lint`'s `os-spec-completeness`,
  `domain-completeness`, `authority-personas`, and `agent-registry` gates.
- **Each milestone keeps RFC-0001, this roadmap, the affected specs, and the `CHANGELOG` in sync in
  the same PR.**

## Open questions (each resolved within its milestone)

| OQ | Question | Resolved in |
|----|----------|-------------|
| OQ1 | Manifest schema-versioning mechanics | ✅ M1-B (item 1.4) — embedded `schema_version` |
| OQ4 | product-manager vs game-designer role shape | ✅ M2-A (item 2.1) — one authority role + domain persona overlay |
| OQ2 | Risk-score thresholds (per-domain?) | ✅ M4-A (item 4.4) — global default + per-domain override in risk.yaml |
| OQ3 | Committed, CI-generated SVG vs Mermaid-only | ✅ Resolved — Mermaid-only (no Node toolchain; `.mmd` committed, SVG on demand) |
