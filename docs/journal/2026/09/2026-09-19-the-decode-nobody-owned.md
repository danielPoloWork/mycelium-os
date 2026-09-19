# 2026-09-19 — the decode nobody owned (roadmap 6.15)

- **Session scope:** roadmap 6.15 — what an ingestion projects depended on which unrelated
  packages happened to be importable.
- **PR:** #169 (`fix/pin-the-html-detector`). Follows #168 (6.20), merged as `b8975ee`.
- **Milestone 6:** 6.15 closed. Open: 6.8, 6.12, 6.23, 6.24, 6.25, 6.26, 6.27, 6.28, 6.29,
  6.30, 6.31, 6.32.
- **Records it writes:** [ADR-0134](../../../adr/0134-own-the-decode-and-stop-asking-whatever-is-importable.md),
  [BUG-0032](../../bugs/2026/09/BUG-0032-an-importable-package-changes-what-html-ingestion-projects.md).

## The item asked for two measurements first, and both changed the answer

*"Measure before choosing: the five documents that moved are the evidence, and whether the
current committed corpus was rendered with or without `chardet` is the first thing to
establish."*

**The corpus is neither.** All 62 HTML sources are valid UTF-8 and not one declares a
charset — pandoc's html5 writer emits a bare fragment without `--standalone`, so there is no
`<head>` to put one in. So the corpus is a plain UTF-8 rendering that the detectors
installed today happen to agree with, and the detector is consulted for every document,
every time, ahead of UTF-8.

**And the number is not ours.** The incident was replayed without installing anything: each
detector's answers for the 62 sources were captured in a throwaway `uv run --no-project`
environment, written to JSON, bound back into `bs4.dammit.chardet_module` as a lookup table
keyed by the bytes' digest, and the real corpus check re-run in process.

| detector | evidence documents that move |
|---|---|
| charset-normalizer 3.5.1 | 0 |
| chardet 3.0.4 / 4.0.0 / 5.0.0 / 5.1.0 / 5.2.0 / 6.0.0 | 7 |
| chardet 7.6.0 | 0 |

Two consequences. 6.6 recorded five; a replay produces seven, and the disagreement is the
thesis restated rather than something to reconcile. And **the defect is invisible on today's
resolution** — anyone re-running 6.6's experiment now, with `chardet` 7.6.0, would conclude
there is nothing here and close the item.

The seven are exactly the sources whose entire non-ASCII content is one character: an em
dash, or a single `✓`. Too little signal for the detectors that guess wrong, enough for the
ones that do not, at 0.73 confidence either way.

## Why the two obvious fixes are the wrong ones

The item proposed three answers and said they compose. Two do not survive the measurement.

**Declaring a detector** in the `ingest` extra — bs4 even publishes
`beautifulsoup4[charset-normalizer]` for it — makes one *present*, not *chosen*: bs4's
import-time chain prefers `cchardet`, then `chardet`, and only then the one we declared. The
environment 6.6 created by accident would still have overridden it. And the table above
shows the answer moving between versions of a single detector, so a locked dependency
narrows the ambiguity without removing it. A pin that cannot pin the answer is worse than
none, because it reads as a fix.

**Recording the detector's identity in the fidelity report** *as a field, the way the
parser's version is*, cannot be done at all — and finding out why was the best thirty minutes
of the session. ADR-0034 makes the report **a pure function of the KIR document**, so that
anyone holding the KIR blob can recompute it and check it against the digest. An encoding is
not derivable from the KIR. The invariant decides where the fact goes: into the KIR's own
`warnings`, which the report already copies verbatim — so the item gets what it asked for by
the only route that does not break something older.

## What shipped

A rule this repository owns: byte-order mark, then a declaration the document makes, then
UTF-8, then windows-1252, then quarantine. It is deliberately **BeautifulSoup's own chain
with the ambient step removed** rather than a new invention — which is what makes it
reviewable, and why the committed corpus did not move a byte.

The mechanism at the seam is a **byte-order mark**. The decoded text is re-encoded as UTF-8
with `EF BB BF` in front, and *that* is what docling's backend gets. A UTF-8 mark is the one
encoding declaration carried in the byte stream rather than in the markup, so it changes no
element and no character, and bs4 treats a sniffed mark as definite — ahead of the detector
it would otherwise ask. Verified both ways round:

```text
plain:                  81 evidence documents match a fresh ingestion
chardet 5.2.0 replayed: 81 evidence documents match a fresh ingestion
                        fake detector consulted: 0 hits   (62 before)
```

Not agreed with. Not asked.

## Two costs, both named

An undeclared, non-UTF-8, non-windows-1252 document — undeclared Shift-JIS — is now read as
mojibake where a detector sometimes saw through it. It arrives with a warning on the
document instead of in silence, which is the trade this project makes every time: a
deterministic wrong answer that says so beats a clever one that cannot be reproduced.

And UTF-16 without a mark is *valid UTF-8* — every other byte is a NUL — so it decodes to
text nobody authored. The rule still does not guess, because guessing is the thing being
removed; it notices that HTML cannot carry a NUL and says what the document probably is.
That case was found by a test parameter that was wrong: `text.encode("utf-16-be")` writes no
mark, and the failure was the rule doing exactly what it should with bytes that carry no
declaration at all.

## Lesson

A measurement that reproduces an old finding is worth more than the finding, because it
dates it. Replaying 6.6 turned "five documents moved" into "seven move under six versions of
one detector and none under the two installed today" — and the second sentence is what
disqualified pinning a dependency as the fix, while the first would have supported it.
