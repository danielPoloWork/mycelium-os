# ADR-0019: Command-surface taxonomy — phases, sub-modes, cross-cutting commands, adapters

## Status

Accepted (2026-07-10)

## Context

The maintainer's command wishlist is a flat menu of eleven one-shot verbs
(`interview / debug / refactor / optimizecode / systemdesign / api / database / scalability /
security / testcases / pseudocode`). EADOS, however, models work as a **small, gated phase
machine over a persistent manifest** (RFC-0001 §3), routes deterministically by phase +
ownership — never by fuzzy intent (RFC-0001 D2) — and explicitly rejects a monolithic 360°
orchestrator (RFC-0001 §1). Minting eleven phases would betray all three commitments; leaving
the verbs unmapped keeps the surface undiscoverable and invites exactly the ad-hoc, ungoverned
handling the OS exists to prevent.

The owner ratified a hybrid taxonomy on 2026-07-09 (M15 plan, decision 1; drafted as issue 0022 /
[#234](https://github.com/danielPoloWork/pgs-eados/issues/234)). This ADR records it as the single
citable authority for every M15 command issue, and decides the **governance boundary** the
cross-cutting code commands (#242/#243/#244/#246) were blocked on: may they run against
pasted/standalone code with no active `delivery_state` manifest?

## Decision

Every wishlist verb classifies into **exactly one** of four classes. The classes — not the verbs —
are the extension points of the command surface, and each class is closed: extending it takes an
ADR, never an ad-hoc addition.

1. **Phases.** The state machine stays the closed set
   `init → design → plan → scaffold → audit → refactor` (→ `migrate` once the #236 rename lands)
   defined in `workflow.yaml`. **No wishlist verb mints a phase.** `interview` is not a command at
   all: it is the intake of `init` (and of the planned brownfield front door `/eados adopt`, #247)
   and surfaces only as an alias.

2. **Phase sub-modes** — a deepened entry into an existing phase.
   `systemdesign`, `api`, `database`, `scalability`, `pseudocode` → sub-modes of `design` (#240);
   `security` (controls + threat modeling) → sub-mode of `audit` (#241). A sub-mode adds **no new
   state, no new transition, no new authority**: its artifacts are the phase's artifacts, its
   gates the phase's gates, its owner the phase's owner. `database` stays inside ADR-0004's frame
   (SQL remains a secondary Q1.2 component; no primary profile, no standalone command).

3. **Cross-cutting commands** — the class `/eados status` and `/eados review` already occupy,
   extended by `debug` (#242), `refactor` in its code-quality meaning (#243, after the #236
   rename vacates the name), `optimize` (#244 — the wishlist's `optimizecode`), and `testcases`
   (#246, QA-owned per #245; ratified as cross-cutting by the M15 plan's wishlist mapping).
   Members are **advisory and non-state-advancing** — they never write `delivery_state.phase` and
   never propose a phase transition — and everything they *do* write is **fully governed**:
   role-owned per `authority.yaml`, deterministically gated, human-confirmed, one logical change
   per drafted PR, artifacts landing only in governed surfaces (bug ledger, `docs/benchmarks`,
   patterns catalogue, `src/test/**`). Read-only members (`status`) satisfy these obligations
   vacuously — they produce no artifacts. A new member requires an ADR, exactly like a new phase.

4. **Adapters + aliases** — surfacing, not semantics. Every verb reaches users through thin host
   adapters (#239) and the **canonical alias table in `orchestrator/commands/README.md`**. An
   alias only routes a verb to its class target; it never adds behavior, state, or authority. The
   README table is the single registry the adapter-coverage check (#239) enforces against.

**Governance boundary — a manifest is required.** A cross-cutting code command runs **only
against an initialized project**: a repository whose manifest carries `delivery_state`. Given
pasted or standalone code with no active manifest, the command **refuses and routes** — greenfield
to `/eados init`, an existing ungoverned repository to `/eados adopt` (#247). A plain *question*
about code stays a Step-0 triage question (`0-question` in `triage.yaml` — answered directly,
no command run); what requires the manifest is the
*command run*, because everything a command produces presupposes governance: its artifacts need a
governed surface to land in, its owner is resolved from `authority.yaml` path globs (no paths →
no owner → no gate), and its PR needs traceability edges (RFC ↔ milestone ↔ PR) to anchor.
Dropping the boundary would rebuild the ungoverned per-snippet code chatbot that the M15 plan
lists as out of scope — this ADR closes that door deliberately.

**Alternatives rejected.** (a) *Eleven phases* — state-machine explosion; betrays RFC-0001 D2/D3
and the §1 monolith rejection. (b) *A free-standing "code assistant" mode* outside the manifest —
the ungoverned chatbot by another name. (c) *Intent-classification routing* of the flat verb menu
— already rejected as RFC-0001 D2 (arbitrary, non-deterministic). (d) *Aliases only, no taxonomy*
— leaves every downstream issue re-deciding phase-vs-command from scratch; an alias line buried in
a draft is not an authority.

## Consequences

- **RFC-0001 §2 gains non-goal N5** admitting the bounded cross-cutting class explicitly, so the
  class cannot be read as scope creep toward the rejected monolith.
- **`orchestrator/commands/README.md` documents the four classes and the canonical alias table**;
  planned commands appear there as planned, so the surface registry is complete before Wave 2
  ships.
- **#242/#243/#244/#246 are unblocked** with a citable precondition (manifest required, refusal
  route stated); #240/#241 build sub-modes without new machinery; #239's adapter-coverage check
  gets its canonical verb list. The M15 command drafts (0011, 0016–0019, 0024, 0025) cite this
  ADR.
- The `refactor` naming collision is resolved by sequencing, not by this ADR: the taxonomy defines
  the end-state; the phase rename (#236) must land before the cross-cutting `refactor` command
  (#243) may ship.
- Nothing changes in the phase machine, the manifest schema, or any tool today — this ADR is
  pure recorded authority; the machinery lands through the cited M15 issues.

## References

- Issue [#234](https://github.com/danielPoloWork/pgs-eados/issues/234) (draft 0022) — the
  decision request; owner ratification 2026-07-09 (`.issues/M15-command-surface-milestone.md`).
- RFC-0001 §1 (monolith rejected), §2 (goals/non-goals), §3 (phase machine), D2/D3 (routing and
  orchestration forks).
- ADR-0004 (SQL stays secondary), ADR-0011 (the phase-machine pivot), ADR-0014 (`/eados review`
  precedent for advisory cross-cutting), ADR-0015 (posture orthogonality — the sibling M15
  authority for #248).
- M15 issues: #239 (adapters), #240 (design folds), #241 (security sub-mode), #242 (debug),
  #243 (refactor-cleanup), #244 (optimize), #245/#246 (QA persona + testcases), #247 (adopt),
  #236 (phase rename).

---

## Addendum — 2026-07-27: class 3 admits `/eados upgrade` (#320)

Class 3 is closed — *"a new member requires an ADR, exactly like a new phase"*. The record admitting
**`upgrade`** is the **2026-07-27 addendum to
[ADR-0003](0003-generated-repos-are-self-governing.md)**, because the decision being made is
substantive rather than taxonomic: ADR-0003's two rejected branches were both about *writing* into a
generated repository, and the third branch — advisory notification — was never weighed. That is
where a future reader will look for it, so it is recorded there and pointed at from here rather than
duplicated.

It satisfies this ADR's class-3 obligations the way `status` does: **read-only**, therefore
advisory, non-state-advancing, and vacuously compliant with the "everything it writes is governed"
clause — it writes nothing at all, asserted by hashing the target tree across a run.

**One boundary reads differently for this member, deliberately.** The class requires an initialized
manifest (`delivery_state`). `upgrade` runs against a repository that may predate the provenance
stamp entirely, and it does *not* refuse-and-route on a missing manifest: it falls back to the
recorded provenance line in the rendered `AGENTS.md`, and with neither it explains what is missing
and exits cleanly. The manifest boundary exists because a command's *artifacts* need a governed
surface to land in and an owner to resolve; a command that produces no artifact has nothing to
govern, and routing an old repo to `/eados init` would be advice to overwrite the very repository
it came to inform.

---

## Addendum — 2026-07-27: adapters are data, and every host gets a tree (#375)

**Status:** Accepted · **Deciders:** Maintainer, Enterprise Project Architect · **Related:**
ADR-0024 (Host → Provider → Models), #239 (the Claude adapters), #373 (the host-independent CLI),
#374 (the command table in the generated contract), #372 (whether a consumer *tracks* the tree).

### What this addendum decides

The Delivery paragraph above describes adapters for **one** host. `os/routing/routing.yaml`
declares **four**, and since M19 / ADR-0024 provider-agnosticism is an explicit commitment: EADOS
resolves tier, effort and model for any host. The command surface never followed — `codex`,
`gemini` and `opencode` shipped **zero** adapters, so the OS was built to know which host it is on
and did nothing with that knowledge where a user feels it most.

**Adapters become data.** Each host declares a `commands:` block — `scope`, `dir`, `ext`, `format`,
`nest`, `invocation` — and one renderer (`adapter_render.py`) emits a tree from the canonical
command registry. Hand-maintaining 14 commands across 4 hosts would be 56 files and guaranteed
drift, which is the failure #365 and #366 each closed with a gate; here it is closed by not creating
the copies at all.

**The class boundary is unchanged.** An adapter remains *surfacing, not semantics* (class 4): every
generated file is a **pointer** naming the canonical procedure. No procedure body is copied, so
`orchestrator/commands/` stays the single source of truth for every host.

### Three scopes, and the middle one is the interesting decision

| `scope` | behaviour | who |
|---|---|---|
| `project` | EADOS writes the tree into the repository | Claude Code, Gemini, OpenCode |
| `home` | the host reads from **outside** the project; EADOS renders inside it and prints the install command | Codex |
| `none` | no verified mechanism; the surface is `AGENTS.md` §13 + `eados.py` | — |

**Codex is a constraint, not an oversight**, and it is recorded so it stops looking like a gap
nobody got to. Its custom prompts live in `~/.codex/prompts` and the documentation states they are
*"not shared through your repository"*. Writing there would break the containment posture the
installer is built on — the same rule that makes a bundle install additive and no-clobber. So EADOS
renders the tree into the project and the **user** installs it with one command.

### Verification is part of the decision

Every `commands:` block was verified against the host's **current documentation** on 2026-07-27, and
that requirement is now part of the schema rather than a one-off diligence:

- **Gemini** — project commands in `<project>/.gemini/commands/`, TOML, `prompt` required and
  `description` optional, subdirectory namespacing via `:` (so `eados/init.toml` → `/eados:init`).
- **OpenCode** — `.opencode/commands/<name>.md` with YAML frontmatter; the filename becomes the
  command name. **Subdirectory namespacing is not documented**, so names are flat (`/eados-init`)
  and `nest: false` records that as a verified limit rather than a preference.
- **Codex** — `~/.codex/prompts`, home-scoped (see above).

A host whose format cannot be confirmed declares **`scope: none`**, never a guess. Shipping a
directory a host does not read is worse than shipping none: it looks like support, and the failure
is silent. This mirrors the `detect[]` rule — only observed markers belong in the catalog.

### One question this addendum deliberately does NOT answer

Verification surfaced it: **Codex custom prompts are deprecated**, and the documented successor is
**skills** — which *are* project-scoped and would remove the `home` constraint entirely. But skills
are invocable **implicitly** (model-triggered by description matching), and the Decision above
rejected `.claude/skills/` for exactly that reason: it is the fuzzy-intent routing RFC-0001 D2
rules out.

That is a real trade — a project-scoped surface bought with a mechanism this ADR declined — and it
is **the maintainer's to make**, not one to settle in passing while implementing something else.
Recorded here as open. Codex stays `scope: home` until it is decided.

### Consequences

- `adapter_render.py --host <id>` generates the tree; `--list` shows what each host supports. The
  `init` procedure resolves the host explicitly (manifest `routing.host` → `detect[]` → ask) and
  **states which host it generated for** — a silent default is how every non-Claude host quietly
  received Anthropic model names before #325.
- `command-adapters` covers **every** project-scoped host, symmetrically (missing adapter, orphan
  adapter, non-pointer), for whichever trees are present.
- **Whether a consumer commits a generated tree is #372's question, not this one.** This addendum
  decides how trees are produced; the factory therefore ships only the Claude tree it already had,
  and the renderer is invoked on demand. Pre-empting an open decision by committing 28 more files
  would have settled #372 by accident.

---

## Addendum — 2026-07-27: a generated repo does not commit its adapter tree (#372)

**Status:** Accepted · **Deciders:** Maintainer, Enterprise Project Architect · **Related:** the
2026-07-27 adapters-as-data addendum above (#375), #374 (the command table in the generated
contract), #373 (the host-independent CLI), #353 (the run-record exception this mirrors).

### The question

A generated repository ignores `.eados-core/` — the shipped `.gitignore` says why in its own words:
*"the bundle is copied in to (re)generate this repo; it is not part of the project's own source."*
`.claude/commands/eados/` was **tracked**: the one piece of factory tooling landing in a consumer's
history as if it were theirs. Nothing decided that; it fell out of `.gitattributes` not listing
`.claude` and `gitignore.tmpl` not mentioning it.

### Decision

**A generated repository does not commit any host's adapter tree.** `gitignore.tmpl` excludes
`.claude/commands/eados/`, `.gemini/commands/eados/`, `.opencode/commands/eados-*` and
`.eados/adapters/`, with the reason stated at the point of use — the shape #353 established for the
run-record exception, so a maintainer can tell an intentional rule from an oversight.

The exclusions are scoped to the **EADOS subtree**, never the host's whole command directory: a
project's own `.claude/commands/mine.md` stays tracked. Asserted by a test, because "ignore the
adapters" written carelessly would silently swallow a team's own commands.

### Why this reverses the recommendation the issue was filed with

#372 recommended *keep them tracked*, on the grounds that a teammate who clones should get working
slash commands. Two facts made that wrong, and neither existed when it was written:

1. **A committed adapter is a dangling pointer.** An adapter names
   `.eados-core/orchestrator/commands/<cmd>.md` — a path the same `.gitignore` excludes. Verified
   against a real render: the adapter is tracked, its target is not. Whoever clones gets slash
   commands that resolve to a **missing file**. That is worse than absence: an absent command is
   obviously absent, while a dangling one fails at the point of use and reads as a broken repo.
2. **Trees are now per-host** (#375). Committing one imposes the original author's host on the whole
   team — a `.claude/` tree does nothing for a teammate on Gemini, Codex or OpenCode, each of whom
   generates their own in one command.

The cost that argued for tracking has also collapsed. When #372 was filed, an uncommitted tree meant
the commands were effectively invisible. Since then **#374** put the full command table in the
generated `AGENTS.md` §13, and **#373** gave every host a CLI covering all 14 verbs. A teammate who
clones now finds the commands in the contract they already read, and one command away.

### The factory is not a consumer

EADOS keeps its own `.claude/commands/eados/` tracked and shipped in the bundle. That tree is the
factory's working copy *and* what the installer places; the decision above governs **generated**
repositories. Conflating the two is what made this look like an inconsistency in the first place.

### Consequences

- `gitignore.tmpl` carries the exclusions and the reason; deleting those lines is the supported way
  for a team that *does* want a shared tree, and the comment says so.
- The generated `AGENTS.md` §13 tells the reader their host's tree is not committed and how to
  generate it — the contract is where they already are.
- The installers state that the adapters they place will not be committed, so the additive
  `--with-adapters` prompt does not imply otherwise.
