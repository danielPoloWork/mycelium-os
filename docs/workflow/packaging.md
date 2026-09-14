# Packaging & Distribution

How `mycelium-os` is built into a distributable artifact and published. This doc exists
because the project is distributed via a package registry (`capabilities.packaging`).

## Artifact

Two archives, and each is an **allowlist** rather than whatever the build happened to sweep
up (roadmap 6.11, [ADR-0116](../adr/0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md)):

| | contents | why |
|---|---|---|
| **wheel** `mycelium_os-X.Y.Z-py3-none-any.whl` | `mycelium/` and its `dist-info` — 106 entries, runtime only, with the PEP 561 `py.typed` marker | what a consumer installs |
| **sdist** `mycelium_os-X.Y.Z.tar.gz` | `src/mycelium/`, `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md` — about 1.5 MB | what builds the wheel, and what states its terms |

- **Consumers import it via:** `from mycelium.sdk.types import KirDocument`.
- **Metadata:** name, version (from `__about__.py`), license `Apache-2.0` as a PEP 639 SPDX
  expression, keywords, classifiers, and the links a registry expects — homepage, docs,
  changelog, source, issues.
- **`tests/` is deliberately not in the sdist.** The suite reads `eval/corpora`,
  `tests/fixtures`, a pandoc binary, nine tree-sitter grammars and, for two tests, a 133 MB
  model; shipping tests that cannot run is worse than not shipping them. They are one
  `git clone` away and the metadata links the repository.

**Why an allowlist.** Until 6.11 the sdist was declared by one exclusion (`contrib`), which
made it *the working directory minus whatever the root `.gitignore` named*. The archive built
at v0.5.0 carried 14.5 MB across thirty top-level entries: a 1,248-file Hypothesis cache
(ignored by a nested `.gitignore` the backend does not read), the vendored delivery factory,
2.7 MB of judged corpora — and, the finding that decided it, **untracked working files**.
Two of those are defects rather than bloat: a published version is immutable, so an artifact
whose contents depend on the builder's tree cannot be reproduced, and an in-progress document
that reaches an index cannot be recalled.

`python tools/check_distribution.py` is what holds this: it builds both archives, asserts the
sdist carries only what it declares, asserts the wheel carries the package and its marker,
runs `twine check --strict`, then installs the wheel into a clean environment and walks it
from `mycelium init` to a cited answer. It runs in CI at `code` mode and again inside the
publish workflow, because an index cannot un-publish.

## Registry

- **Where:** [PyPI](https://pypi.org), under the name **`mycelium-os`** — decided by the owner
  at D-024 (2026-07-31) and re-verified free on 2026-09-14. The import package stays
  `mycelium`; the console script stays `mycelium`.
- **`mycelium` as a distribution name is taken** — one release, `0.4.9`, a luigi workflow
  library last uploaded 2019-10-08. D-024 records a PEP 541 transfer request as the route to
  it, and that request is not this item's business: if it is ever granted, the distribution
  moves and `mycelium-os` stays as a transitional alias.
- **Auth: there is no credential.** Publishing uses **PyPI Trusted Publishing** (OpenID
  Connect): the workflow asks GitHub for a short-lived token scoped to this repository, this
  workflow file and the named environment, and the index verifies it. No API token exists in
  repository secrets to leak, rotate or misplace — which is what threat-model B2 asks of
  anything holding publish authority.

## Publish flow

Publishing is tied to the release ([`release.md`](release.md)) and is the **human checkpoint**,
like the GitHub Release itself:

1. The release PR is merged and the annotated tag is pushed (`vX.Y.Z`).
2. `release.yml` fires on the tag, builds both archives, refuses the build if the artifact
   version does not equal the tag, and attaches them to a **draft** GitHub Release.
3. A human reviews and presses **Publish** on the GitHub Release.
4. A human runs the **`publish` workflow** by hand, naming the tag and the index.

**Step 4 cannot happen by itself, and that is structural.** `publish.yml` fires on
`workflow_dispatch` and nothing else, so pushing a tag can never publish as a side effect; its
index input defaults to **TestPyPI**; and its job runs inside a GitHub Environment, where
required reviewers make the approval something GitHub enforces rather than something a
document asks for. The job re-derives the tag-equals-version invariant rather than trusting
the drafting run, runs the distribution check, and only then uploads.

The rule that comes with a registry: **a published version is immutable.** A mistake is fixed
forward with a new version, never by overwriting, and a name is claimed by its first upload.

## Turning the publish on

Three things remain, and all three are the maintainer's — no workflow can do them, and this
repository deliberately holds no credential that would let one try.

1. **Rehearse on TestPyPI.** Add a *pending publisher* at
   <https://test.pypi.org/manage/account/publishing/> for project `mycelium-os`, owner
   `danielPoloWork`, repository `mycelium-os`, workflow `publish.yml`, environment `testpypi`.
   Then run the `publish` workflow with the default index. TestPyPI is throwaway: it proves
   the OIDC handshake, the metadata and the upload without committing the name anywhere that
   matters.
2. **Create the `pypi` environment** in Settings → Environments, with yourself as a required
   reviewer. Without it the environment gate is a label; with it, a run waits.
3. **Add the PyPI pending publisher** at <https://pypi.org/manage/account/publishing/>, same
   fields with environment `pypi`, and run the workflow with `index: pypi`. That upload claims
   the name.

**On sequencing.** Roadmap 6.11 was filed saying not to reserve a name before 6.5's trademark
search lands. D-024 had already decided the name, and the exposure it is worried about is
already carried: `mycelium://` citation URIs and the `mycelium_*` MCP tool names are inside
the five stable contracts, whose identity rules are append-only *for good*
([ADR-0114](../adr/0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)).
A trademark outcome that forced a rename would break those whether or not PyPI holds the name.
So the publish does not wait on 6.5 — but it is still the owner's call to make, which is why
the last step above is a step and not a workflow trigger. See ADR-0116.

## A second distribution: modules

Since roadmap 5.5 this repository builds **two** packages, and only one of them is
`mycelium-os`.

| | `mycelium-os` | `mycelium-chats` |
|---|---|---|
| Sources | `src/mycelium/` | `contrib/chats/src/mycelium_chats/` |
| Version | `__about__.py`, in lockstep with the tag | its own, in its own `pyproject.toml` |
| Ships when | every release | on demand, independently |
| Installed by a user | `pip install mycelium-os` | `pip install mycelium-chats` |

They are joined for development by a **uv workspace** (`[tool.uv.workspace] members =
["contrib/*"]`), so `uv sync --all-extras --dev` installs the module from the working tree
and a core change is visible to it without a publish. Three consequences worth knowing:

- **The `mycelium-os` sdist excludes `contrib/`** (`[tool.hatch.build.targets.sdist]`), so one
  archive never carries two packages. The wheel never did — it names its packages explicitly.
- **A module's version is not in version lockstep** with the core's, and the consistency
  lint does not check it. That is deliberate: spec 05 §4.3 lets a contrib module "lag one
  minor", and a module is held to the *plugin API generation* it declares in `PluginMeta`
  (spec 05 §5), which the registry checks at load time and reports precisely. A version pin
  would be a second, weaker statement of the same thing.
- **Publishing a module is its own act**, human-gated like every publish here, and it is not
  tied to the core's release. `mycelium-chats` has not been published yet: pre-1.0 it is
  developed in-repo, and spec 05 §4.3 promotes it to its own repository after the 1.0 freeze.

Both are held to the same gates: `ruff`, `mypy --strict` and the test suite read `contrib/`
too (`tools/verify.py`'s `CHECKED_PATHS` and `TYPED_PATHS`), because a core change that
breaks a module must fail the *core's* own suite.

## Versioning & provenance

- The published version **equals** the tag and the version constant (the consistency lint's
  `version-lockstep` enforces this).
- Prefer a reproducible build and attach provenance/SBOM where the ecosystem supports it.
