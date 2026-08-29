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

## Versioning & provenance

- The published version **equals** the tag and the version constant (the consistency lint's
  `version-lockstep` enforces this).
- Prefer a reproducible build and attach provenance/SBOM where the ecosystem supports it.
