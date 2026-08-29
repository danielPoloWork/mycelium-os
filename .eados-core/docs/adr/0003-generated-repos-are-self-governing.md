# ADR-0003: Generated repositories are self-governing

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Maintainer, Enterprise Project Architect
- **Related:** ADR-0001, `templates/AGENTS.md.tmpl`, `orchestrator/generate.md`

## Context

Once EADOS renders a new repository, that repository will live and evolve on its own — with
its own agents, CI, and maintainers. We must decide whether the generated repo stays coupled
to EADOS (pulling rules/templates at runtime) or is fully independent after generation.

## Decision

A generated repository is **self-governing**: generation copies a complete, standalone
`AGENTS.md` (and adapters, CI, lint, docs) into it, and from that point the new repo's own
`AGENTS.md` is authoritative. The generated repo has **no runtime dependency** on EADOS — it
does not fetch templates, rules, or the lint from EADOS. EADOS's responsibility ends at the
bootstrap PR; the two-contracts rule (`AGENTS.md` §header note) makes this explicit so an
agent never imports EADOS's own rules into a generated project.

## Alternatives Considered

- **Submodule / runtime link to EADOS.** Rejected — couples every project to the factory,
  creates version-skew and supply-chain risk, and contradicts the reference project's
  zero-external-governance-dependency posture.
- **Re-render on every EADOS change.** Rejected — projects diverge intentionally after
  bootstrap (their own ADRs, milestones, patterns); re-rendering would clobber that history.

## Consequences

- Generated repos are portable and durable; they outlive any EADOS version.
- Improvements to EADOS benefit *future* generations, not retroactively — acceptable, since
  each repo owns its evolution via its own ADRs.
- The generated `consistency_lint.py` is a self-contained copy with a filled CONFIG block,
  not a shared library.

## References

- `templates/AGENTS.md.tmpl` (header note: "this contract is now authoritative");
  `orchestrator/generate.md` Step 8 (hand-off).

---

## Addendum — 2026-07-27: self-governing is not the same as uninformed (#320)

**Status:** Accepted · **Deciders:** Maintainer, Enterprise Project Architect · **Related:**
ADR-0014 (`/eados review` recommends, never merges), ADR-0017 (advisory-first), ADR-0019 §3
(cross-cutting command class), #319 (the provenance stamp this depends on).

### What this addendum decides

The Alternatives above weigh **two** branches: couple the generated repo to the factory
(rejected), or re-render it on every factory change (rejected — it clobbers the divergence the
repo is *supposed* to accumulate). Both branches are about **writing** into the generated repo.
Because neither survived, the record has been read ever since as deciding the whole question, and
the operative answer became *nothing*: EADOS has shipped twelve releases, several carrying fixes
with real consequences downstream (#128 a UTF-8 crash across the CLI tools, #129 installer
tar-slip hardening, #310 an action pin that lied about its own version), and there has been no
channel to an already-generated repository — not to update it, and not even to **tell** it.

That silence was never decided. It was inherited from a two-option frame written when there was
one generated repo and its maintainer was the factory author. #96, #140 and the `egl-utils-js`
field run (#306/#313) are evidence that this is no longer true.

**There is a third branch, and it is admitted: advisory notification.** EADOS may *tell* a
generated repository what has changed upstream since the version that produced it. It may not act
on that repository. Concretely:

- **`/eados upgrade` reports and stops.** No patches, no three-way merge, no `git` operations, no
  manifest edits, no "upgrade my repo for me". The maintainer cherry-picks; the tool says what is
  worth cherry-picking. The moment it writes, the rejected re-render branch is back through the
  side door — so the boundary is asserted by a test, not left to convention.
- **The stamp is read, never guessed** (#319). Absent a recorded provenance, the command explains
  what is missing and how to record it, and exits — an unstamped repo and a repo stamped by an
  unknown version are different situations, and inventing a starting point would silently produce
  a delta against the wrong baseline.
- **What cannot be established is stated, not omitted.** A report the tool could not filter says
  so; it never reports "you are up to date" from an absence of evidence (L-0006).

### Why this does not weaken the original decision

The Decision above says a generated repo has **no runtime dependency** on EADOS. Advisory
notification adds none: nothing is fetched at build time, nothing is imported, no gate consults
the factory, and a repo that never runs the command behaves exactly as it does today. The command
is a thing a **human chooses to run**, on the factory side, pointed at a repo — the same
relationship a maintainer already has with `git log` of an upstream they vendored.

The Consequences' line *"improvements to EADOS benefit future generations, not retroactively —
acceptable, since each repo owns its evolution via its own ADRs"* is unchanged and is in fact the
premise here: a repo owning its evolution is precisely why it must be **able to see** what it is
choosing between. Ownership without information is not autonomy.

This is also the posture the project already takes on every other axis where the OS knows
something the human must decide: routing is advisory (ADR-0017 — *"the human keeps final model
authority"*), `/eados review` recommends and never merges (ADR-0014), `lesson_sweep` prints drafts
and never writes the ledger. `/eados upgrade` is that same shape applied to the factory→consumer
axis. Per ADR-0019 §3, admitting a new cross-cutting member takes an ADR; this addendum is that
record.

### The open questions, resolved

1. **Where does the delta come from?** The released `CHANGELOG.md` — data the release process
   already maintains under the `version-lockstep` gate — **not** a curated `upgrades.yaml`. A
   curated register would have to be back-filled across twelve releases and would rot silently the
   first time someone forgot it; the changelog cannot rot without the release itself being wrong.
   The consequence class is taken from the **Keep a Changelog section heading** (`Security` /
   `Fixed` / `Added` / `Changed` / `Deprecated`), which is data, and refined to `governance` only
   from **paths the entry itself names**. Prose is not mined for a class it does not state.
2. **Does the generated repo carry the command?** No — it runs **from the factory against a repo
   path**. Rendering it into every new repo would pin each consumer to the logic that shipped with
   *their* version, which is the staleness the command exists to cure. The generated `AGENTS.md`
   carries a **pointer** instead. (The factory's own `CHANGELOG.md` is `export-ignore`d from the
   bundle, so a bundle-only install has no local delta to read; the command fetches it via `gh` and
   degrades to a stated skip when it cannot.)
3. **Semver is not a consequence class.** A MINOR bump carries both a security fix and a README
   tweak. Classifying by section and by named surface answers *should I care*; the version number
   does not.

### Consequences

- A new cross-cutting command, `/eados upgrade` — advisory, **read-only**, non-state-advancing;
  registered in `orchestrator/commands/README.md` with its adapter (ADR-0019 class 4).
- `templates/AGENTS.md.tmpl` gains one line under the provenance stamp telling a maintainer the
  channel exists and that it will never rewrite their repo.
- The write boundary is enforced by a test that runs the command against a scratch tree and
  asserts the tree is byte-identical afterwards — the check that would actually catch the erosion.
- Still explicitly rejected, and named here so a later reader does not re-litigate it as an
  oversight: applying changes, generating patches, three-way merges, and any automated
  re-rendering of a generated repository.
