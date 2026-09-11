# 2026-09-11 — a name looked up exactly (roadmap 5.9)

- **Session scope:** roadmap 5.9 — spec 04 §3's symbol leg: build it, run its ablation, and
  decide the default from the measurement (spec 04 §§2-3; ADR-0075's shape).
- **PR:** #107 (`feat/symbol-retrieval-leg`). Follows #106, merged as `5e0a0ed`.
- **Milestone 5:** 5.9 done; 5.19 filed (the finding that outlives the flag).
- **ADR:** [ADR-0080](../../../adr/0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md).

## The measurement came first, and it answered the question before the code did

My own note from 5.3 says it plainly: before adding a leg, decide whether it *adds* candidates
the other legs cannot reach — if it only re-ranks what they already found, it belongs as a boost
and not as a leg. So the session opened with a probe rather than an implementation: what do the
three corpora define, which judged queries name one of those symbols, and where does the lexical
leg already rank that symbol's definition sites?

All three answers were discouraging in a way that turned out to be the deliverable.

**The corpora define almost nothing the queries ask about.** Ours: three symbols, all headings.
uv: fourteen, mostly filenames. The `symbol` slice, nineteen case-instances across six sets,
asks for `SqliteStore`, `UlidFactory`, `uvx`, `uv tool install` and seven more — and not one of
them names a symbol any corpus defines. Our documentation discusses classes in prose without
fencing their definitions; uv's documents commands, which are not symbols at all. The lookup can
fire on four cases out of 133, and on none of the nineteen.

**Where it fires, it has nothing to add.** This is the part I did not see coming and it is
arithmetic, not luck: a definition site is a passage *containing the name that makes it a
definition*, so BM25 retrieves it for any query naming it, and usually first. Measured on the
four firings: ranks 11 and 49 on uv, 10 and 44 on the ingested twin — every one inside the fifty
candidates the ranking already has. Under ADR-0075's rule that a leg adds and never promotes, a
leg whose candidates are all already retrieved carries nothing at all.

**And promoting them would be wrong rather than merely risky.** On all four firings the
definition site is not judged relevant. `uv lock --check` names `uv.lock`, whose `defined_in`
is a line in a project-layout listing; the judged answer is the section about checking the
lockfile. That is ADR-0062 meeting ADR-0073 from the other side. ADR-0062 decided a `symbol`
judgment names the section that *documents* the thing and that a page which merely names it
scores lower or not at all — and ADR-0073's extractor reads `defined_in` from exactly such a
page, the heading that spells the name.

## Built anyway, and both readings scored

I built the leg for two reasons. A measurement of something you did not build is a prediction;
and spec 04 §3 prescribes the generator, so the deliverable is the ablation rather than the
feature — ADR-0075's shape, one item earlier.

The interesting design fork is that spec 04 §2 says *"symbol lookup **first**"*, which reads as
a licence to promote, while ADR-0075 says a leg that promotes makes RRF pay one piece of
evidence twice. Both cannot be obeyed, and arguing about which the spec meant is not how this
project decides things, so `SYMBOL_PROMOTE` became a named constant and the runner scores both
arms. Add-only: byte-identical on all six sets. Promote: −1.1 % overall on both release sets,
`u-1001` falling 0.6764 → 0.5174, and **+0.0 % on the `symbol` slice under both readings**,
because the leg cannot reach that slice either way.

No constant was swept, and that is a deliberate omission with a reason: under add-only no
discount changes a single result, and under promote the candidate is the wrong passage, so no
discount makes it right. This is the rare case where a sweep is not merely fitting but
arithmetically pointless.

## What proves the leg works, given that it does nothing

A null result is only worth reporting if the thing measured demonstrably runs, so the tests had
to produce an addition somewhere. That took longer than the leg did, and each failed attempt
taught the same lesson from a different angle: a two-document fixture could not do it, because
the definition ranks *first* for its own name; shrinking the ranking's depth could not do it,
because the served window is capped by the same number; and `Widget` was not even looked up,
because one capitalised word is a word and the shared identifier rule correctly says so.

What works is the real-world condition stated as a corpus: fifty-five documents that mention
`WidgetFactory` repeatedly, and one that defines it once inside a fence under a heading that
does not repeat it. The definition lands at lexical rank 56, outside the leg's fifty candidates,
and the symbol table brings it into a ten-deep window at position 8 — which is also ADR-0075's
discount derivation in action, since 0.9/61 beats the window's weakest at 1/70 and loses to its
best at 1/61.

## Two things folded in rather than bolted on

`identifier_like` was written twice — once at 5.1 for headings, once here for queries — and the
second copy lasted about ten minutes before becoming a shared function. Two regexes for "what a
name looks like" would drift, and the drift would make the leg unable to find precisely the
symbols the extractor had written. The heading rule now calls it too.

And `symbols/` joined `TUNING_PATHS`, for the reason `graph.py` joined one item earlier: with the
flag on, what the extractor decides a document defines is what a query can be answered with.

## Gate G2, re-recorded, with the check that it was only a fingerprint move

`retrieval_identity()` gained the symbol constants, which makes the committed verdict stale by
construction. The re-record went the way my note says it must: rebuild all three corpora first,
set the uncommitted analysis documents aside so the verdict describes a tree a clone can
reproduce, then record. The check that it was only a fingerprint move is that the four `uv` and
`uv-ingested` numbers reproduce byte-identically — they did — and only `ours/*` moved, by the
corpus growth a self-hosting corpus reports rather than gates. The decision is still `lexical`.

## One expected re-bless, checked rather than assumed

Adding `symbol_lookup` to `[retrieval]` moved gate G6's `config_digest`, because that digest
covers resolved settings and not file bytes (ADR-0014). The golden diff is that one line and
nothing else — every document, chunk and symbol byte-identical, `counts` unchanged — which is
the shape a config-only change must have. Worth looking at rather than waving through: a golden
that had moved further would have meant a retrieval flag reaching the compiler, which is exactly
what the tier boundaries forbid.

## Lesson

The useful output of an ablation is not always a number. Here it is a *reason*: the symbol table
records where a name is spelled, and a question about a name wants where it is explained. No
discount, budget or routing rule can bridge that, which is why 5.19 is filed against the
extractor and not against the ranker — and why the boost form that spec 04 §4 would otherwise
favour was rejected too, since it would promote the same wrong passage.
