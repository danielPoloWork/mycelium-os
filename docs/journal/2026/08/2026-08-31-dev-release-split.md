# 2026-08-31 — the benchmark measured itself, and a corpus we did not write said so (roadmap 3.13)

- **Session scope:** roadmap 3.13 — the dev/release split spec 04 §7.1 asks for, ≥ 60 judged
  cases across two corpora (§7.6), and the independent-judgment problem ADR-0021 filed.
- **PR:** #43 (`feat/dev-release-split`). Follows #42 (3.12), merged as `313575b`.
- **Milestone 3:** 3.1–3.13 done; 3.14 and 3.15 open, the second filed by this item.

## What the split found in its first run

| corpus | dev | release | gap |
|---|---:|---:|---:|
| this project's docs | 0.569 | **0.453** | +0.115 |
| `uv` docs | 0.403 | **0.249** | +0.153 |

Retrieval is about a quarter worse on cases it was never tuned against, and worse again on
documentation nobody here wrote. Gate G3 was green through all of it, and could not have been
anything else: it compares a run to a baseline over *the same twenty cases* the change was
tuned against. A change that fits those cases better passes G3 by construction.

So every retrieval number this project has published was measured on the set it was tuned
against. That sentence belongs in the changelog, not in a footnote, and it is there.

## The finding I did not go looking for

Two `exact` cases and one `symbol` case on the second corpus scored **0.000** — slices that
should be trivial. It was not retrieval. For `storage directories` the retriever returned five
chunks from the right document, under the right heading path, and the case had judged the
section's *opening* chunk.

A section is not a chunk. The metric is anchor-exact, so a judgment naming one anchor for a
section the chunker split into twelve measures how well I guessed chunk boundaries.

Our own set never showed this, and the reason is the whole point of the item: **its anchors
were chosen by someone who knew where the boundaries fall.** The same-author bias did not show
up as a generous grade — it showed up as a method that only works when the judge has read the
chunker.

**I left the judgments as authored.** I noticed the flaw while looking at scores, and
re-judging after seeing a ranking cannot be told apart from fitting the set to the result.
The release sets are frozen as written, the low numbers stand, and whether relevance should be
section-scoped is roadmap 3.15 — argued on its own evidence, not repaired with the number in
front of me. Writing that sentence was harder than writing the fix would have been.

## Freezing, as much of it as a machine can hold

"The release set is frozen before any tuning of the change under test" cannot mean *immutable*
— the sets have to grow toward ≥ 200 and ≥ 1 000. What is checkable is the **conjunction**:
one change may tune retrieval, or re-judge a release set, and not both. That is the failure
that actually happens, and `tools/check_frozen_release_sets.py` refuses it from the diff.

## On acquiring a corpus

`uv`'s documentation: MIT, 81 Markdown files, ~700 KB, pinned to one commit and **vendored**.
Fetching it in CI would have been lighter, and would have meant the benchmark measures whatever
upstream holds that day — plus a gate that fails when the network does, against D-017's
posture. The obligation MIT attaches travels with the copy.

It is deliberately *unlike* ours: short imperative task pages about a command-line tool, against
long cross-referential architecture decisions. A retriever tuned on one and measured only on it
learns the shape of that one.

## Two things fixed on the way

**The builder was validating against the wrong corpus.** It staged a hand-written list of
paths, while the gates score the whole repository minus `mycelium.toml`'s excludes — so an
`unanswerable` case could pass the builder and be answerable in CI. It stages the repository
now and lets the config decide, which is the rule the gates run under.

**A lint I promoted broke two standing cases, and the lint was wrong.** Making the heading-stub
check an error failed `## License` followed by one line naming the licence: 24 tokens, and a
complete answer to "what licence is this". Short is only a proxy for empty. It warns.
