# 2026-09-09 — the third asking (roadmap 4.42)

- **Session scope:** roadmap 4.42 — raise the leaf heading field weight from 2.0 to 3.0, now
  that a dev set can see it (spec 04 §3; ADR-0058/0063/0067).
- **PR:** #93 (`perf/leaf-heading-weight`). Follows #92 (4.41), merged as `d23222f`.
- **Milestone 4:** 4.42 done; 4.43 open, and the M5 question below is still the maintainer's.

## A one-line change, and the reason it took three items to earn

The diff in `src/` is one tuple element. What made it takeable is that roadmap 4.39 was
commissioned, two items ago, to build the evidence that would decide it — and then the
evidence came back saying something better than "yes".

At twelve judged cases, `uv/dev` scored **every** safe setting of this family identically:
that is why ADR-0058 refused the candidate and ADR-0063 refused it again. At twenty-two the
parameter has an interior optimum — 3.0 reads 0.614 against the shipped 0.609, and **4.0
reads 0.599, below the baseline**. A set that can distinguish 3.0 from 4.0 can *choose*, and
it chooses against the release sets, which prefer 4.0 (0.616 against 0.611). That
disagreement is the dev/release split doing the only job it has.

The two refusals were right and the acceptance is right, and nothing about the mechanism
changed between them. Only the instrument did.

## What I did not want to find, and reported anyway

Two rows point the wrong way.

**`ours/dev` is a hair worse** — 0.540 → 0.539, one case, `q-0014` losing 0.0127. One dev set
says yes and the other says a barely-measurable no. The item's own text did not mention this;
ADR-0063 had.

**`ours/release` trips `conceptual` by −2.1 %**, and that is one case: `r-0004`, *"may an
agent merge its own pull request"*. Its answer falls from rank 4 to rank 5, overtaken by a
chunk whose leaf heading is literally **Pull Requests**. The mechanism working, on a query
whose better answer is a boundary table elsewhere in the same document.

I spent most of the decision time on that row, because the convenient move was available and
wrong: G3 does not enforce on our own release set (ADR-0053), so I could have not mentioned
it. Three things decided it instead. It is ADR-0069's per-case veto to the decimal — a
four-case slice at these means trips at 0.042 and the case gives up 0.044. The same set gains
four points overall, because `r-0010` gains 0.369 where `r-0004` loses 0.044. And the bar is
not moved, because ADR-0069 refused to move it two PRs ago and filed 6.8 for the denominator;
moving it now, with a candidate in flight, would be that ADR's own warning happening.

## The finding that was not in the item

After the change, the full suite passed — 1559 tests — and `mycelium_explain` was reporting
`heading 2.0` while the ranker used 3.0.

ADR-0068 built `retrieval_identity()` for exactly this and named 4.42 as the change that
would test it. It fired, correctly, on the G2 verdict. But that sweep found the two
hand-typed copies of the field weights in the run manifest and missed two more in
`mycelium.mcp.tools` — the `explain` payload and `mycelium_explain`'s `config` block. The
tool whose whole purpose is to tell an agent how a query was ranked was the last thing in the
codebase still describing the old configuration.

The tests did not catch it because both sides were literals and they agreed with each other.
The fix keeps the literals in the test — that is where a pinned value belongs — and makes the
code derive. Verified by mutation: reverting the weight now fails both tests, where before it
failed nothing.

Worth generalising, and it is this session's lesson: a fingerprint proves a *record* is
current. It says nothing about every other place the same fact was copied by hand.

## Order of operations, for the record

Verdicts read against the committed baselines first, then the two enforceable baselines
re-blessed, then the G2 verdict re-recorded. Neither re-blessed set's `cases_digest` or
`corpus_digest` moved, so what landed in those files is a retrieval move and nothing else.
This repository's own baseline is deliberately not re-blessed.

## Still open

4.43 (`tools/` is neither linted nor type-checked). And the question from 2026-09-08 that
this item's own text raises again in its last sentence — Milestone 4's Phase-2 exit gates
were met at PR #59, and 4.42 served none of them.
