# ADR-0116: Publish under a name already decided, and let the artifact be a defined thing

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), under owner decision D-024 for the name
- **Related:** [ADR-0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md)
  (the review that filed this item), [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (the frozen contracts that already carry the brand), [ADR-0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md)
  (the docs site this links from the index page), [ADR-0071](0071-advertise-the-types-and-check-the-tools.md)
  (the PEP 561 marker, now checked in the built wheel rather than the tree),
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md) and
  [ADR-0059](0059-make-the-plan-one-implementation-too.md) (one implementation, two callers);
  BUG-0006 (the release that shipped zero assets); D-024 (the name), D-026 (one identifier),
  D-029 (one engine until the freeze); spec 06 §Phase 3; `docs/workflow/packaging.md`,
  `docs/workflow/release.md`; roadmap 5.43, 6.5, 6.11, 6.12

## Context

The M5 exit review found the gate under the gate: *≥ 10 external repos dogfooding* stands at
zero, and the reason is one step earlier than adoption — **the package is not published
anywhere**. `release.yml` builds the wheel and the sdist, refuses a build whose version does
not equal the tag, attaches both to a draft GitHub Release, and stops. No registry step
appears anywhere in `.github/`. Meanwhile `docs/workflow/packaging.md` described a publish
flow in the present tense and the README told a reader to `pip install mycelium-os`.

Roadmap 6.11 asked four questions: which index, whether the name is available, how the
credential is held, and what the release procedure gains as a step. Answering them turned up
two things the item did not predict.

### The name was decided fourteen months before the item worried about it

6.11 says *"whether the name is available (it interacts with 6.5's trademark and brand
decision, so do not reserve one before that lands)"*. But D-024 — an **owner decision**, dated
2026-07-31 — already reads: *"PyPI distribution: `mycelium-os` (verified available
2026-07-31; `mycelium` is held by an unrelated package abandoned since 2019 …)"*, and in the
same paragraph: *"A trademark search remains a pre-1.0-launch task."* The owner decided the
name **and** recorded that the trademark search was still outstanding. Re-verified on
2026-09-14:

| name | PyPI | detail |
|---|---|---|
| `mycelium-os` | free | also free on TestPyPI |
| `mycelium` | taken | one release, `0.4.9`, a luigi workflow library, last upload 2019-10-08 |
| `mycelium-chats` | free | the second distribution, unpublished by design (D-029) |

So the item's caution was written at 5.43 without D-024 in front of it. What the caution was
protecting against is real but already spent: a trademark outcome that forced a rename would
not merely cost a PyPI name, it would break `mycelium://` citation URIs and the `mycelium_*`
MCP tool names — both inside the five stable contracts, whose identity rules ADR-0114 makes
append-only *for good*. The brand is in a frozen contract and in a public repository. Holding
the PyPI name back protects nothing that is not already committed.

### The artifact was not a defined thing

The sharper finding, and it is only visible by opening the archive — which nothing ever did.
CI ran `hatch build` on every cell, proved the tag compiled, and threw the result away. No
test opened it; no test installed it. The sdist was declared by a single exclusion
(`exclude = ["contrib"]`), which means *the working directory, minus contrib, minus whatever
the root `.gitignore` names*. Built at v0.5.0 it carried **14.5 MB across thirty top-level
entries**:

| in the sdist | size | what it is |
|---|---|---|
| `.hypothesis/` | 1,248 files | a machine-local example database, ignored by its own nested `.gitignore` — which hatchling does not read |
| `eval/` | 2.7 MB | judged corpora, including documentation this project did not write |
| `.eados-core/`, `.claude/`, `orchestrator/` | ~2 MB | the delivery factory |
| `docs/` | 316 files | ADRs, journal, 1.9 MB of brand assets |
| **`docs/analysis/`, `.claudeignore`** | — | **untracked working files** |

The last row is the one that decides it. Those files are untracked and not gitignored, so
they were swept in from the builder's tree. A published version is immutable and cannot be
recalled; an artifact whose contents depend on who built it and what they had open is not
reproducible, and an in-progress document that reaches an index is published forever.

The metadata had a matching gap: no `classifiers` and no `keywords` at all, and two
`[project.urls]` entries — while `packaging.md` had promised *"the links a registry expects
(repo, docs, changelog)"* since M1. An index page with no audience, no Python versions, no
topic and no link to the documentation is invisible to exactly the reader 6.12 needs.

## Decision

**The index is PyPI and the name is `mycelium-os`**, confirming D-024 rather than re-deciding
it. The import package and console script stay `mycelium` (D-026: one identifier). The PEP 541
transfer request for the bare `mycelium` name stays where D-024 put it — a separate future
act, not this item's business.

**The credential is not a credential.** Publishing uses PyPI **Trusted Publishing** (OIDC):
the workflow asks GitHub for a short-lived token scoped to this repository, this workflow file
and the named environment. No API token exists in repository secrets to leak, rotate or
misplace, which is what threat-model B2 asks of anything holding publish authority. The
publish job's permissions are exactly `id-token: write` and `contents: read` — it cannot write
to the repository.

**Publishing cannot happen as a side effect, and that is structural rather than procedural.**
`publish.yml` fires on `workflow_dispatch` and nothing else, so no tag push can reach it; its
index input defaults to **TestPyPI**; and its job runs inside a GitHub Environment named by
that input, where required reviewers make the approval something GitHub enforces. Before
uploading it re-derives the tag-equals-version invariant rather than trusting the drafting run,
and runs the distribution check. `tests/test_packaging.py` pins each of those properties, so a
later edit that makes it fire on a push, or that adds a token, fails a test rather than a
release.

**The sdist becomes an allowlist**: `src/mycelium/`, `pyproject.toml`, `README.md`, `LICENSE`,
`CHANGELOG.md` — 14.5 MB to 1.5 MB, thirty top-level entries to six. An allowlist states what
a source distribution *is*; a denylist has to predict what will be lying around, and the two
defects above are exactly what it failed to predict. `tests/` is deliberately absent: the
suite reads `eval/corpora`, `tests/fixtures`, a pandoc binary, nine tree-sitter grammars and a
133 MB model, so shipping tests that cannot run is worse than not shipping them.

**The artifact is checked before it can be published.** `tools/check_distribution.py` builds
both archives, asserts the sdist carries only what it declares and none of the named
regressions, asserts the wheel carries the package and its PEP 561 marker, runs `twine check
--strict`, then **installs the wheel into a clean environment** and walks it from `mycelium
init` through `build` to a `mycelium://` citation. That last step is the check the README's
install line has been making on the project's behalf since M1, and it now runs: at `code` mode
in `tools/verify.py` and in CI's `distribution` job (one implementation, two callers —
ADR-0059), and again inside the publish workflow, because an index cannot un-publish. 64 s,
the same price as the ingested-corpus check beside it.

**The metadata describes the package to a reader who has not heard of it**: keywords,
classifiers whose Python versions are compared against the CI matrix by a test rather than
maintained beside it, and the five URLs a registry expects. No `License ::` classifier — the
SPDX expression is the current spelling and PEP 639 deprecates the other, so the fact is
stated once.

**The publish does not wait on 6.5, and the first upload is still the maintainer's.** The
sequencing argument is in Context: the trademark exposure is already carried by the frozen
contracts. But an upload to an index is irreversible and outward-facing, and the index-side
setup — a PyPI account, a pending publisher, an environment reviewer — is the maintainer's in
a way no workflow can be. So the pipeline is finished and the last step is a step:
`packaging.md` § *Turning the publish on* lists the three actions, in the order that rehearses
on TestPyPI first.

**Until that upload happens the install lines say what is true.** The README had no install
instruction at all — the gap was larger than the wrong line 5.43 recorded — and the tutorial's
`pip install mycelium-os` could not work. Both now give the tag install, verified in a clean
environment, and say in one line what it becomes.

## Alternatives Considered

- **An API token in repository secrets.** The traditional flow and the one `packaging.md`
  described (*"publishing credentials live in CI secrets"*). Rejected: a long-lived token that
  can publish is the highest-value secret a repository can hold, it has to be rotated by
  somebody who remembers to, and Trusted Publishing removes the object entirely rather than
  guarding it better. There is no case where the token is easier here — the OIDC handshake
  needs no repository configuration at all, only index-side setup the maintainer does once.
- **Publish from `release.yml` on the tag push, gated only by the environment.** Fewer moving
  parts, and rejected on what happens when the gate is not configured: an environment that
  exists without required reviewers does not pause anything, so the safety of the whole flow
  would rest on a setting nobody can see from the repository. A `workflow_dispatch`-only
  workflow is safe when *nothing* is configured, which is the state it will spend its first
  weeks in. It also keeps AGENTS.md §11's boundary legible: an agent pushes the tag, and the
  act an agent must never perform lives behind a trigger an agent cannot pull.
- **Publish to PyPI directly, skipping TestPyPI.** Rejected: the first upload claims the name
  and cannot be undone, and it is also the first time the OIDC handshake, the environment and
  the metadata run together. TestPyPI is the same machinery against an index nobody depends
  on. Making it the *default* of the index input costs nothing and means a mis-click rehearses
  instead of committing.
- **Keep the denylist and add the offenders to it** (`.hypothesis`, `docs/analysis`,
  `.claudeignore`, …). Rejected, and it is the heart of this ADR: a denylist is a prediction
  about what will be in a working tree, and the two defects it let through were both things
  nobody predicted. The next one will also be unpredicted. An allowlist is wrong only in the
  direction that fails loudly — a missing file breaks the build from the sdist, which
  `uv build` exercises on every run.
- **Wait for 6.5 before building any of this.** Rejected: 6.5 is an owner call of size S with
  no date, 6.12 is blocked behind 6.11, and nothing in the pipeline commits the name. Building
  it now means the trademark decision, whenever it lands, is followed by one workflow run
  rather than by a milestone of packaging work.
- **Reserve the name now with a placeholder upload.** Rejected: it commits the name without
  the artifact being ready, which is the squatting shape, and it spends the irreversible act
  on a version nobody wants. The pending-publisher mechanism reserves nothing and costs
  nothing, which is why the checklist uses it.
- **Ship `tests/` in the sdist** for downstream packagers. Genuinely arguable and rejected on
  the facts of this suite: it cannot run without the corpora, the fixtures, a pandoc binary,
  nine grammars and a model. A packager who unpacked it would find tests that fail for reasons
  unrelated to their build. Revisit if a packager ever asks — the allowlist is one line.
- **Pin the wheel's contents with a golden**, as ADR-0114 does for the contracts. Rejected as
  the wrong instrument: a wheel's file list changes with every module added, so the golden
  would be re-blessed on most PRs and read by nobody (ADR-0053's rule). The properties worth
  pinning are invariants — *only the package*, *the marker is present*, *no `__pycache__`* —
  and those are assertions, not a golden.

## Consequences

- **The release procedure gains step 11**, and the agent-versus-human boundary gains a row:
  agents never run the `publish` workflow. Steps 1–10 are unchanged, so a release that stops
  at step 10 is exactly the release this project has been cutting.
- **`pip install mycelium-os` still does not work, and the README no longer says it does.**
  The tag install is there instead, verified end to end in a clean environment. When the first
  upload lands, three short blocks collapse to one line each — the change is a paragraph, not
  a project.
- **CI gains a `distribution` job** and `tools/verify.py` gains a `distribution` step at
  `code` mode. `tests/test_verify_ladder.py` already forces those to agree.
- **A docs-only change does not run the distribution check**, and the one thing such a change
  can move is the long description, `README.md`. For `text/markdown` `twine check` validates
  little beyond that the file decodes, so the gap is named here rather than paid for on every
  documentation PR.
- **The sdist is reproducible in the sense that matters**: its contents no longer depend on
  the builder's working tree. Byte-level reproducibility is not claimed — archive timestamps
  are not pinned — and nothing in this project needs it.
- **Attestations come free.** `pypa/gh-action-pypi-publish` emits PEP 740 attestations under
  Trusted Publishing, so uploads are provenance-bearing without extra work. That is *not*
  6.6's "signed artifacts + SBOM", which remains open and is a larger claim.
- **A limitation, stated.** Everything here is checked except the one thing that cannot be:
  no upload has ever happened, so the OIDC handshake, the environment gate and the index's
  acceptance of this metadata are unexercised. TestPyPI is in the flow precisely so the first
  exercise is a rehearsal rather than the name-claiming upload, and until someone runs it the
  honest status of this item is *the pipeline is built and unproven at its last inch*.

## References

- Decision log: D-024 (the name, and the trademark note), D-026 (one identifier), D-029 (one
  engine until the freeze).
- `.github/workflows/publish.yml`, `.github/workflows/release.yml`, `.github/workflows/ci.yml`
  (`distribution`).
- `docs/workflow/packaging.md` § *Turning the publish on* — the three maintainer actions.
- Re-runnable: `python tools/check_distribution.py`, and
  `curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/mycelium-os/json` (404 while
  the name is unclaimed).
