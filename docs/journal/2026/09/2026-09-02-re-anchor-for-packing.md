# 2026-09-02 — judging across two chunkers (roadmap 4.12)

- **Session scope:** roadmap 4.12 — re-anchor the five cases `pack_atomic` invalidates, and
  settle the one judgment that omits its own source of truth. Judgments only; no code.
- **PR:** #62 (`test/re-anchor-for-packing`). Follows #61 (4.11), merged as `97e599d`.
- **Milestone 4:** 4.1–4.7, 4.9–4.12 done; 4.8, 4.13–4.15 open, and 4.16, 4.17 filed here.

## The rule the item had to write down first

`eval/README.md` says: name the section when a reader needs more than one chunk, the chunk
when the answer is confined to it, and when unclear the chunk. That rule assumes a **fixed**
chunker. Five judgments now have to be true under two — the one that ships and the one 4.15
turns on — and the rule has nothing to say about that.

So 4.12 wrote the missing clause: **a judgment names the smallest unit that contains the
answer under every configuration the set is scored under.** Where the judged chunk survives
packing it stays a chunk judgment; where packing merges it into its section, the section is
that smallest unit. Nothing was widened for tidiness — five anchors moved, and every other
anchor in four sets is untouched (ADR-0043).

Result: ours/dev 33/33, ours/release 17/17, uv/dev 12/12, uv/release 18/18. Every judgment
survives the flip.

## What it cost, on one build, at the shipped default

| set | nDCG@10 | moved slice |
|---|---|---|
| ours/dev | 0.536 → 0.536 (**+0.000**) | none |
| ours/release | 0.448 → 0.450 (+0.002) | `exact` 0.957 → 0.983 |
| uv/release | 0.280 → 0.306 (**+0.025**) | `conceptual` 0.377 → 0.495 |

**Our own dev set does not move at all** — the pleasant surprise. Four of the five
re-anchorings are free today: the retriever was already returning the judged chunk, so
widening the judgment to its section credits nothing it did not already credit. The
generosity I had budgeted for simply is not there on four of five cases.

**On the fifth it is, and it is worth looking at rather than averaging away.** `u-1016` asks
how to keep credentials out of shell history; the judged paragraph recommends piping the
secret through stdin. Under the section anchor the case is now satisfied at **rank 5** by a
different chunk of the same section:

```text
5. [ 18t] …#logging-in-to-a-service/5
      The credentials will not be validated, i.e., incorrect credentials will not fail.
```

That does not answer the question. +0.118 on a gated slice, bought by a judgment getting
easier rather than by retrieval getting better.

## Why I section-scoped it anyway

ADR-0029 argues against exactly this — *"a reader who gets chunk 7 when the answer is in
chunk 4 did not get the answer"* — and `u-1016` is that shape: one paragraph of a six-chunk
section. Overriding a recorded decision needs better than convenience, so, in order:

1. **There is no third anchor form.** Chunk or section; nothing else is expressible. The
   chunk form is false under one of the two configurations, so it is not on the menu.
2. **After the flip the objection dissolves.** Packing makes that section a single 204-token
   chunk, so the section anchor becomes chunk-exact — a reader who matches it *does* get the
   stdin advice. The generosity lives only in the world we are leaving.
3. **The alternative measures nothing.** Left alone it scores zero at 4.15 and contributes a
   false regression to the change it exists to judge.

And the ordering is what makes the trade safe rather than merely defensible. Re-blessing the
baselines **now** books that +0.025 as a *judgment* change, so 4.15 measures packing from the
raised line and gets credited with less. Reverse the order and the same 0.025 would have
arrived as a retrieval win. That is not bureaucracy; it decides who gets the credit, and it
is why `check_frozen_release_sets.py` refuses the conjunction.

## The other judgment, which nothing forced

`r-0003` — `Conventional Commits`, our release set's only `exact` case — named
git-workflow.md and CONTRIBUTING.md and omitted **AGENTS.md §6.3**, the file this repository
calls its source of truth and tells every agent to read first. Both existing anchors survive
packing, so this is not anchor repair: it is a judgment that named two of three places and
missed the authoritative one. Settled here, with no retrieval change in flight, which is the
only time it can honestly be settled.

## Two things found on the way, filed rather than absorbed

**The ingested twin's judgments do not reproduce from their own generator.** Re-running
`tools/build_ingested_cases.py` on a clean `main` writes 10 dev cases where 12 are committed,
dropping four for losing every anchor at coverage 0.48–0.49 against the floor. I reproduced it
with my changes stashed, so it is not mine, and the generator builds both corpora itself, so
it is not stale state. Regenerating would have smuggled a four-case shrink of a CI-scored set
into a re-judging PR, so the derived set is left exactly as committed and the drift is on the
books: [BUG-0018](../../bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md),
roadmap 4.16. The finding is not the four cases — it is that four anchors sit within 0.02 of
a cliff.

**Our release set's `relationship` slice has halved since the last bless** — 0.304 → 0.106 —
and the controlled measurement reads 0.106 on *both* sides, so it is not this change. It is
corpus growth crossing a boundary G3 refuses to enforce across ([BUG-0014], correctly), which
is also how a slow decay survives several milestones unremarked. Filed as 4.17 rather than
frozen into the new baseline in silence.

## A smaller irritation, twice

Measuring anything here means building, and building pins `mycelium_id` into ~100 documents
that must not be committed — the second session in a row that ended by stripping them back
out. `build_eval_cases.py` already does the right thing (it stages into a tempdir);
`build_ingested_cases.py` builds in place. Roadmap **4.14** is the fix and it has now cost
two sessions.
