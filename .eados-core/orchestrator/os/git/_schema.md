# `git.yaml` — schema

The **Git/PR/CI/release policy** as data: branch naming, commit convention, the PR rules
(including the mandatory PR↔RFC↔milestone cross-links that feed the traceability graph), and
the release flow (with the explicit **merge ≠ deploy** boundary). This encodes the rules
`AGENTS.md` §6 states in prose, so the workflow gates can enforce them mechanically.

`eados_lint` (`os-spec-completeness`) requires the instance to define every top-level key
below.

## Required structure

```yaml
version:            # integer schema version
branch_naming:      # pattern + the allowed type vocabulary
commit:             # convention, scopes, one-change-per-PR / one-PR-at-a-time
  squash_body:      # the squash-merge commit carries a verbose body (subject one-liner + PR summary)
pr:                 # who drafts/opens/merges, the body cross-links, the project-board metadata
  metadata:         # GitHub fields set on creation: assignee(owner), one type label, milestone, project-if-present
release:            # SemVer flow, tag flow, the merge!=deploy boundary, delegation flag
traceability:       # the artifact lineage the graph + lint (M3/M4) are built from
```

## Item shapes (runtime-enforced, M3/M4)

- **`branch_naming`** — `{ pattern, types[] }`. `types` is the Conventional-Commit type set.
- **`commit`** — `{ convention, scopes[], subject_max, one_logical_change_per_pr,
  one_pr_at_a_time, one_pr_counts, squash_body{} }`. **`subject_max`** (integer, default 80) caps
  the subject line **the author writes**: squash-merge appends ` (#PR)`, which no author can
  prevent, so `git_check` strips one trailing reference before measuring (#363). It is data
  rather than a constant because it is the one threshold a project might legitimately set for
  itself — and because a number in code cannot be changed by a repo that only vendors the tool. **`one_pr_counts`** (`authored` | `all`, default `authored`)
  says *whose* open PRs `one_pr_at_a_time` counts. The rule exists so an agent does not stack
  work in flight; it was never meant to cap a dependency bot's queue, and counting bots put a
  generated repo in violation of its own policy minutes after bootstrap (#350). Matched on the
  **author type** (`gh` `author.is_bot`), never a login denylist — a list of bot names is a list
  to keep current, and the next bot would be counted until someone remembered it. `squash_body` requires the squash-merge commit (squash is the only merge
  method) to carry a **verbose, professional body**, not a one-line subject collapse:
  `subject` = the Conventional-Commit one-liner (the PR title), `body_from: pull_request` = the
  PR description (context, change, verification) preserved into the merge commit. The repo is
  configured (`github-setup` §1) to take the PR title/body as the squash message, so a structured
  PR body *is* the merge-commit body.
- **`pr`** — `{ draft_by, opened_by, merged_by, merge_method, one_type_label,
  required_crosslinks[], template, review_gate, metadata{} }`. `required_crosslinks` (e.g.
  `[rfc, milestone]`) are the references a PR *body* must carry; the traceability lint fails on a
  missing edge. **`metadata_applies_to`** (`authored` | `all`, default `authored`) scopes the metadata contract
  the same way: a bot cannot assign, cannot set a milestone, and its requested label is dropped
  until the repo's labels are imported, so every required field is unsatisfiable for a dependency
  PR — reporting them `INCOMPLETE` trains maintainers to ignore the check, and a check that is
  routinely ignored has stopped being one (#350). `metadata` is the distinct set of GitHub fields **set on creation** via
  `gh pr create` — `assignee` (the repository **owner**, never `@me`/the drafting actor: EADOS →
  `danielPoloWork`, a generated repo → the manifest owner), `label` (one type label matching the
  lead commit's type, per `one_type_label`), `milestone` (the current open release/roadmap
  milestone), and `project` (the GitHub Project, attached when the repo has one). `review_gate`
  names the cross-cutting inbound-review gate (`contribution-review`) that `/eados review` runs on
  a PR — a recommendation, never a merge (M8).
- **`release`** — `{ scheme, tag_flow, merge_is_not_deploy, tag_by, draft_release_by, publish_by,
  delegation_flag }`. **Carry-through:** the agent always takes a release up to a **draft** —
  `tag_by: agent` creates + pushes the annotated tag, `draft_release_by: agent` opens the GitHub
  Release as a draft (CI drafts it on tag-push in generated repos) — and the human only
  **publishes** (`publish_by: human`, the deliberate checkpoint; `delegation_flag: true` delegates
  the publish too). `merge_is_not_deploy: true` models `merged → tagged/released → deployed` as
  distinct, separately-gated states.
- **`traceability`** — `{ graph, gate }`. `graph` is the lineage string the lint walks.

## Invariants

- `pr.merged_by` and `release.publish_by` are `human` unless `delegation_flag: true`
  (`AGENTS.md` §6 — the agent never merges to the default branch or publishes a release on its
  own authority).
- `pr.required_crosslinks` are the edges the traceability graph (M3/M4) depends on; dropping one
  breaks end-to-end auditability.
