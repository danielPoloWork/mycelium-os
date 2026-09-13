# ADR-0106: Escape what CommonMark will see, and keep the repairs that worked

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0093](0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md)
  (the block-shape escapes this corrects, and the indented-line gap it leaves standing),
  [ADR-0099](0099-ask-the-compiler-whether-the-prose-survived.md) (the read-back invariant
  whose fallback this changes), [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md)
  (ask the reader, do not predict it), [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md)
  (the precedent for reading a single case that a corpus change moved),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md) (why G3 declines to
  enforce across a corpus change); D-007, D-010; spec 02 §5, spec 03 §4; roadmap 5.28, 5.35

## Context

Roadmap 5.35 was filed as a residue: *eight projected blocks lose their leading whitespace,
and no escape reaches it.* One to three leading spaces are stripped by CommonMark inside a
paragraph, four being a code block; a PDF's text layer renders a directory tree or an
indented TOML continuation; and a backslash cannot help, because the escape is defined only
before ASCII punctuation. The item offered two honest answers — accept and report it, or
decide that an indented run is a *block* KIR should model — and said to read one of the four
documents before choosing.

Reading them says the premise is incomplete. The eight blocks lose **53** source lines
between them, and only **20** of those are a leading space. The rest are three other things:

- **Inline constructs the escape already knows how to repair.** `__init__.py` read as strong
  emphasis and indexed as `init.py`; `` `namespace = true` `` read as a code span;
  `[[tool.uv.index]]` read as a reference and indexed as `tool.uv.index`. These are precisely
  the defects ADR-0099 exists to fix, and they were being lost anyway — because `_repaired`
  tries the escape, finds it does not achieve *full* read-back (the space is still gone), and
  falls back to writing the block **unescaped**. The repair that worked was discarded along
  with the one that did not.
- **Block markers under one space.** ` + cchardet==2.1.7` in `config.pdf`. `neutralise`
  matched its shapes against the raw line, but CommonMark strips up to three leading spaces
  *before* it looks for block structure — so the line was prose to the projector and a bullet
  to the compiler, and the paragraph split into a paragraph and a list.
- **Headings under one space**, the same blind spot with `#`.

So the loss was never only whitespace, and accepting it as filed would have accepted 33 lines
that had nothing to do with whitespace and that the lane already knows how to keep.

## Decision

**`neutralise` tests each line as the compiler will see it** — with up to three leading
spaces removed — and puts the spaces back in front of the backslash it writes. Four or more
spaces are still left alone: that is an indented code block whatever precedes it, no
backslash reaches it, and ADR-0093's gap is unchanged and still measures empty.

**A block that cannot be made whole keeps the repairs that worked.** When neither the plain
nor the escaped rendering reads back, `_repaired` now writes the escaped one *if the two read
back differently at all*, and the plain one when they do not.

**That choice needs no metric, because an escape is inert.** Every character `_escaped`
backslashes is ASCII punctuation, so CommonMark consumes the backslash and hands the reader
the character — the property `test_the_escape_costs_the_text_nothing` has pinned since
ADR-0093. An escaped rendering can therefore only ever return *more* of the source than the
plain one, never less. So a difference between the two read-backs is, by construction, text
the plain rendering was losing; there is nothing to weigh and no threshold to invent. Where
they read back identically, escaping achieved nothing and no backslash is written for
nothing.

**The residue is accepted and reported** — roadmap 5.35's first option, taken on the
measurement rather than ahead of it. With both corrections the eight blocks lose **34** lines
and **every one of them is a leading space**: the loss is halved and what remains has exactly
one cause, which is the one the item named.

**The KIR option is refused on the evidence.** Modelling an indented run as a block would
require the projector to decide what an indentation *means* — a tree drawing, a TOML
continuation, a traceback — from a PDF text layer that carries no such distinction. That is
parsing research, which D-007 says this project adapts rather than performs, and it would put
the decision in the one place spec 03 §4's closed node vocabulary cannot express it. Nothing
in the residue asks for it: the content of every one of those 34 lines is present in the
chunk, one to three spaces to the left of where the source had it.

## Alternatives Considered

- **Accept all 53 lines as filed.** Rejected: 33 of them are repairable by machinery this
  project already built and tested, and accepting them would have retired ADR-0099's promise
  for exactly the blocks that needed it most.
- **Substitute a character that survives** — a non-breaking space, `&nbsp;`, a fenced block
  around the tree. Rejected for the reason roadmap 5.35 names: each one puts characters in
  the evidence document that the source did not have, which is the text-moving this lane
  refuses — and a fenced block is what roadmap 5.22 spent an item taking *out* of these very
  documents.
- **Order the two renderings by lines lost, preferring plain on a tie.** Implemented first,
  then replaced: it cannot see a line that loses *both* its indent and an identifier, calls
  that a tie, and writes the identifier away. Resting the rule on the escape's proved
  inertness is both simpler and strictly more faithful.
- **Model an indented run as a KIR block** (roadmap 5.35's second option). Refused above.
- **Undo the change because one eval case fell.** Rejected — see below; the corpus is more
  faithful, the ranker is untouched, and D-010 is the rule that settles it.

## Consequences

- **On the vendored ingested corpus**: source lines lost by the eight unreadable blocks
  **53 → 34**, all 34 now leading-whitespace only (from 20 of 53); blocks written with
  escapes 34 → 39; blocks that do not read back **8 → 8**, unchanged and still counted. Three
  evidence documents change; zero backslashes reach any chunk's indexed text, asserted.
- **`escaped` and `unreadable` now overlap.** A block can be both — escaped for what escaping
  fixed, unreadable for what it did not. Both counters stay true of it, and both docstrings
  say so. `unreadable`'s docstring also stops claiming zero, which it has not been since
  roadmap 5.28.
- **One evaluation case moved, and the mechanism is measured.** `u-1022` (uv-ingested/release,
  `relationship`) falls 0.8847 → 0.7872, taking the slice from 0.6473 to 0.6229 (−3.8 %) and
  the overall from 0.6187 to 0.6144. Neither of its judged anchors is in a changed document.
  Its grade-3 anchor is at rank 1 on both sides; its grade-2 anchor moved from rank **10 to
  11** — across the boundary nDCG@10 cuts at. The cause is corpus statistics, not ranking:
  recovering the lost text added a chunk (591 → 592) and raised the document frequency of
  `project`, `environment` and `run` — three of that query's own content words — by one each,
  which lowers their IDF. **The grep arm did not move at all**, on any case or any slice,
  because it ranks by term counts rather than by corpus-wide statistics; that is the cleanest
  confirmation available that nothing about retrieval changed. G3 reported the slice and
  declined to enforce it, which is what ADR-0045 built it to do across a corpus change, and
  both arms were re-blessed with the diff in the PR body.
- **Nothing in retrieval was touched** — no ranker, no weight, no configuration — so this is
  the shape ADR-0044 already named: the corpus moved and one case crossed a rank boundary.
  D-010 decides it: the product got more faithful and the benchmark followed, which is the
  direction that rule exists to protect.
- The carried cases and `eval/carry.json` are **byte-identical**: coverage is computed over
  word tokens, and the recovered characters are punctuation the tokenizer already dropped.

## References

- Spec 02 §5 (the evidence lane, "verbatim"); spec 03 §4 (the closed node vocabulary);
  D-007 (adapt engines, do not do parsing research); D-010 (fix the product, not the
  benchmark).
- `src/mycelium/ingest/projection.py` — `neutralise`, `_neutralise_line`, `_repaired`.
- Tests: `tests/test_ingest_projection.py` (every opener under one to three spaces, the
  four-space gap left standing, the escapes kept on an unreadable block, the plain fallback
  when escaping recovers nothing, and the list marker that no longer splits its paragraph).
