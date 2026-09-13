# 2026-09-13 — the residue that was three things (roadmap 5.35)

- **Session scope:** roadmap 5.35 — eight projected blocks lose their leading whitespace and
  no escape reaches it. Read one of the four documents before choosing between accepting it
  and modelling an indented run as a KIR block.
- **PR:** #134 (`fix/escape-what-commonmark-sees`). Follows #133, merged as `f9d9e87`.
- **Milestone 5:** 5.35 done.
- **ADR:** [ADR-0106](../../../adr/0106-escape-what-commonmark-will-see-and-keep-the-repairs-that-worked.md),
  correcting a clause of [ADR-0099](../../../adr/0099-ask-the-compiler-whether-the-prose-survived.md).

## Reading the documents, as instructed

The item was filed as a clean residue: one cause, no repair, choose between two ways of
saying so. Reading the eight blocks line by line says they lose **53** source lines and only
**20** of them are a stripped space.

The other 33 are two things, and both were the previous decision's own doing.

`_repaired` tries the escape, finds it does not achieve *whole-block* read-back — the space
is still gone — and falls back to writing the block **unescaped**. So every inline repair
that worked was discarded along with the one that did not: `__init__.py` went back to being
read as strong emphasis and indexed as `init.py`, `[[tool.uv.index]]` as `tool.uv.index`.
Those are exactly the defects ADR-0099 was written to fix, lost in the blocks that needed it
most, for a reason unrelated to them.

And `neutralise` matched its block-opening shapes against the raw line, while CommonMark
strips up to three leading spaces *before* it looks for block structure. ` + cchardet==2.1.7`
in a PDF's text layer was therefore prose to the projector and a bullet to the compiler, and
the paragraph holding it split in two.

So ADR-0099's sentence — *"every one of them is leading whitespace"* — is true about why each
block fails the comparison and false about what the blocks lose. It has a correction note on
it now, at the paragraph it applies to.

## The rule that needed no number

Fixing the fallback meant choosing between two imperfect renderings, and my first attempt
ordered them by lines lost, preferring plain on a tie. That is wrong in a way the corpus
shows: a line that loses *both* its indent and an identifier is lost under either rendering,
the count calls it a tie, and the identifier gets written away.

The better rule was already proved elsewhere. Every character `_escaped` touches is ASCII
punctuation, so CommonMark consumes the backslash and hands the reader the character — the
inertness `test_the_escape_costs_the_text_nothing` has pinned since ADR-0093. An escaped
rendering can therefore only ever return *more* of the source than the plain one. So: if the
two read back differently at all, the difference is text the plain rendering was losing, and
the escapes are kept. No metric, no threshold, and it rests on a property with a test rather
than on a number I would have had to defend.

## What it cost, and the case that moved

53 → 34 lines lost, and all 34 are now a stripped leading space. The residue finally *is*
what the item said it was, so accepting and reporting it — the item's first option — became
the right answer, taken after the measurement instead of before it. The KIR option is
refused: deciding what an indentation means in a text layer is parsing research, and every
one of those 34 lines is in the chunk anyway, one to three spaces to the left.

Then one evaluation case moved, and it took a while to be sure it was not a defect.
`u-1022` falls 0.8847 → 0.7872. Neither of its judged anchors is in a document I changed. Its
grade-3 anchor is at rank 1 on both sides. Its grade-2 anchor went from rank **10 to 11** —
across the line nDCG@10 cuts at.

The cause is corpus statistics. Recovering the lost text added a chunk (591 → 592) and raised
the document frequency of `project`, `environment` and `run` — three of that query's own
content words — by one each, which lowers their IDF. The confirmation is the incumbent: the
grep arm did not move on any case or any slice, because it ranks by term counts and not by
corpus-wide statistics. Nothing about retrieval changed; the corpus did, and a case sitting
exactly on the boundary crossed it. That is the shape ADR-0044 already named, and D-010
decides it — the product got more faithful and the benchmark followed.

## Lesson

A residue is a claim about what is left, and it is worth re-deriving rather than inheriting.
This one had been stated once, plausibly, by the change that created it — and the two extra
causes hiding inside it were both that change's own side effects, which is exactly the place
nobody looks.
