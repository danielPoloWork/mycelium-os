# ADR-0054: Gate the query, not the documents

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.23 (this item), 4.19 (where it was filed), 4.25, 4.26; RFC-0001;
  spec 04 §§3, 7; D-010; NFR-5;
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) (amended here),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md)

## Context

ADR-0048 added a stem column beside each surface column and gated the stems behind a
surface hit, with one MATCH expression:

```text
{surface} : (terms) AND ( {surface} : (terms) OR {stem} : (stems) )
```

It shipped because the alternative failed a gate: Porter over-stems — `organization` and
`organ` reduce to the same token — and without the leading clause one word of judged
`unanswerable` case `r-0014` conflates with a word this repository uses freely, so the case
is answered out of a corpus that holds nothing of the sort. Gate G4 counts that as the false
answer it is. (The case is named by id and its words are not quoted, for the reason ADR-0048
gives: this repository's documentation *is* its corpus, so quoting the query would make it
answerable and fail G4 on the prose.)

Roadmap 4.23 was filed from the other side of that trade: *"a query whose every word is
inflected differently gets silence."* It proposed closing the gap with something the index
does not carry — document frequency of a stem against its surface forms, or a query-side
morphological signal — and warned that both are heuristics with thresholds.

**Measuring it first changed what the item was about.** Two findings, from the four judged
sets on today's corpora:

1. **The silence costs nothing measurable.** Every judged case with no literal foothold —
   ten of them across ours/dev, ours/release, uv/dev and uv/release — is an `unanswerable`
   case. Not one *answerable* case is blocked by the missing reach. The gap the item was
   filed to close has no headroom on the judged evidence.
2. **The expression held two rules, and only one of them was buying the safety.** The
   leading clause says both "this *query* must have a literal footing in the corpus" and
   "every *candidate document* must carry one of the query's words as written". Abstention
   needs only the first. The second was excluding documents that share a stem and nothing
   else — and *that* is where the headroom is.

So the item's premise was inverted: the reach worth having was not for footholdless
queries, it was for footholdless *documents* under queries that do have a foothold.

## Decision

**Split the two rules. The gate asks the corpus once; the search is open.**

```text
gate    {surface} : (terms)                              -- LIMIT 1, before the search
search  {surface} : (terms) OR {stem} : (stems)          -- no filter on candidates
```

`mycelium.store.foothold_query` builds the gate and `search_chunks` runs it as a
`LIMIT 1` probe under the caller's own filters; an empty probe returns no hits, which is
the same abstention ADR-0048 shipped. The probe is **threshold-free** — a word either
appears in the corpus as written or it does not — which is what makes it choosable on sets
too thin to settle a parameter (the objection roadmap 4.23 raised against its own two
proposals).

The gate is always *disjunctive*, even for a `match_all` caller: "did the author write any
of these words" is the abstention question, and "all of them, in one chunk" is a different
question that the search itself asks.

**`STEM_WEIGHT` moves 0.1 → 0.05, and this is the same balance rather than a new one.**
The old expression named the surface clause twice, which raised the surface contribution
above its nominal weight and left the stems relatively quieter than 0.1 suggested. With the
duplication gone the nominal weight is the effective one, and the dev sets locate the same
balance at half the number.

**A prefix query is not gated**, because it carries no stems: there is nothing for a
foothold to authorise, and `sign*` already generalises across suffixes (ADR-0048).

## What it costs, and the numbers

Developed on the dev sets, then read off the release sets. Every row re-runs with
`python tools/measure_ranking.py --release`, where `index: expand-gate <w>` is this
decision and `index: expand-pre 0.1` is what ADR-0048 shipped.

**Dev sets — where the weight was chosen.** nDCG@10, and the two-set sum that chose it:

| stem weight | ours/dev | uv/dev | sum |
|---|---:|---:|---:|
| ADR-0048 (`expand-pre` 0.1) | 0.5417 | 0.6527 | 1.1944 |
| gate 0.025 | 0.5307 | 0.6124 | 1.1431 |
| **gate 0.05** | **0.5496** | **0.6727** | **1.2223** |
| gate 0.075 | 0.5493 | 0.6727 | 1.2220 |
| gate 0.1 | 0.5533 | 0.6358 | 1.1891 |
| gate 0.15 | 0.5511 | 0.6358 | 1.1869 |

The curve is unimodal with its peak over 0.05–0.075. **0.05 and 0.075 are tied to within
0.0003**, which 32 dev cases cannot resolve — ADR-0044's finding applied to ourselves — so
the tie is broken by the margin to the nearest observed failure rather than by the third
decimal. At 0.09 and above, dev case `u-0007` ("what does resolution mean") loses its
definition — *"Resolution is the process of taking a list of requirements and converting
them to..."* — to a passage that merely contains "this **means** that", reached through the
correct inflection of a function word. 0.05 sits furthest from that edge. It is a 1.8×
margin, narrower than the 3.5× ADR-0048 had, and that is stated rather than smoothed.

**Release sets — read, never tuned against.** nDCG@10 and the per-slice view:

| set | ADR-0048 | this | Δ |
|---|---:|---:|---:|
| ours/release | 0.4982 | 0.4978 | −0.0004 |
| uv/release | 0.5483 | **0.5620** | +0.0137 |
| uv-ingested/release | 0.6469 | **0.6556** | +0.0087 |

Per slice, every row that moved at all:

| slice | ours before | after | uv before | after | uv-ingested before | after |
|---|---:|---:|---:|---:|---:|---:|
| `conceptual` | 0.4921 | 0.4929 | 0.8784 | 0.8784 | 0.8784 | 0.8784 |
| `exact` | 0.7593 | 0.7593 | 0.6505 | 0.6505 | 1.0000 | 1.0000 |
| `fact` | 0.4602 | 0.4585 | 0.4033 | **0.4306** | 0.5005 | **0.5180** |
| `relationship` | 0.2600 | 0.2600 | 0.8522 | 0.8522 | 0.8522 | 0.8522 |

Nothing regresses beyond a rounding wobble anywhere: ours/release `fact` reads −0.37 %,
inside G3's −2 % and on the set G3 reports rather than enforces. So **gate G3 enforces and
passes on both frozen corpora** — the first change measured against the headroom-free
baselines roadmap 4.22 blessed (ADR-0053), which is what makes the pass mean something.

The whole gain is in `fact`, the slice roadmap 4.25 has open as still the
incumbent's: the gap to `grep` on uv/release narrows from 0.093 to 0.066, and on the
ingested corpus from 0.036 to 0.019. It does not close, and 4.25 stays open. That the
movement is confined to one slice on all three corpora is itself worth reading — the
candidates this change admits are documents that share a word's inflection and nothing
else, which is what a "how do I do X" query has and a definitional one does not.

**Abstention is unchanged, and that is the point.** Results returned on each of the ten
judged `unanswerable` cases, where 0 is a correct abstention:

| case | ADR-0048 | open expansion | this decision |
|---|---:|---:|---:|
| eight footholdless cases | 0 | 0 | 0 |
| ours/release `r-0014` | 0 | **13** | 0 |
| uv/dev `u-0010` | 0 | **5** | 0 |

Open expansion — the same search without the gate — answers two out-of-domain queries out
of two corpora that hold nothing of the sort, through a stem that conflates one of their
words with a common one. The gate is what keeps that at zero, and G4 measures 0.00 % on all
three corpora.

**Latency.** The probe adds one `LIMIT 1` index read whose expression is a subset of the
search's own, so it touches pages the search is about to touch. Measured on this repository,
query p95 went 18 ms → 17 ms against a 150 ms budget; gate G5 is unmoved.

## Alternatives Considered

- **The item's own two proposals** — document frequency of a stem against its surface
  forms, or a query-side morphological relatedness signal. Not needed, and that is the
  finding rather than a dodge: both were designed to serve footholdless *queries*, and no
  judged answerable case is one. Both are also thresholded heuristics that would have to be
  calibrated on sets that cannot settle a third decimal (roadmap 4.26).
- **Remove the precondition entirely** (open expansion). Better on three of four sets and it
  fails G4 by answering two unanswerable cases, measured above. This is ADR-0048's own
  refusal, re-measured, and it is why the gate exists rather than nothing.
- **Keep `STEM_WEIGHT` at 0.1** so that no parameter is re-chosen. Tempting, and it scores
  best on ours/dev (0.5533) — but it costs uv/dev 0.0169, and every point of that cost is
  `u-0007` losing its definition to "this means that". A change whose only dev-set loss is a
  definition demoted below a function-word match should not ship at the value that causes it.
- **Choose 0.075 instead of 0.05.** It reads better on ours/release (0.519 against 0.498)
  and is tied on dev. Rejected because the release sets are read, never tuned against: the
  only legitimate tie-break was margin to the observed edge, and 0.075 has less of it.
- **A second FTS table, or a fused ranking.** Refused ten times already (ADR-0031,
  ADR-0041) and refused here for the same reason: this is one BM25 computation over one
  table, with nothing added to tune.
- **Re-judge `u-0007`** so the parameter question dissolves. Rejected on inspection rather
  than on process: the judgment is right. `#/0` defines resolution and
  `#dependency-preferences/0` does not, so the case is measuring what it claims to.

## Consequences

- **One public name added**, `mycelium.store.foothold_query`, and `expanded_query` changes
  meaning: it is now the open expression, and a caller that wants ADR-0048's semantics must
  run the gate itself. `search_chunks` does. Pre-1.0, so the CHANGELOG carries it.
- **No schema change.** The index columns are ADR-0048's; only the expression that reads
  them and the weight that scores them moved. Store version stays `mycelium/store/v4`, and
  no store is rebuilt.
- **Gate G6 did not move**, for the same reason it did not move at 4.19: the determinism
  golden observes chunk records, and neither the expression nor the weight reaches one.
- **The baselines are *not* re-blessed here.** ADR-0053 fixed that a re-bless is its own PR;
  this is a retrieval change, so it is measured against the lines already drawn and G3
  enforces on the two frozen sets. The gain therefore shows up as headroom in the next
  bless rather than as a moved line here.
- **`stem_weight` in the run manifest now reads 0.05**, which is how a reader tells a run
  on this index from a run on the last one.
- **Roadmap 4.23 closes, and the reason is not the one it was filed with.** Its premise —
  reach for footholdless queries — is refused on measurement: no judged answerable case
  needs it, and the two mechanisms it proposed would both be calibrated on sets too thin to
  calibrate anything. What shipped instead is the reach it did not ask for.
- **One thing the measurement found is left open**: a stem match on an inflected *function*
  word ("means" → `mean`) is morphologically correct and semantically empty, and at a high
  enough stem weight it outranks a definition. The weight bounds it here; distinguishing
  content words from function words is a thresholded heuristic, so it waits for 4.26's
  sets — filed as roadmap **4.28**.

## References

- ROADMAP 4.23 (this item), 4.19 (ADR-0048, where the gap was filed), 4.25 (`fact` on the
  second corpus), 4.26 (set sizes), 4.28 (filed here).
- Spec 04 §3 (the lexical leg and its field weights — unchanged), §7 (dev/release
  discipline, the gates).
- `python tools/measure_ranking.py --release` — every number above, with
  `index: expand-gate` beside the variant ADR-0048 shipped and the open expansion both
  refused.
- [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) — amended: its expression and
  its weight are superseded here; its columns, its stemmer, and its refusal of open
  expansion stand.
