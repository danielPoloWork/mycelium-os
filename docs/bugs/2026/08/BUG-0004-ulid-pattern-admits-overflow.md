---
id: BUG-0004
title: the Ulid record pattern admits 26-character strings that overflow 128 bits
status: fixed
severity: medium
reporter: internal
discovered: 2026-08-29
affected-versions: "unreleased (introduced by PR #14, roadmap 2.2)"
fixed-in: "0.2.0"
---

# BUG-0004: the Ulid record pattern admits 26-character strings that overflow 128 bits

## Summary

The `Ulid` contract in `mycelium.sdk.types` validated any 26 Crockford-base32 characters.
Twenty-six base32 characters carry 130 bits, but a ULID is 128, so strings whose leading
character exceeds `7` are not ULIDs at all — yet they passed record validation and could
have entered a `doc_id`, `snapshot_id`, or `entity_id` field.

## Environment

- **Affected versions:** unreleased — merged to `main` in PR #14 (roadmap 2.2), never in a
  released artifact (v0.1.0 predates `mycelium.sdk`).
- **Toolchain / platform:** any; pure validation logic (pydantic 2.13.5, CPython 3.12+).
- **Configuration:** none — the pattern is unconditional.

## Reproduction

```python
from pydantic import TypeAdapter
from mycelium.sdk.types import Ulid

TypeAdapter(Ulid).validate_python("8" * 26)   # accepted before the fix
```

The regression test is
[`test_decode_ulid_rejects_malformed_input`](../../../../tests/test_sdk_identity.py), whose
`"8" * 26` case asserts that the record contract and `decode_ulid` refuse the same inputs.

## Expected vs. actual

- **Expected:** `"8" * 26` is rejected — it decodes to a value larger than 2^128 - 1 and
  therefore has no timestamp/randomness interpretation.
- **Actual:** the pattern accepted it, so an unconstructible identity could be stored in a
  record and only fail later, at decode time in a different layer.

## Root cause

The pattern `^[0-9A-HJKMNP-TV-Z]{26}$` encodes the alphabet but not the width. The two
high bits of the 130-bit encoding must be zero, which constrains the *first* character to
`0`–`7`; nothing in the character-class-only pattern expressed that. The gap was invisible
while the contracts had no producer — writing `decode_ulid` (roadmap 2.3) against them is
what surfaced the disagreement between the two layers.

## Impact

No released artifact is affected and no data exists yet. Left unfixed, an invalid identity
could have been persisted by any producer that formats ids by hand instead of calling the
identity library, and surfaced as a decode failure far from its origin — the class of
defect the record contracts exist to prevent. Hence medium, not low: it defeats a
validation boundary rather than merely permitting an odd value.

## Fix / workaround

Tighten the pattern to `^[0-7][0-9A-HJKMNP-TV-Z]{25}$` so the record contract and
`mycelium.sdk.identity.decode_ulid` accept exactly the same set. No workaround was needed
in the interim (no producers existed).

## References

- Fixing PR: #16 (roadmap 2.3)
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [ADR-0005](../../../adr/0005-adopt-in-repo-identity-library.md),
  [ADR-0004](../../../adr/0004-adopt-pydantic-v2-record-contracts.md), spec 03 §2
