# 2026-10-06 — the board read the evidence and said conditional go (roadmap 7.12)

- **Session scope:** roadmap 7.12 — the architecture review before the v1.0.0 cut is planned,
  re-cut by the maintainer on 2026-10-05 from a ~200-seat vote into an Architecture Review
  Board: 24 named disciplines, severity by impact, an adversarial challenge before any finding
  may block, and a verdict of GO / CONDITIONAL GO / NO-GO in `docs/analysis/`.
- **PR:** `feat/architects-panel-review`, from `ea0d167` (#204).
- **Milestone 7:** 7.12 closed by this PR; the review itself asks the maintainer to re-cut
  Milestone 7 (decision D-01 in the analysis).
- **Record it produces:**
  [`docs/analysis/0002-architecture-review-board-v1-readiness.md`](../../../analysis/0002-architecture-review-board-v1-readiness.md)
  — no ADR, by the analysis directory's own convention: an analysis is evidence plus
  recommendation, never a decision.

## The verdict, in one paragraph

**CONDITIONAL GO.** Fifty-five independent assessments (30 board seats, 25 recovered from the
earlier configuration, same commit) produced 410 findings, every one with a tracked path, a
number, a test or a command behind it; seven triage clerks merged them into 180 clusters and
rejected none; the adversarial pass refuted none outright but cut 23 of 33 standard-tier
severities and re-read two defects as disagreements with recorded decisions. What survives as
release-blocking after 67 challenge verdicts is one P0 (the authored lane follows a junction
out of the repository and pins identity into the outside file, confirmed by both of its
challengers), three consolidated P1 groups (the widened tree-sitter pin, the recovery
commands that wipe a foreign-version store, MCP stdin in the Windows code page), a ledger of
owner actions the repository has reported absent for weeks, and three decisions nobody has
taken — beginning with the exit gate the v1.0.0 tag binds to, which no record states (the
label itself is the owner's recorded correction in ADR-0113; spec 06, `project.yaml` and the
GitHub title are what drifted). Eight more P1 groups were confirmed and judged not to block.

## What the method taught

- **A finding filter that drops nothing is still doing its job.** The mechanical evidence rule
  dropped 0 of 410 findings; the reading rule (the clerks) rejected 0 of 180 clusters. Both
  were designed to catch unsupported criticism, and the reviewers, told the rule in advance,
  wrote none. The adversarial pass is where the record moved: severity, not existence.
- **Convergence predicted nothing about severity.** The most-converged cluster (parser
  libraries outside the build key, 12 seats) was downgraded to P2 by its challenger, who found
  the gap recorded in ADR-0015/ADR-0154 and measured 0 of 326 KIR digests differing across the
  two installed parser majors. The P0 was reached by three seats. The brief's rule — impact,
  never count — was the right one.
- **Two panel configurations, one commit, one call.** The 25 area-lens seats recovered from the
  210-seat run and the 30 discipline seats disagreed on nothing of substance; the clerks'
  49 contradiction notes are about counts and probe thresholds, and the two that mattered
  (whether a stale chunk window reached a released store; whether BUG-0024 is open) were
  settled by the clerk reading `git show <tag>:` and a record's frontmatter.
- **The cost ran on the weekly model allowance, not the five-hour one.** Fifteen frontier seats
  took one five-hour window and 31 points of the weekly frontier allowance; the maintainer
  moved the second fifteen, the clerks and the non-blocking challengers to the standard model
  and kept the frontier for the blockers (option 3, 2026-10-06). A one-shot scheduled task
  resumed the frontier tier at the window reset instead of waiting for a human message.

## What the next session should know

- **Everything the board produced lives outside the tree** under the project's
  `panel-7-12/board/` directory (reviews, clusters, challenge verdicts, the clerk's
  adjudication, the 30 rendered issue drafts) — the analysis quotes the evidence a reader
  needs and names the cluster ids as stable keys. The drafts are opened **one at a time, each
  confirmed by the maintainer** (their instruction of 2026-10-05), in the order of the
  analysis §3.
- **`docs/analysis/` is the maintainer's untracked directory** (`0001`, `README.md`): this PR
  stages `0002` alone by path, and the README's index row is theirs to add.
- **Three records the board corrected on the way**, none silently: the dossier's "two open
  bugs" is one (BUG-0024's record says fixed; the ledger row drifted, in I-24); the board's own
  lead that `setup-python` is tag-pinned "in every job" is 8 of 10 in `ci.yml` plus both
  identity-holding workflows; and the dossier's `adoption_report.py --help` crash reproduces
  only on a real cp1252 console, which is exactly the finding (I-12).
- **7.12's roadmap text still describes the first cut** ("ranked by how many independent
  reviewers reached them"); the delivery note on the item records the re-cut and why.
