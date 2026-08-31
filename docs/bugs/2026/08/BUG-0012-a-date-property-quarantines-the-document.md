---
id: BUG-0012
title: a date in a non-contract frontmatter property quarantines the whole document
status: fixed
severity: high
reporter: internal
discovered: 2026-08-31
affected-versions: "0.1.0, 0.2.0 (introduced by PR #17, roadmap 2.4)"
fixed-in: "0.3.0"
---

# BUG-0012: a date in a non-contract frontmatter property quarantines the whole document

## Summary

`Frontmatter.properties` is typed `dict[str, JsonValue]`, and pydantic's `JsonValue`
rejects `datetime.date`. YAML reads an unquoted `2026-08-29` as exactly that, so a property
as ordinary as Obsidian's `created:` raised a validation error, the build quarantined the
document, and its content left the index entirely.

This project's own bug ledger disappeared from its own corpus that way: every record in
`docs/bugs/` carries `discovered: <date>`, so all nine were quarantined and none of them
was searchable.

## Environment

- **Affected versions:** since PR #17 (roadmap 2.4). Present in v0.1.0 and v0.2.0.
- **Configuration:** none. Any document with a date-valued property outside the closed
  contract is affected.

## Reproduction

```text
mycelium build .
  document quarantined: docs/bugs/2026/08/BUG-0001-….md (ValidationError: 1 validation
  error for Frontmatter properties.discovered — input was not a valid JSON value
  [input_value=datetime.date(2026, 8, 29)])
```

## Expected vs. actual

- **Expected:** D-022 promises a vault's own properties are *preserved* and never
  machine-interpreted. A date is the most ordinary vault property there is.
- **Actual:** the document was removed from the corpus. Quarantine is the right response to
  a document whose *identity* cannot be read (spec 02 §11); it is a wild over-reaction to
  a property the tool had promised not to interpret.

## Root cause

Contract fields each have a coercion helper that warns and drops on malformed input — the
module's stated philosophy is that "a human's typo in `tags` must not stop the build".
Non-contract properties had no such helper: they were passed to the model raw, so the
model's own type constraint became a build-stopping error.

It went unnoticed because no test fixture used a date property and the ledger was excluded
from the case-building corpus. It surfaced when roadmap 3.7 scoped the *evaluation* corpus
and the ledger came into it for the first time.

## Impact

High. Whole documents leave the index for a valid, common input, with a warning rather than
a failure — so a corpus can be silently incomplete, and every measurement taken over it is
taken over the wrong corpus. This project's own eval numbers were computed without its bug
ledger until this was fixed.

## Fix / workaround

Non-contract property values are coerced into JSON-representable form: dates, times, and
timestamps become their ISO 8601 spelling — which is what the author wrote before YAML
typed it — and anything else with no JSON form is dropped with a warning naming the key.
Preserving nothing is still better than losing the document that carried it.

Workaround before the fix: quote the date.

## References

- Fixing PR: #37 (roadmap 3.7)
- Introduced by: #17 (roadmap 2.4)
- Related: [ADR-0006](../../../adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md),
  [ADR-0004](../../../adr/0004-adopt-pydantic-v2-record-contracts.md), D-022
