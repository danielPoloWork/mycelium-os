# ADR-0031: Refuse three re-rankings, and name what the ranking failure actually is

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §3, §7.1, §7.3
- **Related:** [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (the split that caught this), [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md); D-010; roadmap 3.18

## Context

Roadmap 3.18 opened on a measurement D-010 does not let this project shrug at: on the second
corpus the **grep incumbent wins**. On its release set, nDCG@10 0.471 against our 0.280, MRR
0.433 against 0.205 — while we win Recall@50 (0.714 against 0.679) and latency (14 ms against
195). "If Mycelium OS does not visibly beat grep on these tasks, the correct response is to
fix the product, not the benchmark."

Winning recall and losing precision says the right passages are in the candidate set and come
back below the wrong ones: a **ranking** failure. Looking at what actually comes back first on
the dev set says what kind:

```text
u-0007 'what does resolution mean'      1. [  8t code ] resolution.md#resolution-strategy/1
u-0006 'uvx'                            2. [  3t code ] guides/tools.md#running-tools/1
u-0004 'what is a workspace'            1. [ 18t prose] internals/metadata.md#…/2
```

Three-, eight-, eighteen-token fragments — many of them code blocks — above the paragraphs
that answer. **BM25 normalises by document length, and our "documents" are chunks of wildly
different sizes.** A three-token code fence containing the query term has maximal term density,
so it wins. On our own corpus, which is long prose sections, the effect barely shows; on task
documentation full of short command blocks it dominates. SQLite's `bm25()` exposes column
weights and not `b`, so the normalisation itself is not ours to turn down.

## Decision

**Three candidate re-rankings were measured on the dev sets, and all three are refused.**
Nothing in the query path changes.

| dev set | baseline | section:max | length ≥ 60 | length ≥ 120 | coverage-first | grep |
|---|---:|---:|---:|---:|---:|---:|
| ours | 0.546 | **0.575** | 0.493 | 0.484 | 0.518 | 0.457 |
| uv | 0.403 | **0.444** | 0.573 | **0.636** | 0.399 | 0.576 |

- **A length prior** — damp chunks below *n* tokens — is refused for trading one corpus for
  the other: at 120 tokens it takes the second corpus from 0.403 to 0.636 and ours from 0.546
  down to 0.484. The reason is not tuning: **short chunks are sometimes the answer.**
  `## License` followed by one line naming the licence is 24 tokens and answers "what licence
  is this" completely. Length cannot tell an answer from a fragment, which is the same shape of
  finding as ADR-0025's similarity floor and ADR-0028's approximate index.
- **Coverage-first** — prefer passages containing more *distinct* query terms, then BM25;
  coordination-level matching, and what grep ranks by — is refused for losing on **both**
  corpora (ours 0.575 → 0.518, uv 0.444 → 0.436 over section:max). Whatever grep is doing
  right, it is not simply term coverage.
- **Section aggregation** — one section competes once, represented by its best-scoring chunk —
  is the interesting one. It improves **both** dev sets with no free parameter, which is
  exactly the profile of a change that should ship. It was implemented, and then **gate G3
  failed it on the held-out release set**: `conceptual` 0.3770 → 0.1836 (**−51.3 %**), `fact`
  −14.6 %. It is reverted.

**The dev/release split caught an overfit on its first real use, and that is the finding to
keep.** A change that improved both dev sets, carried no constant, and had a principled story
was still fitting the sets it was developed against. Without the split it would have shipped
with a table of improvements attached.

## Alternatives Considered

- **Ship section aggregation anyway**, since both dev sets improve and the release regression
  is concentrated where judgments are still chunk-exact. Rejected: that is deciding a gate's
  verdict is wrong because it is inconvenient. The suspicion is recorded below as work, not
  used as an exemption.
- **Re-judge the release cases so the change passes.** Rejected outright, and
  `tools/check_frozen_release_sets.py` would refuse the commit — which is what it is for.
- **Tune the BM25 column weights** (title 3.0 / heading_path 2.0 / body 1.0). Not measured
  here and deliberately not touched: weights are three more constants, and the diagnosis says
  the problem is the length normalisation the weights do not control.
- **Merge short code chunks into their surrounding prose at chunk time.** Rejected for this
  item: it moves every chunk boundary in every corpus, re-blesses the determinism golden, and
  invalidates judged anchors — a chunking decision that cannot be smuggled in as a ranking fix
  (ADR-0007, ADR-0023).

## Consequences

- **The product still loses to grep on the second corpus, and 3.18 stays open.** The item
  asked for a fix; three were measured and none survived. Ticking it would make the roadmap's
  boxes mean less than they say.
- **The diagnosis is now specific enough to work from**: not "ranking is bad" but "BM25 length
  normalisation over heterogeneous chunk sizes, which SQLite's `bm25()` will not let us damp,
  and which a length threshold cannot repair because short chunks are sometimes the answer".
- **A hypothesis worth testing next, in order**: index and score at the *section* level — a
  second FTS table whose documents are sections — so length normalisation compares comparable
  units, then return the best chunk of the winning section. That is an indexing change rather
  than a re-rank, and it makes the length problem structural rather than heuristic.
- **One interaction must be disentangled before section aggregation is proposed again.**
  Returning a different chunk of the *right* section scores zero against a chunk-exact
  judgment, and 3.17 converted only the judgments the documents justified. Whether the release
  regression is retrieval or bookkeeping is answerable — by judging those cases from the
  documents first, and re-testing afterwards — and answering it in that order is the only way
  the answer means anything.
- `tools/measure_ranking.py` re-runs the table above against the dev sets, so the next attempt
  starts from evidence rather than from this ADR's prose.

## References

- Spec 04 §3 (candidate generation), §7.1 (dev/release split), §7.3 (gate G3); D-010
- [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) — the split
- `tools/measure_ranking.py` — the dev-set table, re-runnable
