# 2026-09-18 — the question was the one unbounded cost (roadmap 6.17)

- **Session scope:** roadmap 6.17 — bound what a query may cost the server, the finding the
  6.3 security review filed rather than fixed (register F11).
- **PR:** `feat/bound-the-query`. Follows #163, merged as `33e045e`.
- **Milestone 6:** 6.17 closed, 6.26 filed.
- **Decision it records:** [ADR-0129](../../../adr/0129-bound-the-question-once-before-anything-reads-it.md).

## What re-measuring changed

F11 said 57 s for twenty thousand terms and called the growth superlinear. Both statements
needed correcting, in opposite directions.

The number was **low**, because the probe timed `mycelium.store` — the component the finding
was filed against — and the boundary is B6, the serving edge, which runs the whole `search`
path. The symbol leg has shipped **on** since 5.25; it composes one candidate id per
identifier-like token per language and then re-ranks the survivors with BM25 over the same
enormous expression. Through that path this repository's own README, pasted as a query, held
the server for **146 s**: 130 s lexical, 7 s symbol. That generalises past this row — a probe
aimed at the component a finding is about measures that component, and the boundary is the
path.

And "superlinear" was right only at the extreme. The cost is linear at 3–4 ms a term with a
knee at twenty thousand. Unbounded and linear was already enough; reaching for the knee made
the finding sound narrower than it was.

## The number that decided the bound

Not a round number chosen for looking safe: **the longest query anything in this project
measures itself on is nine terms** — one agent task — across six judged sets and the
agent-task suite, median three to four. Sixty-four is seven times that. The other half of the
choice is that a bound must still bind: at 64 terms the lexical leg costs ~210 ms on the
largest corpus here, against ~110 ms at 32 and ~470 ms at 128.

That evidence is now a test rather than a paragraph. `test_no_query_this_project_measures_itself_on_reaches_the_bound`
walks all six sets and the tasks; the day a judged question grows past 64 terms, the cut is a
scoring change and the test names it before a gate reports it as a regression.

## Where the bound went, and why not where the item said

The item proposed the planner or `fts_query`, and it is neither.

`fts_query` also builds the expression the **index** is written with, so a bound there is a
bound on indexing — it would silently truncate long documents at build time. The planner
decides routing, not cost. And the obvious minimal fix, capping `query_terms`, bounds the
lexical leg and nothing else: the symbol leg tokenizes the raw query itself, with a different
tokenizer that keeps `uv.lock` whole, and 7 s of the 146 was there.

So the bound is on the **question**, taken once in `search` before the plan and before any leg
reads it. Everything downstream is bounded by construction — including a leg nobody has
written yet, which is the property the other three placements would not have had.

## What the work uncovered and did not fix

The surface half of `expanded_query` does not deduplicate its terms and the stem half does,
deliberately and with a comment saying why. So a question contributes one `OR` arm per
*occurrence*: this repository's README is 7 384 terms and 1 979 distinct, and its `MATCH`
expression came to 98.9 KB.

The bound makes the cost of that moot. What is left is a ranking question nobody has argued —
whether a repeated word should weigh twice — and it is not free to settle: two of 155 measured
queries repeat a term, both agent tasks. Filed as **6.26** rather than folded in, because
inside this PR the two effects act on the same expression and no measurement could have told
them apart.

## Lesson

A bound belongs on the thing a caller controls, not on the first place that gets expensive. The
item named two placements and the measurement named a third, because the cost had already
spread to a leg that was switched on after the finding was written.
