# 2026-09-09 — the two cases disagree (roadmap 4.38)

- **Session scope:** roadmap 4.38 — the section that documents a command is the longest
  chunk, and loses for it (spec 04 §§3, 7.4; ADR-0031/0041/0049/0058).
- **PR:** #89 (`perf/damp-the-length-normalisation`). Follows #88 (4.37), merged as
  `5981c8a`.
- **Milestone 4:** 4.38 done; 4.39, 4.40, 4.41 open.

## The premise held, which was itself new

Three items in a row have had premises that did not survive being checked (4.33, 4.37, and
4.36's proposal). This one does. Verified on the current index, after the heading split and
the re-judging:

| case | judged chunk | tokens | our rank | ours | grep |
|---|---|---:|---:|---:|---:|
| `u-1007` | `guides/tools.md#installing-tools` | 409 | 4th | 0.374 | **0.745** |
| `u-1006` | `python-versions.md#requesting-a-version` | 385 | 4th | 0.431 | **1.000** |

The chunks above the answer are shorter — 114, 245, 84 for `u-1007` — and the incumbent puts
the answer first in both. grep's own top six for `u-1007` reads 409/245/366/783/537/687
tokens: its ranking has no length normalisation at all, so ours and its are near mirror
images on length.

## One fact I did not expect, worth keeping either way

`bm25()` normalises by the **row's** total token count, not per column. Two rows with an
*identical* matching heading and bodies of 20 against 400 tokens:

```text
heading-only weights (text weighted 0.0)
   short  -0.000003060
   long   -0.000001151
```

A 2.7× difference produced entirely by a field the weights excluded. So **a column weighted
0.0 is not free**, and after 4.36 three of the four surface columns are a handful of tokens
sharing one denominator with a `text` that runs to hundreds. That is a constraint on every
future field-weight decision and it was written down nowhere.

## The candidate, and the thing it exposed

The lever that fact opens is the only one left that is neither a re-ranking (refused ten
times) nor a change of unit (refused six, and bounded by ADR-0049's oracle): put the short
fields in their own FTS table so they normalise against comparable lengths.

All five settings fail gate G3 on both release sets — `relationship` from −34.7 % to −92.8 %
on ours, −32.3 % to −61.6 % on uv — and none wins on dev either. I expected the diagnosis to
be the scale error: two BM25 scores over tables with different average lengths are not on one
scale, so adding them is arbitrary. So I added an RRF row at spec 04 §3's k=60 — scale-free,
no new constant, the only combination this project sanctions. **It is worse**: uv/dev 0.646
against the baseline's 0.710.

Then the per-case table, which is the actual finding:

| setting | `u-1007` | `u-1006` |
|---|---:|---:|
| baseline (ships) | 0.3742 | 0.4307 |
| `length 1.0` | **0.3194** | 0.6309 |
| `length rrf` | **0.2015** | **1.0000** |
| grep | 0.7453 | 1.0000 |

**Every setting that moves one makes the other worse.** 4.38's bar was that a candidate move
both; they pull in opposite directions, so no setting of this lever could have. And the
hypothesis was wrong about `u-1007` specifically: its heading match ("Installing tools") was
being *helped* by the joint computation more than it was hurt by the shared denominator.
Splitting the fields took the help away.

`length rrf` closes `u-1006` completely — 1.0000, the incumbent's own score, the first thing
in `measure_ranking.py` ever to do it. It is still refused, and that is the whole discipline
of the file: it pays with `relationship` at −54 % and −61 %, and with the other named case.

## What that says about a decision already made

ADR-0048 chose one FTS table over two, arguing the tuning surface: one weight rather than
two. The measurement says the reason is stronger. A split on the *field* axis fails
identically whether the scores are added or RRF-fused, because the fields carry **joint
evidence** inside one BM25 computation that a multi-part query depends on — and
`relationship` is the slice made of multi-part queries. That ADR is strengthened rather than
narrowed, with the note beside the sentence it improves.

## What I did not do

No product change, no new roadmap item. `u-1006` is not refiled: it has stopped being a
mystery and become a price — closable, at four slices — which is more useful to whoever
returns to it than "still open", and the question it now poses (what closes it *without*
paying) needs the set sizes spec 04 §7.6 asks for rather than another pass at BM25. Those
live in 4.39 and 4.41 already.

The refusal count is fourteen families. This is the first refused by its own named cases
rather than by a slice mean or a gate, and it took about as long to falsify as to write —
which is what having named cases buys.
