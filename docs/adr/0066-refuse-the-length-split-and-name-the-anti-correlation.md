# ADR-0066: Refuse the length split, and name the anti-correlation it exposed

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.38 (this item), 4.34 (where it was filed), 4.25; RFC-0001;
  spec 04 §§3, 7.3, 7.4; D-010;
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) — **strengthened here**,
  [ADR-0049](0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md),
  [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md)

## Context

Roadmap 4.38 carried a standing observation with, for the first time, **two named cases on
the set gate G3 enforces**: *a long section that answers a query concedes to shorter ones
that merely mention it, in the `text` field*.

Verified on the current index, after the heading split (4.36) and the re-judging (4.34):

| case | slice | judged chunk | tokens | our rank | ours | grep |
|---|---|---|---:|---:|---:|---:|
| `u-1007` | `symbol` | `guides/tools.md#installing-tools` | **409** | 4th | 0.3742 | **0.7453** |
| `u-1006` | `fact` | `python-versions.md#requesting-a-version` | **385** | 4th | 0.4307 | **1.0000** |

In both, the chunks ranked above the answer are shorter — 114, 245 and 84 tokens for
`u-1007` — and the incumbent ranks the answer **first** in both. grep's top six for `u-1007`
runs 409, 245, 366, 783, 537, 687 tokens: its `(distinct terms, total occurrences)` ranking
has no length normalisation at all, so the two rankings are near mirror images on length.

**One new fact underlies the whole item, and it is worth keeping regardless of the outcome.**
SQLite FTS5's `bm25()` normalises by the **row's** total token count, not per column. Two
rows with an *identical* matching heading and bodies of 20 against 400 tokens score
`-3.060e-6` and `-1.151e-6` under heading-only weights — a 2.7× difference produced entirely
by a field the weights excluded. So a heading match's contribution depends on how long the
body is, which is not a property of the heading match. After 4.36 the index has four surface
columns and three of them are short: `title`, `heading` and `ancestors` are a handful of
tokens each, sharing one denominator with a `text` that runs to hundreds.

That gives the family the one lever on the denominator which is **neither a re-ranking nor a
change of unit** — the two families already refused thirteen times over (ADR-0031, ADR-0041,
and the oracle bound in ADR-0049): put the short fields in their own FTS table so they
normalise against comparable lengths, and combine the two scores.

## Decision

**Refuse all five settings, and record why the item's own bar could not be met by any of
them.** `tools/measure_ranking.py` gains the length family; nothing in the product changes.

Gate G3, on both release sets:

| setting | ours/release | worst slice | uv/release | worst slice |
|---|---:|---|---:|---|
| baseline (ships) | 0.506 | — | 0.604 | — |
| `length 0.0` *(text only, the control)* | 0.507 | `conceptual` **−29.1 %** | 0.614 | `fact` **−2.0 %** |
| `length 0.5` | 0.529 | `relationship` **−34.7 %** | 0.590 | `symbol` **−20.0 %** |
| `length 1.0` *(equal weight, no constant)* | 0.539 | `relationship` **−78.0 %** | 0.534 | `relationship` **−32.3 %** |
| `length 2.0` | 0.510 | `relationship` **−92.8 %** | 0.491 | `relationship` **−61.6 %** |
| `length rrf` | 0.489 | `relationship` **−53.8 %** | 0.471 | `relationship` **−61.3 %** |

Every row fails, and none of them wins on dev either: uv/dev reads 0.710 for the baseline
against 0.709 at `length 1.0` and 0.646 at `length rrf`. The candidate never reaches the
gate that would have refused it.

**The finding is the anti-correlation.** Per case, on the two cases the item named:

| setting | `u-1007` (`symbol`) | `u-1006` (`fact`) |
|---|---:|---:|
| baseline (ships) | 0.3742 | 0.4307 |
| `length 0.5` | **0.2015** | 0.6309 |
| `length 1.0` | **0.3194** | 0.6309 |
| `length 2.0` | **0.3194** | 0.6309 |
| `length rrf` | **0.2015** | **1.0000** |
| grep (incumbent) | 0.7453 | 1.0000 |

**Every setting that moves `u-1006` makes `u-1007` worse.** 4.38's bar was that a candidate
must move *both*; the two cases pull in opposite directions under this lever, so no setting
of it could have. That is a stronger result than "the candidate fails": it says the standing
observation does not have **one** mechanism behind it, and the hypothesis was wrong about
`u-1007` specifically — its heading match was being *helped* by the joint computation more
than it was hurt by the shared denominator. Splitting the fields took that help away.

`length rrf` takes `u-1006` to **1.0000**, matching the incumbent exactly and closing the
case that has been open since ADR-0058 — the first thing in `measure_ranking.py` ever to do
it. It is still refused, and the honesty of the refusal is the point: it pays for that case
with `relationship` at −53.8 % and −61.3 %, and with `u-1007`.

**And the failure is not the scale error it looks like.** Adding two BM25 scores from tables
with different average lengths is not a fusion, which is the obvious diagnosis for why
`length 1.0` breaks `relationship`. So the family includes an RRF row: spec 04 §3's k=60,
scale-free by construction, no new constant. It is **worse**. Any split of the fields — added
or fused — loses the reinforcement a multi-part query needs between a chunk's heading and its
body, and `relationship` is the slice made of multi-part queries. **This is a stronger reason
for ADR-0048's one-table decision than the one it gave**: not merely "no fusion stage to
tune", but that the fields carry joint evidence no combination can reconstruct.

## Alternatives Considered

- **`length rrf` anyway, because it closes `u-1006`.** Rejected: `relationship` −53.8 % and
  −61.3 % against a −2 % bar, `u-1007` from 0.374 to 0.202, and it loses on uv/dev. Adopting
  the one candidate that closes a famous case while failing four slices is how a benchmark
  becomes a trophy cabinet.
- **A weight between 0.5 and 1.0, or per-slice weights.** Rejected: the two named cases move
  in opposite directions across the whole range, so there is no interior point where both
  improve — and a per-slice weight needs a slice classifier the planner does not have and a
  constant per corpus (D-011).
- **Damp `b` directly by computing BM25 ourselves.** The mechanism's true lever, and still
  unavailable: SQLite exposes `bm25()`, `highlight()` and `snippet()` as auxiliary functions
  and no per-row term frequency, and Python's `sqlite3` cannot register an FTS5 auxiliary
  function. Reimplementing the scorer over `fts5vocab` is building the engine, which D-007's
  posture refuses for parsers and the same argument refuses here.
- **Bound chunk length so no chunk is 409 tokens** — lower `target_tokens` until the long
  sections split. Rejected as out of this item's scope and against ADR-0023, which chose the
  default by measurement; it also moves every chunk in every corpus, re-blesses the G6
  golden, and disarms G3's comparability (ADR-0045). If it is ever tried it is a chunking
  item, not a ranking one.
- **Re-open the section-level unit.** Refused six ways by ADR-0041 and bounded by ADR-0049's
  oracle, which says the unit of indexing is not where this gap closes. Nothing here is new
  evidence against those.
- **Leave the observation unmeasured.** What 4.38 was filed to stop. Two named cases were
  exactly what 4.25 asked for, and the right use of them is to falsify a mechanism cheaply —
  which is what happened, in about the time it took to write the family.

## Consequences

- **Nothing in the product changes.** No store, no retrieval, no config, no judged set, no
  baseline. The lexical leg is exactly what 4.36 left.
- **The refusal count is now fourteen families**, and this one is the first to be refused *by
  its own named cases* rather than by a slice mean or a gate. It is re-runnable:
  `python tools/measure_ranking.py --release`, the `length` rows.
- **A property of the engine is written down.** `bm25()` normalises by row length across all
  columns. That constrains every future field-weight decision — a weight of 0.0 does not make
  a column free — and it was not recorded anywhere before.
- **ADR-0048 is strengthened, not narrowed.** Its one-table decision was argued as "no fusion
  stage to tune"; the measurement says a split cannot be repaired *by any combination*,
  because the fields reinforce each other inside one BM25 computation.
- **`u-1006` has a known price now.** It is closable — `length rrf` scores it 1.0000 — and the
  price is four slices. That is more useful to the next attempt than "still open", and it is
  why the case is not refiled: the question is no longer *can it be closed* but *what would
  close it without paying*, which needs the set sizes spec 04 §7.6 asks for (roadmap 4.39,
  4.41) rather than another pass at BM25.
- **No new roadmap item is filed.** 4.38 asked whether the mechanism had a fix; it does not,
  the two cases disagree about what the mechanism even is, and Milestone 4's exit gates were
  met at PR #59. The threads that remain live in 4.39, 4.40 and 4.41.

## References

- Spec 04 §3 (field weights, RRF at k=60), §7.3 (gate G3), §7.4 (the incumbent); D-010, D-011.
- Measured this session, reproducible with `python tools/measure_ranking.py --release`:
  the cross-field normalisation demonstration; five settings across four judged sets; the
  per-case table for `u-1007` and `u-1006`; `u-1007`'s candidate set at 409 tokens ranked 4th
  against grep's 1st.
- [ADR-0031](0031-refuse-three-rerankings.md) — named the length-normalisation mechanism and
  the missing `b`, three milestones ago, and it is still the answer.
- [ADR-0049](0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md) — the oracle
  bound that says the unit of indexing is not where this closes.
- [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md) — where `u-1006`'s
  per-column attribution was first done, and where it was left open.
