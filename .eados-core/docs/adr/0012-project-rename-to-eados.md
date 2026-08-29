# ADR-0012: Rename EAAO → EADOS (repo, path, and bundle migration)

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Owner (`@danielPoloWork`), Enterprise Project Architect
- **Related:** ADR-0011 (the pivot that motivates the new name), `.gitattributes` (bundle),
  `docs/i18n/translation-status.md` (i18n hash), `tools/render.py` (the dev sentinel),
  `.github/workflows/release.yml` (the bundle asset name)

## Context

ADR-0011 expands the project's scope from an *Architecture Orchestrator* to a *Delivery
Operating System*. The name must match the ambition. The old identity is pervasive: the token
`eaao` and the proper noun appeared in **482 places across 73 files**, plus the `.eaao-core/`
factory folder (on which the tooling self-locates), the `.eaao-dev` dev-repo sentinel, the
`eaao_lint.py` self-lint, the GitHub repository name, and the release-bundle asset name.

Two earlier options were considered and dropped: keeping `eaao` as the core name with `eados`
only as a command surface (superseded by the owner's decision to rebrand fully now), and
deferring the rename until after the design package (rejected — it would write the entire RFC/
spec package twice).

## Decision

Perform a single, mechanical, repo-wide rename, as its own focused PR **before** the design
package, so every new artifact is born EADOS:

- **Names:** full name → "Enterprise Agentic Delivery Operating System"; acronym `EAAO` →
  `EADOS`; token `eaao` → `eados`. Generic English words ("orchestrator", "factory") are left
  untouched — only the proper noun and the token change.
- **Paths & assets:** `.eaao-core/` → `.eados-core/`; `.eaao-dev` → `.eados-dev`; `eaao_lint.py`
  → `eados_lint.py`; bundle `pgs-eaao-bundle.*` → `pgs-eados-bundle.*`; repo `pgs-eaao` →
  `pgs-eados`; command surface `/eados`.
- **Tooling is path-stable.** `render.py` / `eados_lint.py` compute `ROOT` as `../..` from the
  tool file, so the directory rename needs no logic change beyond the swept string constants
  (the `.eados-dev` sentinel check and help text).
- **i18n freshness (ADR-0010).** Renaming the English source `README.md` changes its content
  hash; both `translation-status.md` rows were updated from `69353c8a8af7` to the new hash, and
  the `zh-Hans` / `ja` translations received the same mechanical token sweep.
- **History.** Historical ADRs and the CHANGELOG had their path references and the proper noun
  swept mechanically; the recorded **decisions are unchanged** — this is a token rename, not a
  rewrite.

## External / human steps (the agent cannot perform these)

- **Rename the GitHub repository** `pgs-eaao` → `pgs-eados`. GitHub auto-redirects the old repo
  URL and clone paths, so existing links keep working.
- **Rename the local working folder** to `pgs-eados` (renaming it mid-session would break the
  tool's working directory).
- Historical release assets keep their `pgs-eaao-bundle.*` names; only **new** releases publish
  `pgs-eados-bundle.*`, so the `…/releases/latest/download/pgs-eados-bundle.tar.gz` link becomes
  stable from the next release on.

## Consequences

- **BREAKING for consumers** who vendored the bundle: the `.eados-core/` path and the bundle
  asset name change. Flagged in the CHANGELOG. Under SemVer this warrants a **major** bump at the
  next release — a decision left to the owner / release-manager (this PR does not cut a release).
- A one-time external rename on GitHub; all gates (`eados_lint`, render-smoke, `tools/tests/`)
  pass post-rename.
- This ADR (0012) necessarily names the old `EAAO` / `.eaao-core` identity to document the
  migration — the one intentional place the old token survives, as historical record.

## References

- ADR-0010 (i18n content-hash freshness), ADR-0011 (the pivot), `.gitattributes`,
  `docs/i18n/translation-status.md`, `tools/render.py`, `.github/workflows/release.yml`.
