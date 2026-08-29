# ADR-0009: CI supply-chain pinning policy

## Status

Accepted

## Context

The audit flagged the factory's CI supply chain. EADOS's own workflow, the workflow templates it
renders, and several language profiles referenced third-party GitHub Actions by *movable* refs:

- floating tags (`actions/checkout@v6`, `softprops/action-gh-release@v2`, `actions/setup-*@vN`),
- and — worse, non-reproducible by definition — `@latest` (`lukka/get-cmake@latest`) and
  `go install …@latest` tool fetches.

`pip install pyyaml` in EADOS's own CI was unpinned. A moved tag or a compromised release runs
attacker-controlled code; the release workflow runs with `contents: write`. Because EADOS emits
these patterns into every generated repository, the weakness multiplies downstream.

Two facts shape the policy. First, the generated repos already ship a Dependabot config for the
`github-actions` ecosystem, which keeps version-tagged refs current and can bump SHA pins
(it reads the `# vX.Y.Z` trailing comment). Second, `dtolnay/rust-toolchain@stable|nightly|master`
is **not** a version pin — that action uses its git ref to *select the Rust channel*, so pinning
it to a SHA would break it.

## Decision

A tiered policy, by who authors the workflow and by reproducibility:

1. **EADOS-authored workflow surfaces are SHA-pinned**: `.github/workflows/ci.yml` (the factory's
   own CI) and the rendered baseline templates `ci.yml.tmpl` / `release.yml.tmpl`. Each pin
   carries a `# vX.Y.Z` comment so Dependabot can propose bumps. Pins target the latest patch of
   the major each file already used (no silent major bumps): checkout `v6.0.3`,
   setup-python `v5.6.0`, action-gh-release `v2.6.2`.
2. **`@latest` / floating refs are prohibited everywhere.** `lukka/get-cmake@latest` →
   SHA-pinned `v4.3.3` (the action has no stable major tag to ride); `go install …@latest` →
   pinned tool versions (`gofumpt@v0.10.0`, `govulncheck@v1.4.0`).
3. **Language-ecosystem actions inside profiles stay version-tag-pinned** (e.g.
   `actions/setup-go@v5`, `actions/setup-java@v4`, `golangci/golangci-lint-action@v6`) and are
   managed by the shipped Dependabot config. This is a deliberate, documented choice — not an
   oversight — trading a marginal hardening gain for far lower factory maintenance, and it keeps
   the per-language matrix legible. `dtolnay/rust-toolchain@<channel>` is left untouched by design.
4. **The pinned CI dependency is pinned + hashed**: PyYAML moves to
   `.eados-core/tools/requirements-ci.txt` (`pyyaml==6.0.3` with `--require-hashes`), installed via
   `pip install --require-hashes -r …`. PyYAML remains CI-only; the rendering path stays
   standard-library-only.
5. **EADOS gains its own `.github/dependabot.yml`** (`github-actions` + `pip`) so the new SHA pins
   and the hashed requirement are actually bumped — SHA-pinning without an update mechanism rots.

## Consequences

- A moved tag or yanked release can no longer silently change what EADOS's CI or a generated
  repo's baseline workflow executes; bumps arrive as reviewable Dependabot PRs.
- The render-smoke output is unchanged in structure (39 templates); profile CI fragments still
  parse (the emitted-YAML gate covers them). The reference render stays byte-stable except for
  the intended get-cmake pin.
- Profiles remain readable and low-maintenance; the SHA-pin discipline is concentrated where EADOS
  is the author and the blast radius (a `contents: write` release job) is highest.
- Future work, if desired: extend SHA-pinning into the per-language profiles, and add per-wheel
  hash pinning for additional Python tools — both are incremental on this foundation.

## Addendum (2026-06-18)

A later audit found two drift gaps in this policy as implemented:

- **The literal pins in Decision §1 are point-in-time.** The factory's own
  `.github/workflows/ci.yml` has since been bumped by Dependabot (e.g. `actions/setup-python`
  v5.6.0 → v6.2.0) while the rendered templates were not. Dependabot's `github-actions`
  ecosystem only scans real workflow files — never the `.tmpl` copies, nor the YAML fragments
  embedded in language profiles — so the template pins are **not** kept current by the factory's
  Dependabot (contrary to the spirit of §5) and must be maintained deliberately.
- **The templates had pinned `actions/checkout` to the annotated-tag-object SHA** rather than
  the commit SHA the factory CI uses, so the two referenced `v6.0.3` by different object SHAs.

Both were reconciled in PR #11: the templates were re-pinned in lockstep with the factory CI,
and an `action-pins` gate was added to `tools/eados_lint.py` that fails if a SHA-pinned action
shared by the factory CI and the workflow templates diverges. **The specific version numbers in
§1 are illustrative of the original decision, not the current pins — the `action-pins` gate, not
this prose, is now the source of truth for factory/template parity.**

## Addendum (2026-06-27)

The 2026-06-18 addendum noted the template pins "must be maintained deliberately" after each
Dependabot `github-actions` bump (Dependabot never scans the `.tmpl` copies). `tools/sync_action_pins.py`
now **automates** that maintenance: `--fix` rewrites every template pin to the factory CI's pin for
the same action — the inverse of the `action-pins` gate, reusing the gate's regex so the two cannot
disagree — turning a hand-edit into one deterministic command (documented in
[`maintenance/stay-current.md`](../../maintenance/stay-current.md); covered by
`tools/tests/test_sync_action_pins.py`). It only copies a SHA the factory CI already trusts; it never
resolves a tag itself. Hands-off CI auto-remediation on Dependabot PRs (true zero-touch) shipped
alongside the tool as [ADR-0013](0013-dependabot-action-pin-auto-remediation.md)
(`.github/workflows/dependabot-pin-sync.yml`).

## Addendum (2026-06-28)

A post-v2.3.0 re-audit re-flagged this surface from the opposite direction: every
`orchestrator/profiles/*.yaml` references its GitHub Actions by **floating tag**
(`actions/checkout@v6`, `astral-sh/setup-uv@v3`, `dtolnay/rust-toolchain@master`) while the factory
SHA-pins its own workflows — an apparent inconsistency between the core CI and the generated-repo CI.
It is **not** a design gap: it is precisely the tiered policy **Decision §3** already records
(language-ecosystem actions in profiles stay version-tag-pinned, Dependabot-managed). Tracked as
issue #132 and resolved by **reaffirming §3**, not changing it — an apparent inconsistency surfaced
on re-audit, not an actual gap. Two operating facts reinforce (not weaken) the trade-off:

- **The factory maintains only the pins it itself uses.** Its `.github/workflows/ci.yml` references
  just `actions/checkout` and `actions/setup-python`, so those are the only first-party SHAs it
  holds, and `sync_action_pins.py` only ever copies a SHA the factory CI already trusts. The
  first-party `actions/setup-go` / `setup-java` / `setup-node`, etc. live **only** in profiles;
  SHA-pinning them would make the factory begin maintaining pins for actions it does not otherwise
  use — the per-ecosystem maintenance §3 deliberately declined.
- **Dependabot does not scan profiles** (see the 2026-06-18 addendum: it scans real workflow files,
  never `.tmpl` copies nor the YAML fragments embedded in profiles). A SHA pinned *inside a profile*
  would therefore have **no refresh mechanism in the factory** and would rot. A version tag does
  not — and, crucially, the **generated** repo's own Dependabot *does* scan its rendered `ci.yml`,
  so downstream the version refs are kept current regardless of how the factory expressed them.

This is exactly the trust-domain split the design intends: the **core** domain (the factory CI and
the `ci.yml.tmpl` / `release.yml.tmpl` baselines it authors) is SHA-pinned per §1; the **consumer**
domain (per-language profile fragments) is tag-pinned per §3 and refreshed by each generated repo's
Dependabot. A hybrid that SHA-pinned first-party actions *inside profiles* was considered and
**rejected**: it would supersede §3 to buy a marginal hardening gain while reintroducing the
unmaintainable, factory-side pin drift §3 exists to avoid. No structural, renderer, or gate change —
this entry is the record, and #132 is closed by it.

## Addendum (2026-07-27) — the version comment must be TRUE, not merely present (#312)

**Status:** Accepted · **Deciders:** Maintainer, Enterprise Project Architect · **Related:** #309,
#310 (the incident), #312, ADR-0013, `tools/eados_lint.py` (`pin-label-truth`).

### What this adds

The Decision above mandates that every SHA pin **carries** a `# vX.Y.Z` comment, and names its two
consumers: the `action-pins` gate reads it, and Dependabot reads it to propose bumps. It never
requires that comment to be **true** of the SHA it labels. Per L-0004 this ADR was checked first for
an existing decision on the question; presence is decided here, truthfulness is not. A gap, not a
rediscovered trade-off.

On **2026-07-26** the gap was exercised. Merging `main` into Dependabot branch #309 resolved two
lines of `.github/workflows/ci.yml` to `main`'s SHA while keeping the branch's version comment,
landing the **v7.0.0** commit under a `# v7.0.1` label:

```yaml
- uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.1
#                        ^ this is the v7.0.0 commit
```

`main` went red — but **only** because the mangling was non-uniform, so `action-pins` saw the
cross-file disagreement with the workflow templates. Reproduced during #312: applying the same wrong
SHA *uniformly* across `ci.yml` and all three workflow templates yields **zero** `action-pins`
findings. The repository would have carried a pin claiming a version it did not have, green.

### Decision

A pin's version comment is **load-bearing metadata, and is now enforced as such.** The
`pin-label-truth` self-lint resolves each `# vX.Y.Z` in the SHA-pinned workflows against the
upstream tag and fails when it does not name the pinned commit.

- **The SHA remains the security boundary; the label remains the audit aid.** This addendum does not
  elevate the label — it stops the label from lying, which is the property that lets a human, and a
  bot, tell *which* release the boundary corresponds to. To a reviewer reading #309's diff, both
  sides said "v7.0.1".
- **Scope is unchanged from §1/§3.** Only fully SHA-pinned `uses:` lines are governed. A profile's
  floating `@v6` has no SHA to contradict and stays tag-pinned by design — §3 and its 2026-06-28
  addendum are untouched.
- **Annotated tags are dereferenced** to the commit they point at. A gate that failed every
  annotated tag would be a gate people switch off.

### A network-dependent gate, and the posture it takes

This is the factory's **first** lint check that needs the network, so the posture is recorded rather
than left to the implementation:

- **Unreachable upstream is never a failure.** A gate that turns red when the network is down trains
  people to ignore it, and an ignored gate is not a gate.
- **Unreachable upstream is never a silent pass either.** The run states which pins it could not
  vouch for, through a reporting channel added for the purpose, so an `OK` cannot imply a
  verification that did not happen (L-0006). Both halves are required; either alone is worse than
  the other's absence.
- **The cache is a memo, not an authority.** Resolutions are memoised with the date they were read
  and expire; past the TTL upstream is asked again, and a stale entry answers only when the network
  fails — flagged as not re-verified. A cache trusted forever would rebuild this ADR's defect one
  level up: a recorded claim nobody re-checks.

### The remedy is toward upstream, not toward the factory

Recorded because the obvious fix was the wrong one. `sync_action_pins.py --fix` (ADR-0013) copies
the **factory CI's** SHA into the **templates**. Run against the #310 tree it would have propagated
the v7.0.0 commit into all four template pins under a `v7.0.1` label — turning the gate green over a
*uniformly incorrect* pin set, inherited by every repository generated from those templates. Drift
between a pin and its label is resolved toward the **upstream tag**; `--fix` resolves toward the
factory's current state, which is only correct when the factory is right. Teaching `sync_action_pins`
to resolve tags itself was considered and **declined**: it is documented as a copier that never
resolves a tag to a SHA, and that property is what makes it deterministic. The failing gate names
the true upstream SHA; a human applies it. Also recorded as lesson **L-0011**.
