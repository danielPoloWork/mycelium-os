---
id: BUG-0014
title: gate G3 compares against a baseline taken on a different corpus, failing a build that changed no retrieval code
status: fixed
severity: medium
reporter: internal
discovered: 2026-08-31
affected-versions: "unreleased (introduced by PR #37, roadmap 3.7)"
fixed-in: "0.3.0"
---

# BUG-0014: gate G3 compares against a baseline taken on a different corpus, failing a build that changed no retrieval code

## Summary

Gate G3 ("no regression") compared the current run's per-slice metrics against a committed
baseline without asking whether the two runs had measured the same corpus. Because this
repository's documentation *is* its corpus, any PR that adds a document moves the metrics,
and G3 reported a regression for a change that touched no retriever, no ranker, and no
index. `main` is red for exactly this reason.

## Environment

- **Affected versions:** unreleased; introduced by PR #37 (roadmap 3.7), never released.
- **Configuration:** any repository whose corpus grows between the run that blessed the
  baseline and the run being gated — which is every repository under active authorship.

## Reproduction

```text
mycelium eval . --bless           # baseline blessed on 568 chunks
# write an ADR, a journal entry and a bug record; nothing else
mycelium build . && mycelium eval . --gate
  FAIL G3 No regression: conceptual -7.6%, fact -3.2%, injection -13.9%
```

## Expected vs. actual

- **Expected:** a no-regression gate compares comparable runs. Retrieval quality is a
  property of the retriever *and* the corpus; hold one fixed to measure the other.
- **Actual:** the corpus was a free variable, so G3 answered a question nobody asked —
  "did the numbers move?" — and blocked the merge whenever the answer was yes.

## Root cause

The baseline recorded the metrics and the retriever, and nothing about what was measured.
That is enough to compare two retrievers, which is what G2 does, but not enough to compare
two runs across time. The gate had no way to distinguish "the ranker got worse" from "there
are 55 more chunks to rank".

An earlier attempt to fingerprint the corpus with `manifest.artifact_digests["chunks"]` was
worse than useless: that digest folds chunk *records*, which carry a `doc_id`, and an
unpinned checkout mints a fresh ULID per document on every build — so it never matched, on
any machine, and G3 would have silently stopped enforcing forever.

## Impact

Medium. No wrong answer reaches a user, but a gate that fails on unrelated changes is a
gate maintainers learn to override, which costs more than the gate was worth. It also left
`main` red, so the next PR inherits a failing required check.

## Fix / workaround

The baseline records a **content fingerprint** of the corpus it was taken on: the fold of
the sorted `chunk_digest` values, which are a function of chunk content alone and carry no
identity. G3 then does one of two things, and says which:

- the fingerprint matches — the corpus is the one the baseline measured, so G3 **enforces**;
- it does not match — G3 **reports** the deltas, names them as not comparable, and points
  at `mycelium eval --bless` for when the corpus is the one you mean to measure.

That the fingerprint is identity-free is a tested property: two fresh builds of the same
unpinned tree, each minting its own ULIDs, agree.

## References

- Fixing PR: #38
- Introduced by: #37 (roadmap 3.7)
- Related: [ADR-0021](../../../adr/0021-scope-the-corpus-and-gate-the-evaluation.md)
