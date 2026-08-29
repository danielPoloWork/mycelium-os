# `/eados review <PR#>` — inbound-contribution review (recommends; never merges)

The [`contribution-reviewer`](../../agent/contribution-reviewer.md)'s procedure as a command:
evaluate a pull request — especially from a **non-owner** — against the inbound-contribution policy
and draft a **review + a recommended disposition** for the human. Cross-cutting (run it in any
phase, like `/eados status`); it is not a phase transition. It **reports and recommends — it never
approves, merges, or closes** (`AGENTS.md` §6; `git.yaml` `pr.merged_by: human`).

## Procedure

1. **Evaluate** — run the deterministic evaluator:
   ```bash
   python .eados-core/tools/pr_review.py --pr <PR#> [--repo OWNER/REPO] [--domain D] [--json]
   ```
   It classifies the author's **trust tier**, runs the policy `required_checks`, composes the
   **authority** (owned-path) and **risk** (security / size / blast) lenses, and prints a structured
   report with a **recommended disposition**. It reads
   [`os/contribution/contribution.yaml`](../os/contribution/contribution.yaml) as data and degrades
   cleanly offline (no `gh` → it SKIPs, exit 2).
2. **Deepen when it matters** — when the evaluator flags an **owned-path touch** or a **REQUIRED**
   risk score, invoke the [`security-auditor`](../../agent/security-auditor.md) (secrets,
   supply-chain, dangerous CI triggers) and the [`reviewer`](../../agent/reviewer.md) (correctness,
   scope, quality bar) for the deep findings the evaluator only points at.
3. **Draft** — draft the review **comment** + the `review:<disposition>` **label** on the PR via `gh`
   (`gh pr comment`, `gh pr edit --add-label`). **Draft only** — never `gh pr review --approve`,
   never `gh pr merge`.
4. **Recommend a disposition** (the vocabulary + rules live in `contribution.yaml`):
   - **We never merge a non-owner's commits.** A wanted change is **adopted via
     `re-implement-in-house`** — author it ourselves to our standard, **co-author** the contributor,
     leave a **rationale comment** on their PR, and **thank-then-close** (the human closes).
   - Not pursuing it → **`close-with-thanks`** (a rationale comment + thanks; the human closes).
   - An owned path / a security gate → **`needs-maintainer`** (escalate to the human decider).
   - **Always thank** the contributor; **never auto-accept** — the recommendation carries its
     reasoning, and the human disposes.

## Boundary

Drafts and recommends only. The human requests-changes / approves / merges / **closes**. A
non-owner's commits are **never merged** — a good idea enters the tree solely as our in-house
re-implementation with co-author credit, so provenance stays in-house
(`courtesy.merge_nonowner_commits: false`). An **owner-authored** PR is not an inbound contribution —
there is nothing here to triage.

**Calibrate the recommendation** (`AGENTS.md` §10): the disposition carries a confidence tag earned
by evidence (the tier and risk calls cite what they rest on), and a recommendation against the
contributor's ask leads with the dissent template — position / alternative / risk — while still
thanking them.
