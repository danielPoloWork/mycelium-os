# ADR-0117: Sign and inventory the artifact, and reserve the rung a newcomer stands on

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 06 §4
- **Related:** [ADR-0116](0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md)
  (the publish pipeline this extends, and the no-credential stance it borrows),
  [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (build it before the tag that needs it; the contract paths CODEOWNERS now names),
  [ADR-0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md)
  (the docs and the cookiecutter two rungs of this ladder point at),
  [ADR-0098](0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md) (the `render`
  group, the precedent for keeping a heavy tool out of `dev`),
  [ADR-0059](0059-make-the-plan-one-implementation-too.md) (one implementation, two
  callers — and the exclusion list this adds to),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) (a gate
  that fires on everything selects for being ignored); spec 06 §4 and §Phase 4; D-017,
  D-018; threat model B2; roadmap 3.7, 4.40, 6.6, 6.11, 6.12

## Context

Roadmap 6.6 names four rungs: *good-first-issues, CODEOWNERS, release automation, signed
artifacts + SBOM*. Three of the four had something in place, so the item began by asking
what each of them actually did.

**CODEOWNERS existed** as a single line, `* @danielPoloWork`, with a comment saying to split
it by component as the team grows.

**Release automation existed**: `release.yml` drafts a GitHub Release with the archives
attached (6.11 and BUG-0006 between them), and `publish.yml` uploads over Trusted Publishing.

**Signed artifacts and an SBOM did not exist at all.** `publish.yml` passes
`attestations: true` to the PyPI action, which covers a PyPI upload that has never happened;
nothing signs the GitHub Release assets, and no SBOM is produced anywhere. The last line of
`docs/workflow/packaging.md` read *"Prefer a reproducible build and attach provenance/SBOM
where the ecosystem supports it"* — an intention, in a document, with nothing behind it.

**And the good-first-issues rung ran into a decision already on the record.** This repository
opens no tracking issues: `ROADMAP.md` is the single source of work items, and PRs link to
none. The issue tracker is empty — zero issues, ever.

### What asking GitHub found

`docs/workflow/github-setup.md` writes down six one-time configuration steps. Nothing reads
them back. Asked directly, **three had never been installed**:

| step | documented | actual |
|---|---|---|
| §1 squash-only merges | yes | ✅ installed |
| §2 labels imported from the manifest | yes | ⚠️ `test` and `build` carry colours the manifest does not declare; `good first issue` and `help wanted` exist on GitHub and are **not in the manifest at all** |
| §3 `main` refuses a direct push | yes, with the exact `gh api` call | ❌ **no branch protection, no ruleset** |
| §4 Discussions | yes | ✅ installed |
| §4 private vulnerability reporting | yes ("in the web UI") | ❌ **disabled** |
| §5 a milestone per roadmap milestone | yes | ✅ all seven |

Two of those are defects rather than gaps. AGENTS.md §6.1 says *"agents never push directly
to `main`"* and `github-setup.md` §3 says the ruleset *"enforces it server-side"* — it
enforces nothing, and the rule has already been broken once, at roadmap 3.7, where a
session's work landed on `main` and was undone with an authorised force-push. And with
private vulnerability reporting off, an outside reporter following `SECURITY.md` reaches an
advisory form they cannot submit; their remaining option is the public issue tracker, which
is precisely what a disclosure policy exists to prevent.

This is the same failure mode as the label import, which was partial until 2026-09-11 and was
found when `gh pr create --label fix` failed. A setup document is a list of things somebody
did once, and nothing says which.

### The timing question, again

Spec 06 §4 says *"signed artifacts + SBOM **from 1.0**"*, and 1.0 lands at Milestone 7.

## Decision

**Both are built now, and they run from this release onward.** The same reasoning ADR-0114
applied to the compatibility promise and ADR-0116 applied to the publish pipeline, and here
it is stronger than in either: a release that ships unsigned cannot be signed afterwards.
"From 1.0" is when the guarantee must hold, and the way to make it hold at 1.0 is for it to
have been running for several releases by then — 6.11 named *"built and unproven at its last
inch"* as its own residual risk, and this item is built not to repeat it.

**Provenance and the SBOM are signed through Sigstore, keylessly.** `release.yml` gains
`id-token: write` and `attestations: write`, runs `actions/attest-build-provenance` over the
archives and `actions/attest-sbom` binding the SBOM to the wheel's digest. Provenance says
*where these bytes came from*; the SBOM attestation says *what is inside them*, and binds it,
so a friendlier SBOM cannot be swapped in. **There is still no key and no secret** — an
identity is minted per run, which is exactly the property Trusted Publishing gives the
upload (ADR-0116) and what threat boundary B2 asks of anything holding publish authority.
A test pins the permission set and fails on `GPG_`, `COSIGN_` or `SIGNING_KEY` appearing in
the workflow.

**The SBOM describes the artifact, and the tool fails if it describes anything else.**
`tools/build_sbom.py` installs the wheel into an **empty** environment and inventories that.
Pointing a generator at this repository's own `.venv` is the obvious move and produces a
confident, wrong answer: `uv sync --all-extras --dev` installs 162 distributions of which
four are the runtime closure, so the SBOM would tell a consumer they are running pytest,
ruff and hatch. `check_sbom` fails when a development tool appears in the output — the
property the clean environment buys, asserted rather than assumed — and also when the root
component cannot name its own release, which it could not at first: `version` is `dynamic`
in `pyproject.toml`, the generator reads PEP 621 metadata statically, and the first SBOM
came back describing `mycelium-os` at no version at all.

A release inventories **every extra** (85 components); CI inventories the default install
(14) on every push. Output is CycloneDX 1.6 JSON, written reproducibly, so a diff between
two releases is the dependency change.

**The generator runs in an environment of its own and is declared in none of ours** — and
this is the decision the item actually turned on, arrived at by being wrong first.

It shipped as a `sbom` dependency group: kept out of `dev` so no matrix cell paid for its 18
marginal packages, but declared, locked, and synced by the one CI job that needed it. The
reasoning followed ADR-0098's `render` precedent exactly, the measurement supported it, and
**it changed what the compiler produces.** `cyclonedx-bom` pulls `chardet`; BeautifulSoup
binds `bs4.dammit.chardet_module` to it whenever it is importable and uses it to guess a
document's encoding; the HTML lane goes through that path, and five documents in the vendored
ingested corpus projected differently. `tools/build_ingested_corpus.py --check` failed in the
`full` ladder, and uninstalling that one package and re-running it turned green — which is
the whole proof.

So the generator is invoked through `uv tool run`, resolved and cached outside this project,
never importable by anything this project runs. The rule that replaces the one it came in
with is stronger than *keep heavy tools out of `dev`*:

> A tool that is not part of this product must not be resolvable alongside it. What is
> importable is an input to the compiler, whether or not anything imports it on purpose.

`tests/test_packaging.py` holds it — no `cyclonedx` entry in `dependencies`, in any extra, in
any dependency group, and no `--group sbom` in any workflow. CI's `distribution` job still
builds the SBOM on every push, so the generator runs continuously rather than for the first
time at a release; it simply does so without being installed. The cost is named: the
generator's version resolves at run time inside a bounded range rather than being pinned by
`uv.lock`, and the first run on a machine fetches it. Acceptable because the output is a
release artifact validated against the CycloneDX schema, not a golden whose bytes a gate
compares.

**`build_sbom.py` is named in `test_verify_ladder.py`'s exclusion list, with its reason.**
It produces a release artifact rather than judging a diff: the only change that can make the
SBOM wrong is a change to `[project.dependencies]`, which `check_distribution.py` already
catches by installing the wheel, and a contributor's local gate must not require a dependency
group the project deliberately does not install. Roadmap 4.40's finding was that a CI-only
tool goes unnoticed; a tool named in the exclusion list with its argument is not unnoticed.

**`good first issue` means reserved, and AGENTS.md is where that becomes true.** The label is
declared in the manifest with that meaning, and §6.1 forbids an agent from taking an issue
carrying it. Without the rule the label is a trap: Milestone 5 closed 43 items in five days,
so anything a newcomer took a week to reach would already be merged, and an invitation
withdrawn before it can be accepted is worse than no invitation. `help wanted` carries no
reservation. This does not reverse the no-tracking-issues decision — a reserved issue is an
invitation addressed to a person, not a second copy of a roadmap item, and `ROADMAP.md`
remains the single source of planned work.

**CONTRIBUTING.md states which rungs are open, because "contributions welcome" is not
information.** Five, lowest first: report what broke; fix the documentation you were reading
when it was wrong; take a reserved issue; **write a plugin**; change the core. The fourth is
the one that matters pre-1.0 and the one this project is built for — it needs no core change,
no permission and no exception, and the contracts it stands on are frozen (ADR-0114). The
old text discouraged unsolicited contributions in general, which was accurate about the core
and wrong about everything else.

**CODEOWNERS names the paths that carry a contract.** Every line resolves to the same person
today and they are not redundant: the file is where a reviewer learns which paths make a
change a compatibility event rather than an implementation detail, and drawing that line
while the answer is easy is cheaper than inventing it when a second collaborator arrives.

**`tools/check_repo_settings.py` asks GitHub which documented steps are installed, and never
installs one.** Every remaining step is a repository setting under the owner's account —
the same boundary `publish.yml` draws around the index side — so the tool reports, prints the
command beside each finding, and exits non-zero. `github-setup.md` gains a §0 pointing at it
and dates what was absent when it was first run.

## Alternatives Considered

- **Defer signing and the SBOM to Milestone 7, because the spec says "from 1.0".** Rejected
  on what the words protect. The guarantee starts at 1.0; the mechanism has to predate it, or
  1.0 is the first time it runs — and unlike a docs site or a lint, an unsigned release
  cannot be repaired later. Every release between here and 1.0 would have shipped unverifiable.
- **Sign with a cosign key held in repository secrets.** The traditional answer, and it
  reintroduces exactly what ADR-0116 removed: a long-lived secret to leak, rotate and
  misplace, inside a threat boundary that would have to grow to cover it. Sigstore's keyless
  flow gives the same verifiability with a per-run identity.
- **Generate the SBOM from `pyproject.toml`'s declared requirements.** Fast, needs no
  install, and answers the wrong question: `pydantic>=2.11` is a range, and an SBOM that
  cannot name a version cannot be fed to a scanner. Licences are also unavailable without the
  packages, and licence data is half the point.
- **Generate it from this repository's `.venv`.** Rejected in the strongest terms: it is one
  command, it works, and it is a lie about what a consumer installs. The check that forbids
  it is in the tool.
- **Hand-write the CycloneDX JSON and skip the dependency**, as ADR-0011 did for the MCP SDK.
  Rejected, and the difference from that case is the point: the MCP subset was small, stable
  and *checkable against the reference client*. CycloneDX's value is that somebody else's
  scanner parses it, so conformance is the whole deliverable, and the library validates what
  it writes against the published schema. Writing it by hand would produce something that
  looks like an SBOM and might not be one.
- **Put the generator in `dev`, or in a `sbom` group.** Both were tried; the group was
  written, locked and synced before the ladder caught what it did. `render` (ADR-0098) is the
  precedent that made a group look right, and the difference is the one this ADR now records:
  `typst` is a *renderer invoked by a tool*, and nothing it brings is opportunistically
  imported by the compiler. `chardet` is. The precedent was about **cost**; the rule that
  replaces it is about **reachability**.
- **Make `build_sbom.py` a gate in `verify.py`'s plan.** It would charge every `code`-mode run
  about forty seconds and require a group the project deliberately does not install, to catch
  a class of change `check_distribution.py` already catches. Excluded with the argument
  written down rather than by omission.
- **File good-first-issues without the reservation rule.** The cheap version of this rung, and
  it would have been dishonest: the pipeline closes items in days, so the label would have
  described work that was already gone. The rule is what makes the label true.
- **Install the three absent GitHub settings.** They are the owner's repository settings, not
  a change to this repository, and this project draws that line deliberately (ADR-0116's three
  index-side steps). Reported with the exact command instead.
- **Leave `github-setup.md` as prose and fix the three settings by hand.** Rejected on this
  project's standing rule: a claim without a check is a claim. The settings would drift again,
  and the next person to notice would be the one whose PR or whose disclosure failed.

## Consequences

- **A release now attaches five things**: wheel, sdist, SBOM, and two attestations in
  GitHub's store. A consumer verifies with `gh attestation verify <file> --repo
  danielPoloWork/mycelium-os`, which `docs/workflow/packaging.md` now carries — an
  attestation nobody is told how to check is decoration.
- **The release workflow gained two third-party actions holding `attestations: write`**, both
  pinned to a full commit SHA and held there by a test. That is new supply-chain surface on
  threat boundary B2, accepted for the verifiability it buys and bounded the way B2 asks.
- **Three findings are now the owner's to act on**, and none of them can be closed by code:
  branch protection on `main`, private vulnerability reporting, and re-running the label
  import. `python tools/check_repo_settings.py` is how their state is read from now on.
- **An agent may not take a `good first issue`.** If such an item blocks the roadmap, the
  contract says to ask rather than to take it quietly.
- **Nothing about the product's behaviour changes.** No baseline, gate, golden or corpus
  moves; `src/` is untouched except that nothing in it was touched at all.
- **The ingestion lane's output depends on which optional packages happen to be importable**,
  and that is now on the record rather than folded into this item's fix. `chardet` is one;
  nothing says there is not another, and nothing pins the encoding detector the HTML parser
  ends up using. Filed as roadmap **6.15**: the check that caught this compares against a
  committed corpus, so it *detects* the divergence and does not prevent it, and two
  contributors with different unrelated packages installed would regenerate that corpus
  differently.
- **A limitation, stated.** The SBOM describes one resolution, taken when the artifact was
  built — that is what the format is for and the limit of what it claims. And the whole
  signing path is, like 6.11's publish, *unproven at its last inch*: no tag has been pushed
  since it was written, so the attestation steps have never run against GitHub's store. The
  first release after this one is where that is proven, and it is the reason this landed a
  milestone before 1.0 rather than at it.

## References

- Spec: `.draft-specs/06-roadmap-and-governance.md` §4 (releases, contributions, governance)
  and §Phase 4 (the contribution ladder in the milestone's own scope line).
- The promise and how to check it: `docs/workflow/packaging.md` § *Provenance*; the ladder:
  `CONTRIBUTING.md` § *The ladder*; the settings: `docs/workflow/github-setup.md` §0.
- Re-runnable: `uv sync --group sbom && python tools/build_sbom.py`,
  `python tools/build_sbom.py --extras all`, `python tools/check_repo_settings.py`.
