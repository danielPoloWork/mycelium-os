# 2026-09-14 — the rungs that were not there (roadmap 6.6)

- **Session scope:** roadmap 6.6, the contribution ladder — good-first-issues, CODEOWNERS,
  release automation, signed artifacts + SBOM.
- **PR:** `feat/contribution-ladder`. Follows #148 (6.11, the publish pipeline).
- **Reserved issues filed:** #149, #150, #151 — the first three rungs of the ladder, all
  unassigned and held for a first-time contributor.
- **Milestone 6:** 6.1, 6.2, 6.11 and now 6.6 delivered. Open: 6.3, 6.4, 6.5, 6.7–6.10,
  6.12, 6.13.
- **Decision it records:**
  [ADR-0117](../../../adr/0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md).

## The survey was the finding

The item names four rungs and three of them had something in place, so the work began by
asking what each one actually did rather than by building. CODEOWNERS existed as one line.
Release automation existed — `release.yml` drafts, `publish.yml` uploads. Signing and an
SBOM did not exist at all, and `packaging.md`'s last line said *"prefer a reproducible build
and attach provenance/SBOM where the ecosystem supports it"*, which is an intention with
nothing behind it.

Then I asked GitHub instead of reading `github-setup.md`, and **three of its six one-time
steps had never been installed**:

- `main` has no branch protection and no ruleset. AGENTS.md §6.1 says agents never push
  directly to it and §3 of the setup doc says the ruleset *"enforces it server-side"* — it
  enforces nothing, and the rule was already broken once at roadmap 3.7, undone with an
  authorised force-push.
- Private vulnerability reporting is **off**, while `SECURITY.md` and the issue chooser both
  send a reporter to the advisory form. With the setting off an outside reporter cannot
  submit it, and their remaining route is the public tracker — the exact outcome a
  disclosure policy exists to prevent.
- `test` and `build` carry colours the manifest does not declare, and `good first issue` and
  `help wanted` were not in the manifest at all, though both exist on GitHub.

This is the third time this repository has met the same shape: a document that records what
somebody did once, with nothing that says which of it is still true. The labels were partial
until 2026-09-11 and `gh pr create --label fix` found it. So the answer is a checker —
`tools/check_repo_settings.py` — which asks GitHub, prints the install command beside each
absent step, and **never changes one**. Those are the owner's repository settings, the same
boundary 6.11 drew around the index side.

One more thing the survey turned up, filed rather than fixed: **GitHub Pages is not
configured and nothing deploys `docs-site/`**. 6.2 built the site and CI checks it, so the
content is real and has no reader — which also blocks this ladder's second rung, since
"fix the documentation you were reading" currently means reading raw Markdown. It needs a
decision about where Pages serves from and whether the site tracks `main` or the tag, so it
is **6.14** rather than a step in this PR.

## Two decisions worth keeping

**Signing and the SBOM are built now, though the spec times them "from 1.0".** The same
argument ADR-0114 made for the compatibility promise, and stronger here: a release that ships
unsigned cannot be signed afterwards, so deferring to Milestone 7 would leave every release
between here and there unverifiable. And 6.11 named *"built and unproven at its last inch"*
as its own residual risk; this is what not repeating that looks like.

**`good first issue` means reserved, and AGENTS.md is where that becomes true.** This was the
rung I nearly built as theatre. Filing welcoming issues into a repository whose pipeline
closed 43 items in five days would have produced an invitation withdrawn before anyone could
accept it. The label is only honest with a rule behind it, so §6.1 now forbids an agent from
taking one.

## What the SBOM tool caught about itself

Two things, both from checking output rather than trusting the generator.

The first run wrote a root component with **no version**: `version` is `dynamic` in
`pyproject.toml`, hatch reads it from `__about__.py`, and the generator reads PEP 621
metadata statically. An SBOM that cannot name its own release fails the same test the tool
applies to every other component, so it is stamped and asserted.

And the design point the whole tool turns on: an SBOM of this repository's `.venv` would
inventory 162 distributions, of which four are the runtime closure, and tell a consumer they
are running pytest, ruff and hatch. So the wheel goes into an empty environment and the tool
**fails if a development tool appears in the result** — the property the clean environment
buys, asserted rather than assumed.

## The mistake the ladder caught

The SBOM generator first shipped as a `sbom` dependency group. The reasoning was careful and
had a precedent: ADR-0098 keeps `typst` out of `dev` because a 62 MB typesetter should not
ride in every matrix cell, so I measured the marginal cost of `cyclonedx-bom` — 18 packages
against 162 already installed — and put it in a group of its own on the same argument.

Then `python tools/verify.py` derived **`full`** mode, because `.github/CODEOWNERS` counts as
changing the verification itself, and `tools/build_ingested_corpus.py --check` failed. Five
HTML documents in the vendored ingested corpus projected differently. Nothing in `src/` had
changed.

`cyclonedx-bom` pulls `chardet`. `bs4.dammit` binds `chardet_module` to it whenever it is
importable and uses it to guess a document's encoding, and the HTML lane goes through that
path. Uninstalling that one package and re-running the check turned it green, which is the
whole proof.

So a *dependency group for a tool* changed what the compiler produces. The generator now runs
through `uv tool run`, in an environment of its own, declared in none of ours — and the rule
that replaces the precedent I reasoned from is stronger than it:

> A tool that is not part of this product must not be resolvable alongside it. What is
> importable is an input to the compiler, whether or not anything imports it on purpose.

The difference from `render` is worth keeping: `typst` is a renderer a tool *invokes*, and
nothing it brings is opportunistically imported. The precedent was about **cost**; this is
about **reachability**, and I read the first as covering the second.

The instance is fixed; the class is not, and it is filed as **6.15**. Nothing pins which
encoding detector the HTML parser ends up using, `charset-normalizer` is already installed
and disagrees with `chardet` by design, and `--check` detects the divergence after the fact
without being able to tell an environment difference from a parser change.

## Lesson

Two, and the second cost more than the first.

A setup document is a list of things somebody did once, and nothing in it says which are
still true. Three of six had quietly never been done, and the two that mattered protect other
people: the branch anyone could push to, and the disclosure channel an outside reporter could
not use. Ask the system, not the document — and leave behind the command that asks.

And: a dependency you add for a *tool* is still in the environment the product runs in. The
measurement I took — marginal package count — was the right measurement for the precedent I
was following and the wrong question entirely. What mattered was not how many packages
arrived but whether any of them is something the compiler will pick up if it is there.
