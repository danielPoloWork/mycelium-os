# 2026-09-02 — ten refusals, and a ceiling (roadmap 4.8)

- **Session scope:** roadmap 4.8 — the product loses to the grep incumbent on the second
  corpus; ADR-0031's ordered plan, both steps.
- **PR:** #60 (`test/bound-the-section-unit`). Follows #59 (4.9), merged as `d8a842b`.
- **Milestone 4:** 4.1–4.7, 4.9, 4.10 done; **4.8 stays open** for a second time, and 4.11
  is filed out of it.

## The plan ADR-0031 left, executed in order

ADR-0031 refused three re-rankings and wrote down what to do next, in order: first settle
whether the release regression was retrieval or chunk-exact bookkeeping, then test scoring at
the section level as an *indexing* change. Roadmap 3.17 did the judging. This session did the
re-testing and then the hypothesis.

**Step one closed against us, which is the useful direction.** Re-measured after the
re-judging, `section:max` still fails gate G3 on the second corpus: `conceptual` 0.3770 →
0.1836, **−51.3 %** — the same number ADR-0031 recorded before thirteen judgments were
re-scoped. The suspicion that a correct retrieval was scoring zero against a chunk-exact
judgment is answered, and the excuse is gone.

## Six forms of one hypothesis

The section index is real: an FTS5 table whose documents are sections, built in memory from
the store's own chunks. That choice mattered more than it looks — the hypothesis cost an
afternoon instead of a schema version, and it failed.

- **best-chunk representative** (ADR-0031's literal wording) — ours/dev 0.541, uv/dev 0.564;
  fails G3 on both release sets.
- **opening-chunk representative** — the best of the family on the second corpus (uv/release
  0.451 against grep's 0.471, every slice up); `exact` −33.7 % on ours.
- **section-ordering that deletes nothing** — written after the case-level diagnosis said the
  damage was *deletion*: collapsing a section to one chunk drops its other chunks out of the
  ranking, and a judgment naming one of those then scores zero. Ordering instead of collapsing
  made it worse (`exact` −48.2 %), because a whole competing section's chunks now sit above the
  chunk that ranked first.
- **RRF-fused with the chunk leg** — keeps both claims, invents no constant. Both dev sets
  improve; both release sets fail.
- **opener only when the opener is itself evidence** — the last one, and the interesting one.

## The one that passed the gate, and was refused

`open-if-candidate` **passes gate G3 on both release sets** — no slice regressed on either —
improves the second corpus 22 % and lifts its R@10 from 0.500 to 0.607. It is refused, and
the reason is one case on our own dev set:

```text
query: BEGIN IMMEDIATE transaction

  #decision/0   (14 tokens)  ← returned at rank 1
      Decision
      Publication order. One writer, one transaction, one swap::

  #decision/1   (92 tokens)  ← judged, demoted
      acquire .mycelium/lock                 # O_CREAT|O_EXCL; heartbeat = mtime
      BEGIN IMMEDIATE                        # readers keep the old committed state (WAL)
```

The opener qualified as "evidence" on the strength of the incidental word *transaction*, and
displaced the block containing the phrase the query asked for. 0.956 → 0.169.

That is the disease 4.8 exists to cure, produced by the cure. A short fragment outranking the
passage that answers is exactly what ADR-0031 diagnosed; it arrived here through the
representative rule rather than through BM25's normalisation, which makes it a different
route to the same defect and not a different defect.

**And the gate was blind to it**, because the case lives in the dev set G3 does not read.
ADR-0027 built the split to catch a change fitted to the sets it was developed on, and
ADR-0031 recorded it doing that. This is the mirror image: a real regression sitting in the
half the gate ignores. Two independent reasons the split earns its keep, in opposite
directions.

## The bound

Every member of the family wins one corpus and loses the other, which invites the planner
argument — choose the unit per query. That is answerable without building a planner: take the
per-case best of every strategy. No rule can beat it, because it chooses with foresight the
query does not carry.

| set | chunk unit | best section unit | oracle | vs grep |
|---|---:|---:|---:|---:|
| uv/dev | 0.403 | 0.601 | 0.601 | +0.025 |
| uv/release | 0.280 | 0.486 | 0.486 | **+0.015** |

A 3 % margin over the incumbent, unreachable in practice, on the corpus the item is about.
**The unit of indexing is not where this gap closes** — and that is now measured rather than
argued. The per-case winners agree: the section unit takes all three `conceptual` cases and
four of seven `fact`, a distribution with no query-shape rule in it. Whether a section's
answer sits in its first chunk or its fifth is a property of how the author wrote it.

## The framing was too kind

The item says the product loses to grep on the second corpus. It can beat it several ways:
`grep-formula` 0.511, `length>=120` 0.503, `length>=60` 0.481, against 0.471. Every one of
them fails G3 on *our* corpus. The hard part was never beating that incumbent — it is beating
it without paying for it on the corpus we already win, and ten strategies across two ADRs
have not managed both.

One of those ten is worth its own line. **Borrowing grep's actual ranking function —
`(distinct terms, total occurrences)`, no length normalisation anywhere — scores 0.003 on
ours/release.** It is not the `coverage-first` ADR-0031 refused, which kept BM25 as its
tie-break and so kept the length bias in the second key. Applied to a candidate set BM25 has
already selected, raw occurrence counts promote long chunks with incidental repeats: the
incumbent's selection and its ranking are a package, and "just rank like grep" now has a
number attached instead of an intuition.

## Where this leaves 4.8

Open, a second time, and pointed somewhere specific. Every failure in both ADRs traces to
chunks of wildly unequal size — a three-token code fence competing with a four-hundred-token
section — and no ranking rule repairs a unit that was already wrong when ranking saw it.
ADR-0031 named that change and set it aside as a chunking decision that could not be smuggled
in as a ranking fix. It is now the hypothesis left standing, filed as **4.11**, with its costs
stated rather than discovered: it moves every boundary in every corpus, re-blesses the
determinism golden, and invalidates every judged anchor that is not section-scoped — which
turns ADR-0029's durability argument from a nicety into the thing that makes 4.11 affordable.

No product code changed this session. `tools/measure_ranking.py --release --oracle` re-runs
every number above, which is the point: the next attempt starts from the numbers, not from
this file.
