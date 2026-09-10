# Packaging & Distribution

How `mycelium-os` is built into a distributable artifact and published. This doc exists
because the project is distributed via a package registry (`capabilities.packaging`).

## Artifact

- **What ships:** the package produced by `Hatch (PEP 517/518, pyproject.toml)` (and its contents — runtime only,
  no tests/benches).
- **Consumers import it via:** `from mycelium.sdk.types import KirDocument`.
- **Metadata:** name, version (from `__about__.py`), license `Apache-2.0`, and the
  links a registry expects (repo, docs, changelog).

## Registry

- **Where:** the package registry (Dependabot ecosystem: `pip`).
- **Auth:** publishing credentials live in CI secrets, never in the repo.

## Publish flow

Publishing is tied to the release ([`release.md`](release.md)) and is a **human-gated** step,
like the GitHub Release:

1. The release PR is merged and the annotated tag is pushed (`vX.Y.Z`).
2. CI builds the artifact on the tag and verifies it (contents, metadata, version match).
3. A human approves the publish step; CI pushes to the registry.
4. The published version is immutable — a mistake is fixed forward with a new version, never by
   overwriting.

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
