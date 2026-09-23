---
id: BUG-0033
title: the release SBOM is valid CycloneDX and is still refused by the attestation it feeds
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-23
affected-versions: "0.6.0 (the first release whose workflow attests an SBOM)"
fixed-in: "next release (v0.6.0 is re-drafted with it)"
---

# BUG-0033: the release SBOM is valid CycloneDX and is still refused by the attestation it feeds

## Summary

Pushing the `v0.6.0` tag built the wheel and the sdist, verified the version, generated the
SBOM and attested the build provenance, then failed at **"Attest the SBOM against the
wheel"** with `Unsupported SBOM format. Must be valid SPDX or CycloneDX JSON.` No draft
release was created and nothing was attached.

## Environment

- **Affected versions:** 0.6.0 — the SBOM attestation step was added at roadmap 6.6
  (#152, ADR-0117), after v0.5.0, so v0.6.0 was the first tag that ever ran it.
- **Toolchain / platform:** GitHub-hosted `ubuntu-24.04`; `actions/attest-sbom@c604332`
  (v4.1.0), which delegates to `actions/attest@59d8942`; `cyclonedx-bom>=7,<8`.
- **Configuration:** `tools/build_sbom.py` runs the generator with `--sv 1.6 --of JSON
  --output-reproducible --validate`.

## Reproduction

Run `release.yml` for any tag. The generated `sbom/mycelium_os-<version>.all-extras.cdx.json`
has `bomFormat` and `specVersion` but no `serialNumber`, and the attestation step rejects it.
Pinned by `tests/test_packaging.py::test_the_stamped_sbom_is_one_actions_attest_recognises`,
which executes the workflow step's own code against a document without a serial.

## Expected vs. actual

- **Expected:** a schema-valid CycloneDX document is attested against the wheel's digest,
  and the release is drafted with the wheel, the sdist and the SBOM attached.
- **Actual:** the attestation refuses the document, and the job stops before drafting.

## Root cause

Two correct decisions that disagree about one optional field.

`actions/attest` classifies an SBOM by shape. Its `checkIsCycloneDX` (in `src/sbom.ts` at
the pinned commit) returns true only when **`bomFormat`, `serialNumber` and `specVersion`**
are all present. The CycloneDX schema makes `serialNumber` *optional*.

`tools/build_sbom.py` passes `--output-reproducible` deliberately — "no timestamp, no random
serial number: two runs over one resolution must produce identical bytes" — and the
generator honours it by omitting the serial. The document therefore validates against the
published schema (the generator's own `--validate` passes) and is still not something the
attestation action recognises as CycloneDX at all.

Nothing exercised the pair before a real tag did: the attestation needs a Sigstore OIDC
identity that only a workflow run has, so no local check or pull-request job could have
reached it.

## Impact

v0.6.0's first release run produced no draft and attached no artifacts. Nothing was
published, the tag itself is correct (it points at the release merge, `bc8342a`, which
declares 0.6.0), and no consumer could have received an unattested artifact — the workflow
failed closed. Severity medium rather than low because it blocks every release until fixed.

## Fix / workaround

A workflow step between the generator and the attestation gives the SBOM a
**deterministic** serial: `urn:uuid:` of a UUIDv5 over
`pkg:pypi/mycelium-os@<version>?checksum=sha256:<wheel digest>`. It satisfies the attestation
without giving up reproducibility — two runs over one wheel write the same serial, and a
different wheel cannot share it — and it still matches the schema's `urn:uuid` pattern. A
document that already carries a serial is left alone.

**Why the workflow and not `tools/build_sbom.py`.** A re-draft of an existing tag runs the
workflow file from the default branch but checks out the *tag's* tree (BUG-0006), so a fix
to the tool could never reach `v0.6.0`. Only a workflow step can, and the same step serves
every later tag. The tag is not moved: the release is re-drafted with
`gh workflow run release.yml --ref main -f tag=v0.6.0`, the recovery `docs/workflow/release.md`
already documents.

**Why `fixed-in` names no number.** BUG-0001 defines the field as the first tagged release
whose tree *contains* the fix. This fix merges after `v0.6.0` was tagged, so that tree does
not carry it even though its release is the first one drafted by it — BUG-0006's shape, not
BUG-0001's. Whether the next tag is a patch or Milestone 7's is not decided, so the field
says so rather than guessing, and the next release cut sets the version.

## References

- Fixing PR: <#NNN>
- `CHANGELOG` entry: `[Unreleased]` → `Fixed`
- Related: BUG-0006 (why a re-draft reads the default branch's workflow and the tag's
  tree), ADR-0117 (the SBOM and its attestation), roadmap 6.6
