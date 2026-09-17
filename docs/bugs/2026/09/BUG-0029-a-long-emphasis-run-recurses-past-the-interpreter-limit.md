---
id: BUG-0029
title: forty kilobytes of asterisks recurse past the interpreter's limit, killing `mycelium ingest`
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-17
affected-versions: ">=0.2.0,<0.6.0"
fixed-in: 0.6.0
---

# BUG-0029: forty kilobytes of asterisks recurse past the interpreter's limit, killing `mycelium ingest`

## Summary

A Markdown document containing twenty thousand asterisks, one letter, and twenty thousand
more asterisks nests emphasis ten thousand levels deep. markdown-it parses it; building
the syntax tree from the tokens recurses once per level and raises `RecursionError`. In
the build that exception is caught by the per-document catch-all and the file is
quarantined — after thirteen seconds, with the interpreter's error as the reason. In
`mycelium ingest` nothing catches it: the command dies with a traceback and writes no
quarantine record.

## Environment

- **Affected versions:** every release with the Markdown adapter (roadmap 2.4, v0.2.0) up
  to but not including 0.6.0
- **Toolchain / platform:** any; the recursion limit is CPython's default 1000
- **Configuration:** defaults

## Reproduction

Found by the 6.3 security review's pathological-input probes; pinned by
`tests/test_security_controls.py::test_ingest_quarantines_the_emphasis_run_instead_of_dying_on_it`
and, at fixture size, by `tests/fixtures/injection/knowledge/candidate/emphasis-recursion.md`.

```text
$ python -c "open('emphasis.md','w').write('# E\n\n' + '*'*20000 + 'a' + '*'*20000)"
$ mycelium ingest emphasis.md
... RecursionError: maximum recursion depth exceeded        (exit 1, no quarantine record)
```

## Expected vs. actual

- **Expected:** a typed, per-document refusal naming the document, in both lanes, with a
  quarantine record the operator can find.
- **Actual:** the build quarantines it by the luck of a catch-all, slowly and with an
  interpreter error as the reason; the ingest lane crashes.

## Root cause

markdown-it bounds *structural* nesting with its `maxNesting` option (100), but emphasis
is paired after tokenization and is not counted, so a delimiter run nests without limit.
`SyntaxTreeNode` then recurses per nesting level. The ingest pipeline catches only
`IngestError` (spec 02 §5's typed failures), and the Markdown parser plugin converts only
`MarkdownError` and `FrontmatterError` into a `ParseError`, so a `RecursionError` from
inside the adapter escaped both.

## Impact

Denial of service of the ingest command by one file, and an untyped, slow refusal in the
build. Medium: the crash is total for the command and leaves no record, but nothing is
damaged and the file is the operator's own input.

## Fix / workaround

Fixed at roadmap 6.3 (ADR-0119): the adapter measures the token stream's deepest nesting
before building the tree and refuses a document over `MAX_NESTING` (100, the parser's
own number; the deepest document in the three corpora nests six) as a `MarkdownError`,
with a guard behind it that turns a `RecursionError` from the tree builder into the same
typed error. Both lanes quarantine it by name in milliseconds.

## References

- Fixing PR: #154 (roadmap 6.3, `feat/security-review-pass`)
- `CHANGELOG` entry: `[Unreleased]` → *Security*
- Related: ADR-0119; `docs/security/audit-2026-09-17-review-pass.md` finding F8;
  ADR-0033 (the hostile suite, which bounded the same shape for HTML and not for Markdown)
