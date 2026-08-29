# ADR-0014: Inbound-contribution trust model

## Status

Accepted

## Context

EADOS is governed: the agent drafts; the human opens / merges / publishes (`AGENTS.md` §6). But a
pull request can also arrive from a **non-owner** — a collaborator, or an unknown first-time
contributor from a fork. The **#94** episode (an external fork editing the manifest template) showed
the maintainer applying a consistent, unwritten practice by hand: verify the *change*, not the
person; honour a good idea by re-implementing it in-house with co-author credit; the human posts the
close. Nothing encoded that practice, so a reviewer (human or agent) re-derived it each time, and a
consumer's generated repo inherited no inbound-review policy at all.

## Decision

Encode the inbound-contribution practice as **data + a role + a tool + a command + a gate** (M8):

- **Policy as data** — `orchestrator/os/contribution/contribution.yaml` (schema `_schema.md`): the
  owner-identity source (CODEOWNERS + a manifest fallback), the **trust tiers**
  (`owner · collaborator · external-fork`, least → most scrutiny), the **required inbound checks**,
  the **disposition** vocabulary (+ labels), and the load-bearing **escalation** (an external fork
  touching an owned path → a human).
- **The trust principle.** Trust gates the *scrutiny level*, never the *outcome*: a verified external
  change is as welcome as any other — the change is judged, not the author.
- **Never merge a non-owner's commits** (`courtesy.merge_nonowner_commits: false`). A wanted change
  enters the tree **only** as our in-house re-implementation with **co-author credit**
  (`adopt_via: re-implement-in-house`: reimplement-ourselves + co-author-credit + a rationale comment
  on the contributor's PR + thank-then-close), is **declined** via `close-with-thanks`, or is
  **escalated** via `needs-maintainer`. Provenance stays 100% in-house.
- **No auto-accept, always thank** (`courtesy.acceptance_requires_reasoning: true`,
  `always_thank: true`) — a recommendation always carries its reasoning and the human disposes; every
  non-owner disposition thanks the contributor.
- **The role** — `agent/contribution-reviewer.md` + an `authority.yaml` record (engineering pillar,
  `phases: []`, empty `owns`/`may_approve` like `reviewer`): composes `reviewer` + `security-auditor`
  and adds trust classification + the policy checks + triage. It recommends; it never merges/closes.
- **The tool** — `tools/pr_review.py`: classify tier → run the checks → compose `authority_check`
  (owned-path) + `risk_score` (security/size/blast) → a structured report + a recommended
  disposition. Pure core, fixture-tested; a thin `gh` shell that degrades cleanly offline.
- **The command + gate** — `/eados review <PR#>` (cross-cutting, like `/eados status`) drafts the
  review; a `contribution-review` gate in `workflow.yaml` (`required_for: []`, `blocking: false`)
  referenced by `git.yaml`'s `pr.review_gate`, validated by `cross-spec-consistency`.

## Consequences

- The maintainer's #94 practice is now **one source of truth** the role, tool, and command all read —
  not re-derived per PR — and ships to every generated repo in the bundle.
- **Boundary intact.** Everything recommends and drafts; the human requests-changes / approves /
  merges / closes (`git.yaml` `pr.merged_by: human`). The gate is advisory (`blocking: false`) — it
  informs, it never blocks a merge.
- **Provenance is in-house by construction.** Because non-owner commits are never merged, the tree's
  authorship stays the maintainer's, while contributors still get co-author credit + thanks — keeping
  good-faith contributors engaged (the #94 / #96 episodes).
- A non-owner PR touching an owned path always routes to a human; a verified change that does not is
  adopted, declined, or escalated — never silently accepted.
