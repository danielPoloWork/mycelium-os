# 2026-09-14 — a floor is not a preference (roadmap 5.41)

- **Session scope:** roadmap 5.41 — the carry landed a judged anchor on a chunk that does not
  contain the command the query names. Measure the three proposed shapes, then choose.
- **PR:** #140 (`fix/carry-the-anchor-that-answers`). Follows #139, merged as `8c0ad75`.
- **Milestone 5:** 5.41 done. 5.42 (re-bless `uv/release`) still open.
- **ADR:** [ADR-0111](../../../adr/0111-a-floor-can-reject-what-a-preference-must-not-choose.md).

## The item named three shapes and asked for the measurement first

That instruction was the whole value of the item, because all three lose.

**Prefer a same-heading-slug candidate.** Right on `u-0017` and wrong everywhere else. The
projection re-heads a document, so the slug that survives is usually a stub holding the
section's opening sentence: measured, the same-slug candidate scores 0.1883, 0.3857 and 0.2069
on `u-0003`, `u-0020` and `u-1019` against winners of 0.7468, 0.9143 and 0.6207. Adopting it
would have repaired one anchor and broken three.

**Use `whole` as a tie-break.** It does not fix the case it was proposed for. The wrong
winner's `whole` is **0.3383**; the right chunk's is **0.2886**. A tie-break on `whole` picks
the wrong one too, and that is not bad luck — both are fragments, and no comparison *between*
fragments can say that neither is the passage.

**Require the query's terms to survive.** Correct here, and the one thing this tool must not
do. A carry that reads the query stops measuring what projection costs and starts handing the
twin a chunk that lexically matches what is about to be searched for. That is ADR-0027's trap
with the evidence removed. The measurement says so too: 15 of the 63 mapped anchors have a
winner missing one of the query's words — `live`, `clear`, `which`, `mean`, `before` — at
coverage *and* `whole` of 1.0000, so the rule would need narrowing to terms present in the
judged passage, which is more machinery built on a signal that may not be consulted at all.

## What was left, and why it is not the thing ADR-0102 refused

ADR-0102 recorded `whole` and refused to let it choose an anchor. The distinction that
survives that refusal is between **choosing** and **rejecting**. A tie-break asks which of two
candidates is better, which is the question that gets a carry fitted. A floor makes one claim —
*none of these is the passage* — and that is exactly what `MIN_COVERAGE` already says, on the
one metric that cannot see a split.

So `MIN_WHOLE = 0.4`. It sits in a basin rather than on a cliff: over the 63 anchors that clear
the coverage floor, `u-0017`'s 0.3383 is the lowest and the next is 0.5088, so every value from
0.35 to 0.50 drops that one anchor and nothing else. A test asserts the room is still there,
because a constant with no room is a tuned one whether or not it was tuned.

## The shape, which is what the item actually asked for

Five judged anchors grade a feature-list section of `features.md`, whose HTML lane makes a
heading per item. Four are shattered: three were already dropped at 0.39–0.42, and `u-0017`
cleared the coverage floor by accident of vocabulary. The fifth, `u-1019`, is the control and
the reason to trust the floor — its query is `uv python pin`, the projection kept that item
whole, coverage lands on it, and `whole` is 0.5088. One projection shape, and the floor
distinguishes the fragment that holds an answer from the four that hold pieces.

## Numbers

Controlled, with the corpus and the compiler fixed and only the carried set varying:

| set | mycelium | grep |
|---|---|---|
| uv-ingested/dev | 0.583450 → **0.586058** | 0.431194 → 0.431194 |
| uv-ingested/release | identical to six decimals | identical |

One case moves — `u-0017` **0.5788 → 0.6309**, `symbol` 0.4690 → 0.4820 — and it gains because
a wrong anchor left, not because retrieval improved. The anchor was never retrieved at all
(rank > 50); its only effect was to inflate the ideal DCG the case is scored against.

## One correction to the item's own text

5.41 said the change "re-blesses both baselines and re-records gate G2 through `cases_digest`".
It re-records G2 and it re-blesses nothing. The mis-carry is in the **dev** set; the release set
is byte-identical, and gate G3 reported *"same corpus, same boundaries, same judgements, no
enforced slice regressed"* on it before and after. The enforcing gate never disarmed, so there
was nothing to re-arm — and blessing a baseline that did not need it would have been a change
nobody could review, on a set whose numbers did not move.

## Found on the way

The tool's own docstring warned that *"the closest mapped anchor sits at 0.5269 against the
0.50 floor, which is a cliff a reviewer should be able to see rather than discover"*. The thing
standing on that cliff was the defect. With it dropped the closest mapped anchor is 0.6207, and
the coverage floor has the headroom the docstring wished for. Two stale counts in that
docstring were corrected at the same time.

## Lesson

When a rule picks the wrong answer, the tempting repair is a better way to pick. Twice here
that would have been wrong, because the premise was false: nothing in the candidate set was the
right answer. The useful question was not *which fragment* but *is any of these the passage* —
and a metric already in the receipt, refused two milestones ago for choosing, could answer it
by refusing.
