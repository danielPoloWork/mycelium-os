# Intake Interview Protocol

The script the **Enterprise Project Architect** runs to gather everything needed to
generate a governed repository. Work the phases in order. The machine-readable question
bank is [`questionnaire.yaml`](questionnaire.yaml); this document is the human-readable
protocol with the *why* and the follow-up logic.

## How to run it

- **Load the customization overlay first.** Read [`../config/defaults.yaml`](../config/README.md):
  any value set there overrides the built-in default below (precedence: overlay → profile →
  built-in). Copy a non-empty [`../config/house-rules.md`](../config/house-rules.md) body into
  the manifest's `governance.house_rules`. Offer any custom roles under `../config/agents/`.
- **Conduct it in the maintainer's language.** The answers are transcribed into
  `project.yaml` in English (§2 of `AGENTS.md`).
- **Fork first: new or existing?** This protocol frames a **new** project. A repository that
  already has code and history takes the brownfield intake instead —
  [`commands/adopt.md`](commands/adopt.md) (#247, ADR-0021): a read-only gap map, the goal menu,
  and an `adoption:` block in the manifest; it inherits every rule on this list (language,
  defaults, provenance) by reference.
- **Ask only what you cannot safely default.** Each question below carries a default. If
  the default is obviously right for the stated project, state the assumption and move on
  rather than asking. Reserve real questions for decisions that change the output.
- **Record provenance as you go — never retrospectively.** The manifest's `interview:` block
  (#169) records, for every top-level answer key, whether it was `asked`, `defaulted`, or
  `imported`, plus `questionnaire_version` (questionnaire.yaml `meta.version`). Write each
  entry the moment the phase settles it; a block reconstructed at the end is a guess about
  your own behavior. `validate_manifest` rejects a wrong value, a dangling key, and (#201) an
  incomplete block — one entry per answer-bearing section present, plus `questionnaire_version`.
- **Batch related questions.** Prefer a few grouped questions over a long interrogation.
  Phases 1–4 are usually 1–2 rounds; Phase 5 (the spec) is the substantive conversation.
- **Echo back.** After each phase, restate what you captured in one line so the maintainer
  can correct you cheaply.
- **End on the manifest.** The interview's only output is a filled
  [`project.yaml`](project.yaml.template); you show it for confirmation before rendering.

---

## Phase 0 — Frame the project

Establish the one-liner so every later question has context.

- **Q0.1 — What are we building, in one sentence?** → `PROJECT_TAGLINE`, `PROJECT_TITLE`.
- **Q0.2 — What kind of thing is it?** `library` / `service` / `cli` / `app`. Drives the
  capability flags (`IF_SERVICE`, packaging, public API). → `PROJECT_KIND`.
- **Q0.3 — Proposed repository name?** Kebab-case. Suggest one from the tagline if the
  maintainer has none (e.g. *Rust token-bucket rate limiter* → `acme-rust-ratelimiter`).
  → `PROJECT_NAME`, and derive `PROJECT_SLUG` (single lowercase word, e.g. `ratelimiter`).
- **Q0.4 — What is the development target?** `software` / `web` / `game` / `mobile` (default
  `software`). This loads [`domains/<domain>.yaml`](domains/_schema.md), which sets the active
  roles, the artifacts (PRD vs **GDD** for a game), the hard NFR budgets (accessibility + Core Web
  Vitals for **web**; RAM/GPU/framerate for a game; app-size/cold-start for mobile), and the
  milestone vocabulary (SemVer vs Alpha/Beta/RC) used from Phase 5 onward. **web** is the shipped
  seed for the most common modern target (website / web app / web service). If the chosen target
  has no profile yet, that is the normal path: author it from
  [`domains/_template.yaml`](domains/_template.yaml) first. → manifest `domain`.
- **Q0.5 — Enterprise posture?** `standard` (default) / `enterprise`. **Orthogonal to the target,
  not a target of its own:** an `enterprise` posture raises the governance/compliance bar on *any*
  domain — mandatory ADRs for security-relevant decisions, stricter review, an explicit
  compliance-docs expectation — rather than adding a fourth domain (see
  [ADR-0015](../docs/adr/0015-web-domain-and-enterprise-posture.md)). State the assumed `standard`
  default and only ask when the project is plausibly regulated/large-org. → manifest
  `governance.posture`.

## Phase 1 — Language(s)

The single most structural choice — it selects the profile and the source-tree segment.

**EADOS is open to *any* programming language.** The nineteen shipped profiles are seeds, not the
allowed set — there is no "unsupported language", only "language not yet profiled".

- **Q1.1 — Primary implementation language (and standard/edition)?** → `LANG`, `LANG_NAME`,
  `LANG_STANDARD`. If a profile already exists in [`profiles/`](profiles/), use it. **If not,
  that is the normal path, not an error:** author one by copying
  [`profiles/_template.yaml`](profiles/_template.yaml) to `profiles/<lang>.yaml` (schema:
  [`_schema.md`](profiles/_schema.md)), add an ADR, then resume — the `profile-author` role
  drives this. Never hardcode toolchain facts into a template to skip it.
- **Q1.1a — Language-fit check (advisory).** Weigh the requested language against the domain in
  the spec using [`language-fit.md`](language-fit.md). On a *clear* mismatch, surface 1–2 better
  fits with a one-line reason and let the maintainer confirm or override — **their choice is
  final.** On a sensible choice, say "good fit" and move on. (Phase 5 re-checks this once the
  spec is concrete.)
- **Q1.2 — Any secondary/interop language?** (e.g. a C ABI under a C++ core, Python
  bindings, a WASM target.) If yes, note the second profile and how the surfaces relate.
  **SQL, CSS, and HTML are declared here** — as the schema a backend owns, or the markup/styles
  of a frontend — not as the primary language (see [`language-fit.md`](language-fit.md)).
- **Q1.3 — Reverse-domain group path?** Ask for the maintainer's **own** reverse-domain (e.g.
  `com/acme`); there is no built-in default — `it/d4np` is only the reference project's value, not
  a fallback. → `GROUP_PATH`, `GROUP_DOTTED`. From `LANG` + `GROUP_DOTTED` + `PROJECT_SLUG` the
  profile derives `NAMESPACE` in the language's native idiom (`com::acme::ratelimiter`,
  `com.acme.ratelimiter`, `@acme/ratelimiter`, `github.com/acme/ratelimiter`, …).

> **Follow-up triggers (Phase 1):** a systems language (C/C++/Rust) → ask about ABI
> stability and memory model (feeds `IF_PUBLIC_API`, `IF_THREADING`). A managed/runtime
> language (Java/Python/TS/Go) → ask about the minimum runtime version (feeds the CI
> matrix floor).

## Phase 2 — Frameworks

What the project is built *with* and *against*.

- **Q2.1 — Application/domain frameworks?** Web (Axum, FastAPI, Spring, Express/Nest),
  data, UI, etc. — or "none, standard library only" (the reference project's stance).
- **Q2.2 — Runtime/concurrency model?** Sync, async (which runtime), threads, actor.
  Sets `IF_THREADING` and the sanitizer/race-tooling choices.
- **Q2.3 — Public surface & compatibility target?** Stable API/ABI? Supported consumers
  and platforms? Sets `IF_PUBLIC_API` and `TIER1_PLATFORMS`.

> **Follow-up triggers (Phase 2):** "async" → which executor, and does it need
> race-detection in CI? "web service" → health/readiness, config, and deploy target
> (feeds `IF_SERVICE`). "no framework / stdlib only" → record the zero-dependency stance
> as a future ADR-0002 sibling.

## Phase 3 — Tools

The toolchain the profile pre-fills; confirm or override per project.

- **Q3.1 — Build system & package manager?** Defaults from the profile (`BUILD_TOOL`,
  `PKG_MANAGER`). Override only if the project deviates.
- **Q3.2 — Test framework & coverage tool?** Defaults from the profile (`TEST_FRAMEWORK`,
  `COVERAGE_TOOL`). Confirm the coverage target (the reference uses ≥80% line).
- **Q3.3 — Formatter & linter?** Defaults from the profile (`FORMATTER`, `LINTER`). These
  become the CI `format` and `tidy`/lint jobs and the repo-root config files.
- **Q3.4 — Runtime checkers / sanitizers?** Defaults from the profile (`SANITIZERS`).
  Confirm which are feasible on the CI matrix.
- **Q3.5 — API documentation generator?** Defaults from the profile (`DOC_TOOL`).
- **Q3.6 — Benchmarks?** Does performance need a reproducible benchmark suite? Sets
  `IF_BENCH` and `SRC_BENCH` / `CMD_BENCH`.

## Phase 4 — Governance & GitHub

How the repository is run — reproduces the reference project's GitHub rules.

- **Q4.1 — GitHub owner/org and default branch?** → `OWNER`, `DEFAULT_BRANCH` (default
  `main`). Maintainer display name and copyright holder → `MAINTAINER`, `AUTHOR`.
- **Q4.2 — License?** Default `MIT`. → `LICENSE_ID`, `YEAR`.
- **Q4.3 — Conventional-commit scopes?** Propose a set from the architecture's components
  plus the standard `build, tests, docs, ci`. → the `EACH_SCOPE` list.
- **Q4.4 — Versioning start point?** Pre-1.0 milestone-driven (default, matches the
  reference) or start at 1.0.0? Confirm SemVer and the release cadence.
- **Q4.5 — PR metadata policy?** Confirm assignee (defaults to the **owner** — never `@me`,
  which resolves to whichever actor drafts the PR), the one-type-label scheme, and per-release
  milestones (reference ADR-0040). A GitHub **Project** is attached where one exists; reviewers
  are deferred until a second collaborator, exactly as upstream.
- **Q4.6 — Packaging/distribution?** Distributed via a package registry? Sets
  `IF_PACKAGING`. Default off unless the maintainer asks.
- **Q4.7 — Authoring languages?** Asked **unconditionally** — state the defaults and let the
  maintainer override them; never apply them silently (issue #150 / ADR-0016). Three parts:
  - **Documentation language** — the canonical prose-doc language (`DOC_DEFAULT_LANG`, default
    `en`). Echo the assumed `en` back for confirmation.
  - **Code-comment language** — the natural language for source comments (`CODE_COMMENT_LANG`,
    default `en`). **Identifiers, public API names, commits, branches, and PR text stay English**
    regardless (the cross-project consistency bar); a non-English comment choice is honoured as a
    **recorded exception** rendered into the generated `AGENTS.md` §2 (see ADR-0016).
  - **Extra documentation languages (i18n)** — default none. Naming target languages as
    `code`+`name` pairs (`DOC_LANGS`, e.g. `it`=Italian, `es`=Spanish) is what turns i18n **on**
    (sets `IF_I18N`): translations are *derived* copies under `docs/i18n/<code>/` of the
    `DOC_DEFAULT_LANG` sources; seeds `docs/i18n/translation-status.md` and the lint's
    `i18n-freshness` gate.
- **Q4.8 — Release/news announcements on social channels?** Default off. If on, capture the
  channels (`ANNOUNCE_CHANNELS`, e.g. X, Discord, LinkedIn, Reddit, Mastodon, a blog) and who
  owns each handle/webhook. Sets `IF_ANNOUNCE`; seeds `docs/workflow/announcements.md`. The
  agent *drafts* the announcement; a human *publishes* it — the same boundary as releases.

## Phase 5 — The functional specification

This is the real conversation. The goal is a frozen spec
([`templates/docs/specs/template.md`](../templates/docs/specs/template.md)) that mirrors
the reference spec's shape: Objective, Functional Requirements, Non-Functional
Requirements, Logical Architecture, Public Interface, Verification Strategy.

- **Q5.0 — Provenance: do you already have a spec?** Ask this **first**. `import` (a) or
  `coauthor` (b), default `coauthor`.
  - **(a) I already have one** — a technical spec / PRD / SRS, however partial. Then **import &
    validate**, do *not* re-interview: ingest the document and **map it onto the six-section shape**
    (Objective, Functional, Non-Functional, Architecture, Public Interface, Verification). Run the
    **gap audit** — for every section and every requirement apply the Phase-5 testability follow-up
    ("how would CI prove this failed?") — and produce an explicit list of what is **missing** or
    **untestable**. Then ask Q5.1–Q5.7 *only for the gaps*; everything the document already covers is
    carried over, not re-asked. (Still run the Q5.1 language-fit check once the objective is clear.)
  - **(b) Let's build it together** — the Q5.1–Q5.7 co-authoring flow below.
  Either path ends in the **same** frozen `docs/specs/01_spec_<slug>.md` and is held to the same
  testability discipline. → `spec.provenance`.

Walk these — **all** of them for **(b)**, and for **(a)** only the gaps the audit flagged — asking
follow-ups until each is concrete enough to test against:

- **Q5.1 — Objective & business context.** What problem does this solve, and for whom?
  What pain (latency, fragmentation, correctness, cost) does it remove? → `SPEC_OBJECTIVE`.
  Now that the domain is concrete, **re-run the language-fit check** ([`language-fit.md`](language-fit.md)):
  if the spec reveals a clear mismatch with the Phase-1 language, say so with a one-line reason
  and let the maintainer confirm or switch — their choice is final, then continue.
- **Q5.2 — Functional requirements.** The observable behaviors. Push for measurable
  phrasing ("O(1) allocation", "p99 < 5 ms", "exactly-once") over adjectives. →
  `EACH_FUNCTIONAL_REQ`.
- **Q5.3 — Non-functional requirements.** Performance, memory, portability, security,
  no-leak / no-UB guarantees, dependency policy. → `EACH_NONFUNCTIONAL_REQ`.
  **Budget follow-up (scalability fold, #240; enforced #249).** For each **hard** NFR axis the
  domain declares (`domains/<domain>.yaml` `nfr_axes[].hard_budget: true` — typed with
  `unit`/`direction`, and a suggested `seed` to offer as the default: a game's framerate/RAM/GPU,
  web's Core Web Vitals, a service's p99 latency), elicit a **numeric target**, never an
  adjective: "p99 < 5 ms", "60 fps", "cold-start < 2 s", "heap ≤ 256 MB". Record each as a
  **typed `spec.nfr_budgets` entry** (`{axis, target, unit, metric?}` — one entry per `metrics`
  name for a composite axis like Core Web Vitals; the level from the axis's `scale` for
  accessibility) *and* as a §3 non-functional requirement, so the RFC's *Scalability budgets*
  fold states it. The **`nfr-budgets` audit-overlay gate** (#249) evaluates them in-process: a
  hard axis with no recorded number — or a recorded measurement that violates it — fails the
  audit entry; the budget is a gate, not a promise.
- **Q5.4 — Logical architecture & core algorithm.** The central data structure or control
  flow. Capture it as prose + a diagram block; it seeds the first design ADRs. **Also elicit a
  structured architecture style** from
  [`design-patterns.md`](../templates/docs/patterns/design-patterns.md) §5 — *Layered / Hexagonal /
  Clean / MVC-MVVM / Event-Driven / CQRS / Microkernel / DDD building blocks* — with a sensible
  default per kind/domain: a **library** commits to none (it exposes an API, not an app
  architecture); a **service/app** → Layered or Hexagonal; **web** → Layered / MVC / Clean;
  **mobile** → MVVM / Clean. Optionally name the **expected first-class patterns** (each a `name` +
  one-line `why`) and choose the **pattern-discipline posture**: `advisory` (default — the agent
  advises, the human decides) or `enforced` (conformance to the style + adopted patterns becomes a
  review expectation). These seed the generated `docs/patterns/README.md` (architecture-style note +
  the *Planned* table), so the choice shapes the repo instead of leaving the catalogue empty. →
  `SPEC_ARCHITECTURE`, `spec.architecture_style`, `spec.patterns`, `spec.pattern_discipline`.
- **Q5.4a — Layered package skeleton? (service / app / web only).** For a `service`/`app`, or a
  `web` project, offer an optional **layered layout** driven by the style above: which internal
  packages to scaffold under `src/main/…` (mirrored under `src/test/…`) — e.g. `controller`,
  `service`, `repository`, `dto`, `mapper` (add `config`, `api`, `domain`, `query` as the style
  needs). A **library keeps the flat shape — do not offer it.** Opting in sets
  `capabilities.layered: true` and records the package names in `spec.layers`; the generator seeds
  each as an empty (`.gitkeep`) package and notes the layout in the generated ADR-0002. →
  `capabilities.layered`, `spec.layers`.
  - **Algorithm sketch (pseudocode fold, #240) — optional.** For a non-obvious core algorithm,
    capture a short **language-free** pseudocode sketch (the control flow + invariants) alongside
    the prose/diagram; it mirrors into the RFC Decision's *Algorithm sketch* fold. Skip it when the
    approach is standard. → `SPEC_ARCHITECTURE` prose.
  - **Data & schema (database fold, #240).** If the change owns persistent state, capture the data
    model — entities, relations, the target normal form (+ any deliberate denormalization and its
    reason), and the migration policy — **within ADR-0004's frame**: the store is a *secondary*
    component declared at Q1.2, never a primary profile, and there is no `database` command without
    a superseding ADR. → `SPEC_ARCHITECTURE`; the RFC's *Data & schema* fold.
  - **Web UI architecture (web domain).** When `domain == web`, cover the frontend checklist the
    other folds leave implicit: **loading / empty / error states**, **responsive breakpoints**, the
    **accessibility conformance level** (state it — e.g. WCAG 2.2 AA, a web hard `nfr_axis`), and
    **component reusability + props/API conventions**.
- **Q5.5 — Public interface / API contract (api + systemdesign folds, #240).** The
  functions/types/**endpoints** consumers depend on — a checklist, not prose: the operations, their
  **payloads** (request/response or parameter/return shapes, required vs optional), the **error
  model** (the failure taxonomy consumers must handle, not just the happy path), and the
  **versioning / SemVer surface** (what a MAJOR bump would be). → `EACH_PUBLIC_API`,
  `PUBLIC_INCLUDE_HINT`. For a `service`/`web` project, offer **`capabilities.api_spec`**: it seeds
  a `docs/api/` OpenAPI/IDL stub the contract is written into (the RFC *states* it; the stub
  *records* it). → `capabilities.api_spec`.
- **Q5.6 — Verification & test strategy.** How correctness and performance are *proven* —
  unit tests, sanitizers, property tests, fuzzing, the canonical leak/race check, the
  benchmark methodology. → `SPEC_VERIFICATION`.
- **Q5.7 — The full roadmap, up front.** Milestone 1 is the universal bootstrap (build system,
  skeleton, CI) — automatic; you may add extra M1 items (→ `EACH_MILESTONE1_ITEM`). Then lay out
  **all** the project's milestones now, not one at a time: for each, a `number` (2, 3, …), a
  `title`, a one-line `goal`, and its `items` as pre-numbered tasks (`2.1`, `2.2`, …). Ask
  follow-up questions until the whole roadmap is concrete; never defer milestones to "later". →
  `EACH_MILESTONE`.
  - **Routing-signal follow-up (optional, #306/ADR-0023).** For each item, ask whether it
    carries a routing *signal* — `security`, `adr`, `severity:medium|high`, `sets-pattern`
    (first of its class), `decision-heavy` (the decision is the deliverable) — and record the
    item as `{text, signals[]}` instead of a plain string. Signals, **never tiers**: the
    `os/routing` rules stay the one place that maps signals to routes, and the renderer derives
    each item's advisory route (`route: <tier> / <effort>`) into the generated `ROADMAP.md`.
    Plain-string items stay legal and render unchanged (the legend's floor covers them).

> **Follow-up discipline (Phase 5):** for every requirement, ask "how would CI prove this
> failed?" If there is no mechanical check, either refine the requirement until there is,
> or record it as an explicitly manual gate. This is what keeps the generated quality bar
> real rather than aspirational.

---

## Closing the interview

1. Merge the answers with the resolved profile(s) into `orchestrator/project.yaml`, and
   verify the `interview:` provenance block you filled as you went is complete — one entry
   per top-level answer key, `questionnaire_version` set.
2. **Present the manifest to the maintainer**, pointing them at the `interview.provenance`
   entries marked **`defaulted`** — every value you assumed rather than asked — so a wrong
   default is caught now. A considered answer and a silent assumption must never look the
   same at confirmation time.
3. On confirmation, proceed to [`generate.md`](generate.md). On any change, edit the
   manifest and re-confirm — never render from an unconfirmed manifest.
