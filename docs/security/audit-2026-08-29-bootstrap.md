# Risk register — bootstrap audit (2026-08-29)

- **Auditor:** security-auditor role (EADOS `/eados audit`); structured findings reviewed
  in-session; the owner resolves.
- **Change under audit:** the repository bootstrap — PR #1 (delivery pipeline: factory
  bundle, manifest, RFC-0001, roadmap) + PR #2 (scaffold render: 49 files, ADR-0003,
  Apache-2.0) — 386 paths, ≈ 44 000 lines added since the initial commit.
- **Risk score:** `critical` — factors `security-surface` (`.github/**`, `tools/**`
  matched), `large-change` (≥ 400 lines), `wide-blast-radius` (≥ 3 top-level areas).
  Scorer: `risk_score.py --domain software`; threshold for the mandatory gate: `high` →
  **security-auditor gate REQUIRED and run** (this document + the
  [threat model](threat-model.md) are its output).
- **Traceability:** `traceability.py ROADMAP.md RFC-0001 --links <derived>` → **OK — the
  RFC → milestone → PR → commit → release graph is whole** (links derived from merged
  PRs #1–#2 via `derive_links.py`, not hand-written).
- **Preconditions:** `consistency_lint` → OK; `self_review` → OK on the tracked tree
  (clean worktree of `main`; the 13 archive-only hits — see F4).

## Findings

| # | Severity | Component | Finding · realistic impact | Mitigation · status |
|---|---|---|---|---|
| F1 | **low** (confirmed defect) | `.github/workflows/release.yml` | The `draft-release` job references `matrix.toolchain` but declares no matrix; the expression resolves to `'3.12'` only because an undefined context compares false. Behavior is correct **by accident**; any future edit that renames the guard or adds strictness (actionlint) breaks the release path at tag time — the worst moment. | Fixed in this PR: literal `python-version: '3.12'`. Recorded as [BUG-0001](../bugs/2026/08/BUG-0001-release-workflow-matrix-context.md); factory-level lesson drafted (shared `setup_steps` block injected into a matrix-less job). **fixed** |
| F2 | **medium** | Repository settings (governance / supply chain) | All three merge methods enabled; PRs #1 and #2 landed as **merge commits**, so the verbose-squash-body contract (PR body = permanent commit body) silently did not apply, and no branch protection exists (free-plan private repo — GitHub returns 403 for protection APIs). Impact: policy-vs-reality drift on the audit trail; no mechanical guard against a direct push. | **Squash-only set 2026-08-29** (owner-authorized in-session PATCH; verified `{merge:false, rebase:false, squash:true}`). Remaining: branch protection at public/Pro per docs/workflow/github-setup.md; interim control stays owner-only merge + policy. **half-resolved — protection pending public/Pro** |
| F3 | **low** | `SECURITY.md` (policy) | The reporting channel points at GitHub *private vulnerability reporting*, which is not active on a private free-plan repository (API 404 verified). Today there are no external reporters (private repo), so exposure is nil; at public launch a reporter would find a dead door. | Enable private vulnerability reporting the day the repo goes public (Settings → Security), before any announcement; tracked as part of roadmap 1.8/6.x governance. **open — deferred with trigger** |
| F4 | **info** | Local working copy (`.mycelium-os-legacy/`) | The gitignored legacy archive contains stray placeholders that trip repo-wide scanners (`self_review` reported 13 completeness hits from it). Not part of the tracked tree; can confuse future audits. | Run whole-repo scanners against a clean worktree of `HEAD` (done in this audit); archive stays gitignored. No repo change needed. **noted** |
| F5 | **info** | Dependency surface | No Python dependencies exist yet (build system lands at roadmap 1.1), so the package supply-chain surface is currently nil. When 1.1 lands: `uv` lockfile committed, Dependabot `pip` ecosystem already configured, weekly. Template actions SHA-pinned; profile actions tag-pinned **by decision** (factory ADR-0009 §3, Dependabot-managed) — a decided trade-off, not a gap (lesson L-0004). | Planned controls confirmed present in `dependabot.yml`; nothing to change now. **noted — controls land with 1.1** |

## Verdicts

- **Secret hygiene:** clean — pattern grep over tracked files: no hits; no repository
  secrets configured; local agent settings gitignored. (`certain` — commands in the audit
  session.)
- **Workflow permissions:** least-privilege — ci.yml `contents: read`; release.yml
  `contents: write` scoped to the owner-triggered tag path and drafts only. (`certain` —
  files read.)
- **No vulnerability requiring an advisory.** No draft advisory opened. The one confirmed
  defect (F1/BUG-0001) is not exploitable — it is a latent-breakage risk, fixed here.
- **Migration:** not needed — greenfield repo; `audit → migrate` not proposed. The audit
  stands as the standing pre-release gate; re-run at each release or security-surface
  change (risk_score decides when the deep gate is mandatory).

## Evidence trail

`risk_score.py` (critical/REQUIRED) · `traceability.py --links` (OK) ·
`consistency_lint.py` (OK) · `self_review.py` on clean worktree (OK) · `gh api`
merge-method + protection + private-vuln-reporting probes (F2/F3 evidence) · secret
grep (clean) · workflow file review (F1; permissions) · run record:
`.eados-core/learning/runs/` (phase `audit`, 2026-08-29).
