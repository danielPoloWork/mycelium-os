# 2026-08-30 — brand assets and README redesign (roadmap 2.12)

- **Session scope:** roadmap item 2.12 — vendor the legacy brand assets and rebuild the
  root README on the legacy skeleton with v1-true content (RFC-0001, D-028).
- **PR:** #25 (`docs/brand-and-readme`), one item, one PR. Follows #24 (2.11), merged.

## What got done

- `docs/assets/brand/` — banner, icon, and logo PNGs vendored from
  `.mycelium-os-legacy/.bootstrap-os/.assets/`, with a README recording their provenance,
  intended use, and the trademark status (no search run; that is 6.5).
- Root `README.md` rebuilt on the legacy skeleton — centred banner, badge row, language
  selector, *Inspiration & Origins* credit — with content that describes the v1 design
  rather than the superseded one.
- The legacy `architecture.svg` / `architecture-mycelium.svg` are **not** vendored, per the
  item: they depict the dual-layer wiki/machine design that RFC-0001 supersedes. Recorded
  in the brand README so nobody re-salvages them by accident.

## Judgment calls worth recording

- **The logo carries a superseded tagline.** `mycelium-os-logo.png` renders "Semantic
  Cognitive Knowledge Filesystem Operating System" — the legacy positioning, contradicted
  by D-001 (a knowledge compiler and serving layer, not a cognitive OS). It is vendored
  because it is the only portrait lockup that exists, but the brand README marks it
  unusable where the tagline is legible, and the root README uses the tagline-free banner.
- **Badges are limited to signals that are actually wired.** The legacy row advertised
  Discord, Codecov, and Read the Docs. Coverage and docs are not wired (the docs site is
  6.2), and the Discord invite is an external link nobody verified — carrying any of them
  would be a badge that lies. Kept: Status (the lint reads it), CI, Release, License,
  Security Policy, Python version. The Discord invite is an owner call, not an agent's.
- **The language selector ships as labels, not links.** `docs/i18n/` is 2.13's to create;
  linking to it now would put dead links in the front door — the exact failure L-0002
  warns about. The selector renders "English (canonical) · Italiano · 中文 · 日本語 —
  *translations land with roadmap 2.13*", and 2.13 turns the labels into links.
- **Positioning stays honest.** The comparison table's last row says quality is measured
  against a judged case set with the agent's own `grep` as the baseline to beat (D-010),
  and the prose says plainly that the harness is built to report a loss. Overselling in the
  README would contradict the risk clause the project accepted in RFC-0001.

## Verification beyond the lint

Every documented command was run end-to-end in a scratch directory rather than trusted:
`mycelium init` → `mycelium build` (2 documents, 22 chunks, 125 ms) → `mycelium search`,
which returned `mycelium://` citations with line ranges — including a hit on the README's
own "Try it" section, since the README was one of the two documents compiled. A script
checked that every local link and image path in the README resolves.

## Where the project stands

- Milestone 2: 2.1–2.12 ✅ · **2.13 open** (the last item of the walking skeleton).
- Gates green locally: `python tools/consistency_lint.py`, plus the full suite unchanged
  (this item touches documentation and assets only — no source change).

## How the next session resumes

- Wait for PR #25 to merge, then start **2.13** — enable the docs-i18n subsystem, structure
  only: `capabilities.i18n` on with targets it / zh-Hans / ja, `docs/i18n/` index +
  `translation-status.md` (all pages pending), and `i18n_enabled: True` in the
  consistency-lint CONFIG. Flip the flag and ship the artifacts in the same PR (L-0002).
- 2.13 should also turn this README's language-selector labels into links, since it is the
  item that creates their targets. Note that the lint's `i18n-freshness` check compares a
  translation's recorded source commit against `HEAD`, so an entry may only claim
  `translated` once a real translation exists — "all pages pending" is the correct initial
  state.
