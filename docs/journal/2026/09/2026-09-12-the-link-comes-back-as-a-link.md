# 2026-09-12 — the link comes back as a link (roadmap 5.18)

- **Session scope:** roadmap 5.18 — nine links in ten never reached the graph from an ingested
  document, because the projector rendered reference nodes by nobody (spec 02 §5, spec 03 §§3, 6;
  threat model B11).
- **PR:** #117 (`feat/carry-references-into-tier-2`). Follows #116, merged as `dc8bc77`.
- **Milestone 5:** 5.18 done; 5.22 filed. Remaining open: 5.19, 5.21, 5.22. BUG-0023 filed and
  fixed; BUG-0024 filed.
- **ADR:** [ADR-0090](../../../adr/0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-asserted-them.md).

## The item assumed a frontmatter key; the measurement said the body

5.18 was filed with a home in mind — *"where the references go (spec 03 §3 closes the frontmatter
field set, so a new key is a spec change)"* — and left the door open with *"whatever shape they
take"*. Before choosing I parsed the 81 vendored sources again and asked the only question that
decides it: can each reference go back where it stood?

A KIR reference node has a label and a target and no offset. The adapters flatten inline content
deliberately (ADR-0006), so a link's position in its paragraph is gone. What is not gone is the
label, which the paragraph's text still contains. Searching for it from a cursor that advances
with each placement finds **507 of 509** references; the two it misses have no label at all,
anchors around images. And because the compiler flattens `[label](target)` back to `label`, a
block with its links restored re-parses to the very text it had. The chunk does not move. The
anchor does not move. The score does not move — with one exception, measured below, that turned
out to be somebody else's defect.

That makes the frontmatter key the worse home on every axis: it costs a spec change ADR-0082
had just written a lint to defend, it cannot say which chunk a link sits in, and it leaves the
projection a document whose links a reader cannot follow. Its one merit — the body stays the
same — the body already had.

## Why this is safe now and was not at 4.3

The projector dropped reference nodes as threat-model control B11: *the projector emits text,
never assertions*. Roadmap 5.7 measured that control and found it covered the one input format
whose parser makes a reference node; HTML, DOCX and PDF prose reached the projection verbatim
and `[[api]]` compiled to an `authored` edge. 5.7 moved the guarantee to where an assertion is
made — every edge from an `ingested` document is `extracted` — and in doing so made the old
control redundant without saying so. This item says so. With the compiler as the judge, the
projector may be faithful, and dropping a source's links was a fidelity cost B11 had been
charging for nothing.

The B11 row and its STRIDE row are restated rather than quietly edited, and the property is now
asserted end to end: a Markdown source with `[[api]]` is ingested, projected with the wikilink
intact, built, and produces one `extracted` edge and no authored one.

## The defect that was waiting for this

On Windows, 159 of the 507 targets came back spelled with backslashes. docling types a relative
`href` as a `Path`, the adapter called `str()`, and the string was this machine's. ADR-0079 had
noted it as changing no output, which was true while no target was written anywhere. The moment
targets go into a committed projection, a corpus regenerated here would fail its own reproduction
check on Linux. Fixed in the adapter (`as_posix()` for a `Path`), tested with a `PureWindowsPath`,
filed as BUG-0023 — the note at 5.7 was right to name it, and the right time to fix it was then.

## What it yields, and what did not move

The ingested twin: links reaching the compiler **30 → 560**, edges **54 → 366** (293 `links_to`,
each with its chunk; 305 of 366 `extracted`), unresolved warnings 12 → 42 — all forty-two
naming sources the corpus never vendored, the family the authored twin's 54 belong to. The
authored twin, for scale: 657 links, 321 edges, 149 distinct targets against the twin's 137.

Regenerating the projections — 67 of 81 change, the rest carry no references — was the cost the
item warned about, and measuring it corrected my own prediction. The carried case set reproduces
byte-for-byte and 584 of 585 chunks keep their text to the byte. One does not.

## The one chunk that moved

I first believed nothing had, because `stamp_baseline_fingerprints.py --check` printed *already
carries every fingerprint*. That tool verifies fingerprints are *present*; it compares nothing
that is already there. Gate G2's currency test, which does compare, failed in the full ladder, and
rebuilding `HEAD`'s projections beside the new ones found the difference in a single chunk of
`dependencies-docx-d90e9be4.md`: lines 741–768, where the chunk text now reads
`[dependency specifiers](https://packaging.python.org/…)` — link syntax the compiler should have
flattened to its label and could not, because that region is *code* to it. An earlier paragraph
begins with a literal ```` ```toml ```` — a code block flattened into prose upstream, smart quotes
and all — the compiler opens a fence with no closing partner, and a heading and its prose are
swallowed. Four of the 81 projections carry such a region; `config-pdf` loses lines 52–440. That is
a defect four items older than this one, filed as BUG-0024 with roadmap 5.22 for the escape the
chats projector already applies to its own two shapes (ADR-0077).

What the one chunk moved is on the record rather than smoothed over. Both fingerprints of the
ingested twin; one release case for the product, `u-1021` 0.3155 → 0.3333, and its dev set not at
all. The incumbent moved more — `exact` up, `fact`, `relationship` and `symbol` down, overall 0.5217
→ 0.4865 — because grep ranks by term counts without length normalisation and a 28-line code chunk
full of link targets now outranks the judged passage for several queries. The product's lead on
that set widens from +0.115 to +0.151 for a reason that is not a product improvement, and the ADR
says so in those words. The ingested baseline is re-blessed for both retrievers, gate G2's verdict
is re-recorded with the maintainer's uncommitted documents set aside for the record and restored
after, three of its four `uv` numbers reproduce byte-identically and the fourth moves by exactly
that case. The `lexical` default stands.

## Refused

Appending an unplaceable reference to the end of its block, so nothing is lost: it would put the
label into the chunk twice, for two references out of five hundred that have no label to lose.
Rendering images: a docling picture's target is `#/pictures/0`, and a broken image in every
projection helps no one. Escaping a pipe to carry a labelled wikilink through a table cell: a
bet on someone else's parser, and losing it puts syntax into a chunk as text.

## Lesson

A control that has moved leaves a shadow where it stood, and the shadow keeps charging. B11's
rule survived 5.7 intact in the code and the docstring while its justification had been
relocated to the compiler; the cost it kept extracting — 279 links per corpus — was invisible
because nobody had counted what the projector threw away. Count what a control costs when its
reason changes, not only when it is written.

And the smaller one: a tool whose flag is `--check` and whose output says *already carries* is
read as a comparison by anyone in a hurry. It was not one, the prediction it appeared to confirm
was wrong by one chunk, and the gate that does compare caught it. Prefer the gate.
