---
id: BUG-0005
title: one unmatched word returns no results, because FTS5 combines terms with implicit AND
status: fixed
severity: high
reporter: internal
discovered: 2026-08-30
affected-versions: "unreleased (introduced by PR #19, roadmap 2.6)"
fixed-in: "0.2.0"
---

# BUG-0005: one unmatched word returns no results, because FTS5 combines terms with implicit AND

## Summary

`fts_query` quoted each query term and joined them with spaces. FTS5 reads that as a
conjunction, so a single word the corpus does not contain reduced the entire query to zero
results. Every natural-language question — the primary use case — returned nothing, through
the CLI, through MCP, and through the evaluation harness alike.

## Environment

- **Affected versions:** unreleased — introduced by PR #19 (roadmap 2.6), never in a
  released artifact.
- **Toolchain / platform:** any; SQLite FTS5 query semantics.
- **Configuration:** none — the behaviour was unconditional.

## Reproduction

Against a corpus containing this repository's own documentation:

```text
'license'                                  -> 5 hits
'license apache'                           -> 4 hits
'license apache nonexistentword'           -> 0 hits
'what license does the project use'        -> 0 hits
```

The regression test is
[`test_a_query_term_the_corpus_lacks_does_not_zero_the_query`](../../../../tests/test_store.py).

## Expected vs. actual

- **Expected:** a partial match is a result to be *ranked*. BM25 exists to order documents
  by how well they match; a query mentioning one absent word should rank the passages
  matching the other words, not return nothing.
- **Actual:** any absent term emptied the result set, so the more naturally a user phrased
  a question, the more likely they got silence.

## Root cause

`fts_query` produced `"what" "license" "does" "the" "project" "use"`. FTS5's implicit
operator between adjacent terms is `AND`, so the expression required *every* term to appear
in the same chunk. The intent had been to quote each term so that FTS5 operators inside
untrusted query text are matched as words rather than executed (D-017) — that part was
right; the missing piece was stating the operator between them.

The defect survived 2.6's tests because they used short queries whose terms all appear
together, and 2.8's and 2.9's tests inherited those queries. It was found by roadmap 2.11,
when the evaluation harness ran realistic questions for the first time and every one of
them scored zero — exactly the failure D-010 says evaluation exists to expose.

## Impact

High: the product's headline interaction — an agent asking a question in natural language
and receiving cited passages — returned nothing. Search through the CLI and both MCP tools
were affected. Nothing was released with this behaviour, and no data was corrupted; the
damage would have been to first impressions, which for a tool sold on time-to-first-value
is the whole product.

## Fix / workaround

Combine terms with `OR`, so BM25 ranks partial matches, and keep every term quoted so query
text stays data rather than syntax. `fts_query(..., match_all=True)` preserves conjunction
for callers that want precision — the query planner's exact/phrase routes (spec 04 §2) will.

## References

- Fixing PR: #24 (roadmap 2.11)
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [ADR-0013](../../../adr/0013-adopt-the-evaluation-harness.md),
  [ADR-0008](../../../adr/0008-adopt-sqlite-store-behind-a-store-protocol.md), spec 04 §3,
  D-010 (the grep baseline that made this visible)
