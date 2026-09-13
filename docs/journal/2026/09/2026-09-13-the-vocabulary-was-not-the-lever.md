# 2026-09-13 — the vocabulary was not the lever (roadmap 5.36)

- **Session scope:** roadmap 5.36 — measure whether KIR's silence about emphasis makes the
  ingested twin and its source disagree, and decide whether the vocabulary should change
  (spec 03 §§3.1, 4).
- **PR:** #135 (`feat/measure-emphasis-disagreement`). Follows #134, merged as `230c0f4`.
- **Milestone 5:** 5.36 done; 5.40 filed.
- **ADR:** [ADR-0107](../../../adr/0107-refuse-to-model-emphasis-and-name-the-lane-the-disagreement-is-in.md).

## The item was filed as a vocabulary question and is not one

5.36 came out of 5.29 with a prior and a test for it. The prior: KIR modelling no emphasis is
correct and should stay, because emphasis is not a naming and the indexed text is the same
either way. The test: `~~struck~~` survives markdown-it as literal characters and vanishes
through docling as formatting, so the twin and its source would disagree about a document
neither lane thinks it damaged. Measure that first; if it is zero occurrences, record the
refusal and close.

The prior holds. Everything else about the sentence turned out to be wrong, and both errors
were worth the afternoon.

## What the two lanes actually disagree about

Eighteen constructs, each put through both lanes end to end — the authored profile on one side,
source Markdown through pandoc's `gfm` reader to HTML and that HTML through docling on the
other. Twelve diverge, and eleven of them are not strikethrough:

| construct | profile KIR | twin KIR |
|---|---|---|
| `~~struck~~` | `A ~~struck~~ word.` | `A struck word.` |
| `<b> <strong> <i> <em> <u> <s> <del> <ins> <mark>` | `A <u>lined</u> word.` | `A lined word.` |
| `<sub> <sup>` | `Water is H<sub>2</sub>O.` | `Water is H 2 O.` |

Six agree, and they are the ones the prior was about. `**bold**`, `*italic*` and `_italic_`
reach both indexes as the bare word. `~struck~`, `x^2^` and `~/.local/bin/uv` are left alone by
*both* readers — GFM's strikethrough needs the doubled tilde, and neither subscript nor
superscript is in `gfm` at all. That last row matters more than it looks: it is why the eighty-four
stray tildes and nineteen carets in this repository's own prose are not a disagreement. They are
approximately-signs, home directories and exponents, and neither reader touches them.

## The count is not zero, and the first scan said it was

The strikethrough this item was filed against occurs in **none** of the three corpora — 170
documents here, 81 of uv's, 81 in the twin. I had a measurement saying zero for everything and
was ready to write the refusal the item's own escape hatch allowed.

The guard found the site the measurement had missed. My scan had checked `<u>` because `<u>` was
the tag in the example; the guard checked all eleven because the end-to-end run had said all
eleven diverge, and it failed on the first run against `uv-docs/docs/index.md`:

```html
<p align="center">
  <i>Installing <a href="https://trio.readthedocs.io/">Trio</a>'s dependencies with a warm cache.</i>
</p>
```

The profile indexes that paragraph as its own characters, markup included. The twin indexes
`Installing Trio 's dependencies with a warm cache.` Two corpora, one document, genuinely
different, and neither lane reporting damage — 5.36's prediction, reached by a route it did not
anticipate. Writing the guard before the conclusion is the only reason this session did not ship
a refusal resting on a number that was wrong.

## The finding

**Adding an emphasis field to KIR would not move one character of that document.**

For the eleven HTML constructs the profile does not parse the markup at all. HTML is disabled
because authored content is untrusted (D-017), so the block never becomes inline tokens and
there is no emphasis to record — the field would be filled from `em_open` tokens that are never
produced. Making KIR able to hold it would mean enabling raw HTML, which is a decision already
taken, in the other direction, for a reason that has not changed.

For strikethrough the field is not needed either. With the GFM rule enabled the adapter flattens
the construct into node text like every other inline markup it does not model — measured
directly, `A ~~struck~~ word.` becomes `A struck word.`, spans empty, warnings empty, **no KIR
change whatsoever**.

So both halves are parser coverage, not vocabulary. One half is owned by D-017 and settled. The
other is owned by spec 03 §3.1, which already fixes this profile at "CommonMark + GFM tables" —
so the current behaviour is the specification's row implemented correctly, and enabling
strikethrough would be widening a frozen contract to fix zero measured occurrences. The refusal
stands; its stated reason does not.

## What the disagreement costs, which is nothing yet

It does not reach matching. FTS5's `unicode61` discards the punctuation, so a corpus holding
`~~--legacy~~` still answers a search for `struck` and for `legacy` — checked on a two-document
corpus, both forms ranking for both queries. What differs is the BM25 denominator and the
passage a reader is handed. And `docs/index.md` is judged by no case on either set, so nothing
measurable moves today.

"Today" is the word that needed an assertion rather than a memory, so it has one: the extent is
pinned to exactly that document, and that document is pinned as unjudged. The failure message
says to re-open 5.36 rather than edit the expected set, because an argument from extent is only
as good as the extent.

## One sentence removed

`profile_markdown_it`'s docstring has said since 2.4 that raw HTML *"reaches KIR as an `opaque`
node instead"*. It does not and cannot: with `html: False` markdown-it emits no `html_block`
token, the adapter's branch for one is marked unreachable, and even that dead branch builds a
paragraph. The adapter's own module docstring has always said the true thing — *"it survives as
literal text"* — so the repository was carrying both sentences, and the wrong one was in the
file that defines the profile.

It cost real time: it is why this session spent its first pass looking for opaque nodes in the
corpora and finding none, which is exactly what you would find if you were looking for something
that does not exist. One item after ADR-0100 was written about a promise kept in a docstring and
nowhere else, the same file had a docstring describing behaviour the code cannot produce.

## Lesson

The escape hatch in an item's own text — "it may be zero, in which case close it" — is an
invitation to stop measuring at the first zero. This one was wrong, and what caught it was
writing the guard *before* writing the conclusion, so the assertion had to survive the corpus
rather than the corpus having to survive my summary of it.
