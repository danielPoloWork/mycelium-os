# 2026-09-04 — a gate that said it was watching seventeen rows (roadmap 4.20)

- **Session scope:** roadmap 4.20 — give the thin slices enough cases to carry a gate, or
  stop gating them (ADR-0044's benchmark-design half; spec 04 §7.1, §7.3, D-010).
- **PR:** #73 (`eval/thin-slice-gating`). Follows #72 (4.24), merged as `3d62bf4`.
- **Milestone 4:** 4.20 done; 4.22, 4.23, 4.25 open, and 4.26 filed here.

## The measurement said the item was worse than it was filed as

ADR-0044 counted the gated rows at 4.17 and found five holding two cases or fewer. Counting
them again today, against the baselines actually committed:

```text
17 gated rows across three release sets
 5 cannot fail at all      unanswerable ×3, symbol ×2 — all blessed at 0.0000, and
                           `_relative` returns 0.0 or 1.0 against a zero, never a negative
 8 of the remaining 12     hold three cases or fewer
 1 holds one case          exact, on our own release set, blessed 0.9833
```

And the verdict string said `6 slice(s) compared` regardless, which is a gate misreporting
its own coverage.

Two facts sharpened it further, and both came from re-reading rather than re-measuring.
Our own release set is *structurally* never enforced — this repository's documentation is
its corpus, so every PR trips the not-comparable branch (BUG-0014, and 4.22's whole point) —
so the rows G3 really enforces are the two `uv` sets, and **ten of those twelve are thin or
unfailable**. And `unanswerable` should never have been a G3 row at all: its cases name no
relevant anchor, so 0.0000 is its *correct* score, and a fall in it would mean the system got
better at staying silent. G3 was enforcing "must not decrease" on a metric whose right answer
is its floor.

## The item offered two remedies; the arithmetic said do both

Judging cases into a thin slice does not repair the gate on its own — at four cases a single
answer dropping out of the top ten still moves the mean by an order of magnitude more than
the 2 % threshold, and at these set sizes it always will. Stating a reporting rule on its own
would leave rows disarmed that could perfectly well be armed by reading three documents.

So: **a contract stated** for every row, and **cases judged where a set could take them**.

The rule is that G3 enforces a slice when it is not `unanswerable`, its baseline is above
zero, and it holds ≥ 4 cases — and *names* every row it only reports, with the reason:

```text
1 of 6 slice(s) enforced; reported only:
  conceptual (3 case(s), below the 4 G3 enforces on);
  exact (2 case(s), below the 4 G3 enforces on);
  relationship (2 case(s), below the 4 G3 enforces on);
  symbol (blessed at 0.0000: a relative threshold cannot fail it);
  unanswerable (reported by design: 0.0000 is its correct score, and G4 gates it)
```

That is `uv/release`, and it is a worse-looking number than the one it replaces. It is also
the true one: those five rows were being counted as passes.

Four is a line drawn on a continuum, and the ADR says so rather than dressing it as a
statistic. What turns G3 into a regression gate rather than a single-case alarm is set size,
and that is the ≥ 1 000 cases spec 04 §7.6 wants at 1.0.

## The new cases corrected a number that had been flattering us

`exact` on our own release set was blessed at **0.9833** — one case, a term quoted back
verbatim from a heading. Over four cases it reads **0.7593**, and the case that pulls it
down is `STRIDE` at 0.3331: an acronym whose literal home is one document among three that
mention it. The old figure was not a regression waiting to happen. It was a case being
reported as a slice, for four milestones.

None of the five was chosen to score well. Every one was written from the documents before
anything was run, and two of them landed below the case they joined; a set whose additions
all scored well would be a set chosen after the fact, which is the failure ADR-0044 refused
when re-judging would have rescued a slice.

## What the gate could not say, and now says

ADR-0044's complaint was never sensitivity. It was that `relationship 0.3040 -> 0.1064` is a
sentence a reader has to go and investigate, and investigating it took an afternoon. G3 now
appends the cases:

```text
exact 0.9833 -> 0.7593 (-22.8%)
  [r-0003 0.9942, r-0015 1.0000, r-0016 0.7098, r-0017 0.3331]
```

Three cases at or near the old number and one much harder — a population change, not a
regression, legible without opening anything. `--bless` records per-case scores too, so the
next baseline can show where each case moved *from* rather than only where it is now. A
baseline without the field attributes with today's numbers only: an absent field is reported
as absent, never guessed at.

## The eight cases that are not in this PR

Eight more were written for `uv/release` — the set G3 actually enforces on — and they are
not here. Two couplings stopped them, and the first was found by running the suite rather
than by reasoning about it.

`test_the_judged_documents_take_the_formats_in_rotation` went red at index 8. The third
corpus assigns DOCX, HTML and PDF **by rotation over the judged set**, sorted by path, so
cases that newly judge `projects/sync.md`, `projects/run.md` and
`getting-started/features.md` shift every index after them and re-roll the format of
documents already rendered. Those renderings are committed provenance that cannot be
re-derived — typst embeds a build identifier, measured at ADR-0039 — so the change would
have re-rendered the corpus and moved the per-format projection-cost table with it.

Behind that sits a second one. `tools/check_frozen_release_sets.py` forbids a derived set
moving with its source, which makes a source set unable to grow at all: the carry *must*
follow (CI byte-checks it) and a regeneration alone has nothing to regenerate from. The same
deadlock 4.15 met from the chunking side, reached from the judgement side.

The tempting way out was to rewrite the four offending cases so they only touch the
seventeen documents already judged. That is the one option I am sure is wrong: it lets the
tooling decide what gets judged, which is a quieter version of what the frozen-set
discipline exists to prevent. So the cases went into roadmap **4.26** with both couplings
named, and this PR kept its subject.

## What this hands on

Growing our own release set changed its `cases_digest`, so G3 reports on it for that reason
as well as the corpus one — ADR-0051's designed behaviour working. **4.22** re-arms it, and
the baseline it writes will carry per-case scores. **4.26** is the one that matters more:
until it lands, the only sets G3 can enforce are running on a single row.
