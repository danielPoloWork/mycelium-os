---
id: BUG-0028
title: the private-key secret rule scans quadratically, so a file of PEM headers stalls ingestion
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-17
affected-versions: ">=0.4.0,<0.6.0"
fixed-in: 0.6.0
---

# BUG-0028: the private-key secret rule scans quadratically, so a file of PEM headers stalls ingestion

## Summary

The `private-key-block` rule of the ingestion secret scan was one regular expression from
armour header to armour footer with a lazy body. A header with no footer after it makes
the engine scan to the end of the text and fail; twenty thousand headers make it do so
twenty thousand times. A 640 KB text of nothing but `-----BEGIN RSA PRIVATE KEY-----`
lines had not finished scanning after sixty seconds.

## Environment

- **Affected versions:** every release with the secret scan (roadmap 4.6, v0.4.0) up to
  but not including 0.6.0
- **Toolchain / platform:** any
- **Configuration:** the scan always runs, whatever `[ingest] redact_secrets` says, on
  every ingested document, every imported conversation and every paste the chats
  segmenter sends

## Reproduction

Found by the 6.3 security review's regex probes; pinned by
`tests/test_security_controls.py::test_twenty_thousand_pem_headers_scan_in_seconds_and_each_is_a_finding`.

```text
>>> from mycelium.ingest import scan_text
>>> scan_text("-----BEGIN RSA PRIVATE KEY-----\n" * 20_000)   # does not return in 60 s
```

Every other rule scanned a megabyte of its own worst case in under a second.

## Expected vs. actual

- **Expected:** the scan is linear in the text; twenty thousand headers are twenty thousand
  findings in well under a second.
- **Actual:** the scan is quadratic in the number of unterminated headers and stalls.

## Root cause

`[\s\S]*?` between header and footer. A lazy quantifier is linear when the footer exists,
because it stops at the first one; when it does not, the engine tries every extension to
the end of the text before giving up on that header, and `finditer` then moves to the
next header and does it again. The rule also had a second defect the fix removes: a key
whose footer was truncated matched nothing at all, so a truncated key went into the tree
unflagged and unredacted.

## Impact

Denial of service of `mycelium ingest`, `mycelium chats import` and the synthesis
egress by one file, before anything is stored. No data is damaged. Medium: total for the
command, local to one machine, and the file is the operator's own input.

## Fix / workaround

Fixed at roadmap 6.3 (ADR-0119): a rule may now carry a `closer`; the PEM rule matches
the header alone and `scan_text` extends the span forward once, line by line, to the
first footer or the last line that could sit inside a PEM block. Twenty thousand truncated
keys scan in under a second and each is a finding; twenty thousand lone headers scan in the
same time and none is, because a header with nothing under it is documentation of a key —
this record quotes one — and the scan's doctrine is precision. Workaround before 0.6.0:
none short of removing the file.

## References

- Fixing PR: #154 (roadmap 6.3, `feat/security-review-pass`)
- `CHANGELOG` entry: `[Unreleased]` → *Security*
- Related: ADR-0119; `docs/security/audit-2026-09-17-review-pass.md` finding F7;
  ADR-0037 (the scan's design)
