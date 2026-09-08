# 2026-09-08 — the section that defines a sibling (roadmap 4.34)

- **Session scope:** roadmap 4.34 — `u-1007` (`uv tool install`) has scored 0.0000 since it
  was written, on the set gate G3 enforces. Diagnose it, from the documents.
- **PR:** #85 (`test/diagnose-u-1007-symbol-case`). Follows #84 (4.32), merged as `94fc5b9`.
- **Milestone 4:** 4.34 done; 4.33, 4.36 open, plus 4.37 and 4.38 filed here.

## The item gave two hypotheses and an order to check them in

4.34's own text: *"this may be the ranking problem 4.11 addressed for chunks rather than a
reach problem — or the judgement may be naming the wrong home for a command that has two.
Read the case from the documents first."* Both halves turned out to be checkable in a few
minutes, and checking them in that order mattered — the ranking measurement is what made the
judgement question askable rather than speculative.

**It is not a reach failure.** The judged chunk comes back at **rank 11** of 50, BM25 4.0321
against rank 10's 4.0789. That is a 1.1 % gap, and ranks 1 to 11 span 5.09 to 4.03 — eleven
chunks inside 21 % of each other, every one of them genuinely about `uv tool install`. So
the case was not failing because retrieval could not find the passage. It was failing on a
tie-break.

That is the sentence that decided the item. A judged case whose verdict turns on which of
two near-tied chunks lands tenth is not measuring retrieval, and no ranking change should be
proposed to move it.

## What reading the documents said

`uv tool install` has two homes in this corpus, and the judgement named the lesser one.

The judged anchor, `concepts/tools.md#the-uv-tool-interface`, is about the *interface*. It
mentions the command in one clause — "Tools can also be installed with `uv tool install`, in
which case their executables are available on the `PATH`" — and its own document opens by
pointing somewhere else: "See the tools guide for an introduction … this document discusses
details of tool management."

Where the corpus documents the command is `guides/tools.md#installing-tools`: what it does,
where the executables land, `uv tool update-shell`, how it differs from `uv pip install`,
package-versus-command semantics, versions, sources, `--with`,
`--with-executables-from`. And this corpus vendors **no CLI reference** — `reference/cli.md`
is one of the unresolved links every build of it prints — so that section is not one home
among several. It is the documentation.

Two things then made it conclusive rather than arguable.

**The slice already had a convention, and this case is the only one that breaks it.** All
three `symbol` cases added at 4.26 grade *the section that documents the command* at 3 —
`u-1017` → `#checking-the-lockfile`, `u-1019` → `#requesting-a-version/python-version-files`,
`u-1025` → `#exporting-the-lockfile` — and `u-1019` grades a feature-list mention at 1 with
the reason spelled out: "the list is graded 1 because it answers only that the command
exists." `u-1007` followed neither.

**And the anchor it named is the right answer to a different question.** `u-0006` (`uvx`,
uv/dev) grades that same section 3, and correctly: it is where `uvx` is *defined* — "a `uvx`
alias is provided for `uv tool run` — the two commands are exactly equivalent". The section
that defines `uvx` is not the section that documents `uv tool install`, and the judgement
had reused it as though it were.

## The check that it was not fitted

The obvious objection to any re-judgement that raises a score is that the score is why it
was written. Here the arithmetic answers it: the judgement written from the documents scores
**less** than the one written for the number.

| judgement | nDCG@10 |
|---|---|
| as it stood (concepts @2) | 0.0000 |
| guide section @3, alone | **0.4307** |
| guide @3 + concepts @2 | 0.3390 |
| guide @3 + concepts @2 + list @1 — **shipped** | 0.3742 |

nDCG's ideal gain grows with every relevant item, and the retriever still misses the
concepts section at rank 11 — so keeping a true relevance costs 0.06. Dropping it would have
scored better and been re-fitting in the direction nobody inspects.

## What it costs

Exactly one case moves, on all four corpus × retriever combinations; every other case and
slice is identical to within 1e-6. And the incumbent gains **twice** what we do:

| set | retriever | u-1007 | overall |
|---|---|---|---|
| uv/release | mycelium | 0.0000 → 0.3742 | 0.5858 → 0.6021 |
| uv/release | grep | 0.0000 → **0.7453** | 0.4849 → 0.5173 |
| uv-ingested/release | mycelium | 0.0000 → 0.3390 | 0.6153 → 0.6300 |
| uv-ingested/release | grep | 0.0000 → 0.3936 | 0.5046 → 0.5217 |

The lead on uv/release narrows from +0.1009 to **+0.0848**. A correct judgement handed the
incumbent a case it wins two to one, which is the shape of a set getting more honest rather
than more flattering.

## Two things found on the way, filed rather than absorbed

**4.37 — `u-0006` has the same gap.** Its grade-3 anchor sits at rank 13 for `uvx`, its
grade-2 anchor is not in the top 50 at all, and `guides/tools.md#running-tools` — where the
guide teaches the command — sits at rank 3, unjudged. It also scores 0.0000. It is filed
rather than fixed here for a reason worth stating: it is a **dev**-set judgement, and the dev
set is the surface every future candidate is developed against. Moving it deserves a visible
decision, not a paragraph inside another case's change.

**4.38 — the documenting section is the longest chunk, and loses for it.**
`#installing-tools` is 409 tokens, the longest in the candidate set, and BM25 puts it 4th
while grep's occurrence count puts it 1st. ADR-0058 found the same shape in `u-1006` — gap
in the `text` field, 385 tokens against 164. Two named cases in two slices now, which is
what 4.25 closed asking for. Filed with the refusal history attached, because thirteen
re-rankings are refused and the oracle bound says the unit of indexing is not where this
closes: what is new is only that the mechanism has cases to move rather than a mean to chase.

## How it stayed inside the rules

No file under `src/` was touched, so the conjunction `check_frozen_release_sets.py` refuses
is irrelevant rather than merely satisfied. The judgement lives in
`tools/build_uv_docs_cases.py`, which validates every anchor against a real build before
writing the set; the ingested twin was re-carried by its own generator and reproduces
byte-for-byte under `--check`. One anchor does not survive that carry — the feature list maps
at coverage 0.42, below the floor — so the twin's `u-1007` carries two anchors of three,
which is why it scores 0.3390 where the source set scores 0.3742.

Both frozen baselines are re-blessed, both retrievers, in this change: a bless rides with
the judgement change that occasions it, and leaving G3 disarmed would make re-arming it
somebody's errand. It reads "same corpus, same boundaries, same judgements, no enforced slice
regressed", 5 of 6 slices enforced.
