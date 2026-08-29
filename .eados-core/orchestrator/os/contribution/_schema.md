# `contribution.yaml` — schema

The **inbound-contribution review policy** as data: who counts as the owner, the trust tiers, the
checks every inbound PR must pass, the disposition + label vocabulary the reviewer may recommend,
and the load-bearing escalation (an external fork touching an owned path goes to a human). It
encodes the practice the maintainer already applies by hand to external PRs (verify the change, not
the person; honor a good idea via co-author + an in-house re-implementation; the human posts the
close — the #94 episode) so the `contribution-reviewer` role (M8 8.2) and `pr_review.py` (M8 8.3)
read one source of truth instead of hardcoding it.

`eados_lint` (`os-spec-completeness`) requires the instance to define every top-level key below;
`data-file-validity` requires it to parse; `cross-spec-consistency` resolves its role + disposition
cross-references.

## Required structure

```yaml
version:          # integer schema version
owner_identity:   # where "owned" comes from (CODEOWNERS, with a manifest fallback)
trust_tiers:      # the authorship tiers, least -> most scrutiny
required_checks:  # the checks every inbound PR is evaluated against
dispositions:     # the recommendations the reviewer may draft (id + label [+ requires])
escalation:       # the external-fork-touches-owned-path -> human rule
boundary:         # recommends-only; the human disposes / closes
courtesy:         # always-thank + no-auto-accept + never-merge-non-owner-commits (the #94 principle)
```

## Item shapes (consumed by `pr_review.py`, M8 8.3)

- **`owner_identity`** — `{ source, manifest_fallback }`. `source` is the authoritative owner record
  (`CODEOWNERS`); `manifest_fallback` is the `project.yaml` path used when it is absent.
- **`trust_tiers`** — list of `{ id, scrutiny }`, least → most scrutiny. `id` ∈
  `owner | collaborator | external-fork`; `scrutiny` ∈ `standard | high`. Scrutiny attaches to the
  diff + provenance, never to the author (the #94 principle).
- **`required_checks`** — the check ids an inbound PR is evaluated against (`ci-green`,
  `provenance-clear`, `no-added-secrets`, `scope-matches-intent`, `gate-coverage-holds`). They inform
  the recommendation; they are not a merge gate — a non-owner's commits are never merged regardless
  (see `courtesy.merge_nonowner_commits`).
- **`dispositions`** — list of `{ id, label, requires? }` — the three triage outcomes for a non-owner
  PR: `re-implement-in-house` (adopt the idea our way), `close-with-thanks` (decline), `needs-maintainer`
  (escalate). The reviewer **recommends** one; the `label` is what `/eados review` (M8 8.4) drafts onto
  the PR. Drafts only — never an approval or a merge. `requires` lists the courtesy steps a disposition
  entails; for `re-implement-in-house` the full B2 ritual — `reimplement-ourselves`, `co-author-credit`,
  `rationale-comment` (explain on the contributor's PR **why** we re-implemented), `thank-then-close`
  (the human closes).
- **`escalation`** — `{ on, decider, disposition }`. `decider` resolves to an `authority.yaml` role
  or the `human-owner` terminal; `disposition` must be one of `dispositions`.
- **`boundary`** — `{ recommends_only, closes_by }`. Restates `AGENTS.md` §6 as data.
- **`courtesy`** — `{ always_thank, acceptance_requires_reasoning, merge_nonowner_commits, adopt_via }`.
  Every non-owner disposition thanks the contributor; acceptance is never silent/auto (a recommendation
  always carries its rationale, and the human disposes); `merge_nonowner_commits: false` means a
  non-owner's commits are never merged; `adopt_via` names the disposition (`re-implement-in-house`) that
  is the only way a non-owner change enters the tree.

## Invariants

- `boundary.recommends_only` is `true` and `escalation.decider` terminates at the human: the
  reviewer **drafts and recommends; it never merges or closes** (`git.yaml` `pr.merged_by: human`).
- An `external-fork` PR touching an owned path always escalates to a human (`needs-maintainer`) —
  it is never auto-disposed.
- Trust gates the *scrutiny level*, not whether we engage: a good idea is adopted no matter who sent
  it (the change is judged, not the person).
- **No auto-accept.** A non-owner change is never accepted silently
  (`courtesy.acceptance_requires_reasoning`); the recommendation always carries its reasoning and the
  human disposes.
- **Never merge a non-owner's commits.** `courtesy.merge_nonowner_commits` is `false`: a non-owner
  change enters the tree only via `re-implement-in-house` — we author it ourselves and **co-author**
  the contributor (co-author + a rationale comment on their PR + thanks; the human closes), so
  provenance stays 100% in-house. **Every** non-owner disposition thanks the contributor
  (`courtesy.always_thank`).

## Optional: `examples:` — the adopt/decline/escalate call as data (#224)

An **optional** top-level `examples:` block turns the disposition call from prose judgment into a
few-shot policy surface. It is *not* a required key (`os-spec-completeness` does not demand it); when
present, `eados_lint`'s `examples` check validates its **shape** — never that the reviewer obeyed it,
exactly like the lessons ledger.

```yaml
examples:
  verdicts: [re-implement-in-house, close-with-thanks, needs-maintainer]  # >= 2; here, the disposition ids
  cases:
    - input:   # one line — the situation
      verdict: # one of `verdicts`
      why:     # one line
```

Shape rules: `verdicts` lists ≥ 2 allowed verdicts (for this spec, they are the `dispositions` ids —
so the examples stay congruent with the vocabulary they illustrate); every case carries a non-empty
`input` + `verdict` + `why`; and the block covers **≥ 2 verdicts with ≥ 2 cases each** (a genuine
decision surface — ≥ 2 adopt + ≥ 2 decline, not a single worked path). The same block convention is
used by the interview (`questionnaire.yaml`, ask/default) and the learning loop
(`learning/scope-examples.yaml`, apply/skip).
