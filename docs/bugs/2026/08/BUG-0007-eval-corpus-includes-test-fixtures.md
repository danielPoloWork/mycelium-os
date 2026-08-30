---
id: BUG-0007
title: the evaluation corpus includes test fixtures, so an unanswerable case is answered and G4 fails
status: open
severity: medium
reporter: internal
discovered: 2026-08-30
affected-versions: "0.2.0 and unreleased (introduced by PR #24, roadmap 2.11)"
fixed-in: ""
---

# BUG-0007: the evaluation corpus includes test fixtures, so an unanswerable case is answered and G4 fails

## Summary

`mycelium eval` scores against whatever the snapshot contains, and building this repository
compiles *every* Markdown file in it — including `tests/fixtures/determinism/knowledge/`,
a synthetic corpus written to exercise the compiler. One of those fixtures uses the word
"broker", which answers the unanswerable case `q-0019` ("kafka zookeeper broker rebalance").
Gate G4 (abstention) consequently reports a 25 % false-answer rate against a 5 % limit,
for the lexical retriever, on the current corpus.

## Environment

- **Affected versions:** since PR #24 (roadmap 2.11) wrote the case set. Present in v0.2.0.
- **Toolchain / platform:** any.
- **Configuration:** none — a repository with no `knowledge/` directory has its whole tree
  scanned (spec 02 §3), which is the documented behaviour and the reason this repository is
  its own corpus.

## Reproduction

```text
mycelium build .
mycelium eval --set eval/cases.jsonl
  [FAIL] G4 Abstention: false-answer rate 25.00% on 4 unanswerable case(s); limit 5%
```

The single false answer:

```text
q-0019: 'kafka zookeeper broker rebalance' -> 1 hit
    tests/fixtures/determinism/knowledge/verified/architecture.md#event-bus/0  (8.372)
      matched 'broker': "...messages between components without a broker..."
```

## Expected vs. actual

- **Expected:** an `unanswerable` case asks about vocabulary the *documentation* does not
  contain, and the system abstains. That is the behaviour G4 exists to protect.
- **Actual:** test data is indexed alongside documentation, so a fixture written to exercise
  chunking supplies vocabulary the documentation never had, and the system answers.

## Root cause

The corpus was never scoped. Roadmap 2.11 defined the case set against "our own docs" and
ran it against a snapshot of the whole repository, which by then (roadmap 2.10, PR #23) also
held a fixture corpus under `tests/`. Both are Markdown, so discovery cannot tell them apart
— it excludes dot-directories and nothing else.

It went unnoticed because **CI does not run the evaluation gates yet**: there is no `eval`
job in `ci.yml`, and wiring G1–G6 into CI is roadmap 3.7. The failure was found by roadmap
3.3, which had to run the harness by hand to decide gate G2.

## Impact

Medium. Nothing a user of the product experiences is wrong: the compiler, the store, and
retrieval all behave correctly, and a user's own repository has no reason to contain our
fixtures. What is wrong is our *measurement of ourselves* — one of twenty judged cases is
scored against text that should not be in the corpus, so G4's number is not meaningful and
G3's future regression baseline would inherit the same distortion.

## Fix / workaround

Not fixed here: this is a question about what the evaluation corpus *is*, and answering it
by editing a judged case would be tuning the benchmark to the corpus — the move D-010
explicitly warns against. Filed as **roadmap 3.10**, to be decided with the eval-scoping and
CI-gate work at 3.7. The options on the table:

1. an exclusion setting under `[project]` (new surface, and useful to any repository whose
   tree carries sample data);
2. evaluating against a staged copy of the documentation set, the way roadmap 3.3's
   measurement did by hand;
3. moving the determinism fixtures somewhere discovery does not reach (a dot-directory),
   which costs the fixture corpus its readability as ordinary Markdown.

Until then the number is reported honestly rather than suppressed: ADR-0017 states the
lexical baseline's 25 % alongside hybrid's 100 %, and neither is presented as a pass.

## References

- Discovering PR: #33 (roadmap 3.3)
- Introduced by: #24 (roadmap 2.11); fixture from #23 (roadmap 2.10)
- Related: [ADR-0013](../../../adr/0013-adopt-the-evaluation-harness.md),
  [ADR-0017](../../../adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  spec 04 §7.3 (gate G4), D-010
