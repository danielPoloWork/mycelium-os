# 2026-09-09 — the gate that could not have been wired (roadmap 4.40)

- **Session scope:** roadmap 4.40 — gate G2 has no runner, and had not run for three
  milestones (spec 04 §7.3; D-013; ADR-0017/0064).
- **PR:** #91 (`feat/g2-runner-and-verdict-currency`). Follows #90 (4.39), merged as
  `db84cc5`.
- **Milestone 4:** 4.40 done; 4.41, 4.42 open, plus 4.43 filed here.

## The item's sketch did not survive the first thing I tried

4.40 proposed a step in `verify.py`'s `retrieval` mode that runs G2 when the model is
present. The obvious form of that is `mycelium eval --retriever hybrid --gate`, and it cannot
work: `--gate` exits non-zero when *any* gate reports `passed=False`, and `_gate_g2` reports
`passed=False` when hybrid does not earn the default — which is the shipped configuration.
Milestone 3's own exit gate says "lexical-only default is a legitimate G2 outcome". So the
step would have been red on every correct build.

That is not a gap in the wiring. It is why no wiring was ever possible, and it reframed the
whole item: **G2's boolean and G2's runner are two different problems**, and only the second
is 4.40's. The first belongs to 4.41, which was filed to be answered while no candidate is
pending; its line now carries the finding rather than my inventing a fifteenth item for it.

## What actually goes stale

G2's verdict is not a number, it is a sentence: *hybrid has not earned the default against
**this** lexical leg, on **these** corpora, under **these** judgements*. Every qualifier in
it is checkable without the embedding model. The numbers are not — ADR-0017 declares the
embedder non-deterministic across platforms and runtimes, so a float taken on a GitHub runner
is not comparable with one taken here.

That splits cleanly into what each machine can honestly do:

| tier | needs the model | fails on |
|---|---|---|
| currency | no | the retrieval identity, the shipped default, a dated corpus, a judged set |
| reproduction | yes | a per-set **verdict** that flipped |

CI runs the first. This machine runs both. Neither fails because hybrid lost.

## The repair the check turned out to need

Before any of it could work I had to check what the retrieval configuration's own record
says, and it says it from memory. `MyceliumRetriever.config` — the thing a run manifest
carries so an old result can be read — held:

```python
"weights": "title=3.0,heading=2.0,body=1.0,ancestors=0.5",
```

A hand-typed string, in two places, sitting beside the numbers it claims to describe. And
`stopwords` was recorded as `len(STOPWORDS)`, so swapping one function word for another
leaves it identical. **Roadmap 4.42 is a pending change to exactly those weights**: a
currency check keyed on that record would have looked current straight through the change it
exists to catch.

So the string is rendered from `_SURFACE_WEIGHTS` now, `retrieval_identity()` digests
membership rather than counts, and every field is read at call time — which is what makes the
guarantee testable: move a weight in a test and the digest moves. It renders byte-identically
to what the literals held, so no manifest digest moved and no baseline was re-blessed.

## Should CI fetch the model?

The item said to argue this rather than assume it, so: the cost is **not** the reason. I
measured it — 127.6 MB of model files, and the six-set measurement runs in 12–25 s here,
cacheable to roughly nothing after a first run. The reason is comparability. A verdict
computed on a runner is a different measurement from the one on record, and recording CI's
would make the verdict a property of the runner image. Reversing that needs one thing
measured first — whether the per-set verdicts agree across two machines — and that
measurement needs a runner, so it is work rather than a line.

`ours` gets the same treatment for a smaller reason: this repository is its own corpus, so
its content fingerprint moves on every PR, including this one. It is measured, recorded, and
reported — never gated. That is the distinction G3 already makes, for the same reason.

## What widening the ladder test found

4.40 asked that `test_verify_ladder.py` keep the new step and the workflow in agreement. The
step is a script, and the test read only `mycelium` invocations — so widening it was
unavoidable, and widening it immediately said CI runs two gates the local loop does not:
`build_ingested_corpus.py --check` and `build_ingested_cases.py --check`, the ingestion
reproductions. ADR-0059's defect, still alive in a job it had not looked at.

Writing an exemption for drift discovered *by the test whose job is to catch drift* was not
defensible, so both joined the `code` plan: +79 s locally, measured and stated. The test was
run against a tree with the G2 step removed from the plan, and fails there — the check that
it bites.

## The verdict, re-measured

Unchanged in shape from ADR-0064 a day earlier: `ours/release` passes, `uv/release` and
`uv-ingested/release` fail, so the release rows leave the default at `lexical` and hybrid
keeps the burden of proof. The individual numbers *did* move — `uv/dev` lexical 0.6727 →
0.6092, which is 4.39's ten new cases — and that is precisely the drift the record exists to
date.

## Filed on the way

**4.43:** `tools/` is neither linted nor type-checked. The plan and CI both run
`ruff check src tests` and `mypy --strict src`, so the eighteen files that build the corpora,
carry the judgements and now decide G2's currency in CI are checked by review alone.
Measured: 1 ruff error, 184 mypy errors — and almost all of the second number is one cause,
`mycelium` shipping no `py.typed`, which also means the package advertises no types to the
consumers of the record contracts it is built on.
