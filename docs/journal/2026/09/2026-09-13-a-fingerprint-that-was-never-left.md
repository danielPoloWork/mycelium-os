# 2026-09-13 — a fingerprint that was never left (roadmap 5.34)

- **Session scope:** roadmap 5.34 — pandoc, the other half of the ingested corpus's
  generator toolchain, has no version recorded anywhere. Check first whether the same fix as
  typst's applies before reaching for a new declaration.
- **PR:** #133 (`fix/require-pandoc-floor`). Follows #132, merged as `0735232`.
- **Milestone 5:** 5.34 done.
- **ADR:** [ADR-0105](../../../adr/0105-pandoc-gets-a-floor-not-a-pin-because-nothing-it-writes-can-be-checked.md).

## Checking the good news first

5.27 had left this one deliberately incomplete, on the hope that the same trick might work
twice: a typst PDF stamps `Creator: Typst <version>` into itself, so ADR-0098 could pin the
typesetter and test the pin against every committed file. If pandoc's DOCX and HTML did the
same, the fix here would be a test, not a new declaration.

They do not. Unzipped and read directly: a committed DOCX's `docProps/app.xml` says
`Application: Microsoft Word 12.0.0` — a string pandoc's writer always emits, regardless of
which pandoc ran — and its `core.xml` has an empty creator field. The HTML is worse than
uninformative: `_pandoc()` never passes `--standalone`, so pandoc writes a bare fragment with
no `<head>` at all, nowhere a `<meta name="generator">` could even live. `grep -ri pandoc`
over every source in the corpus returns nothing. The hope did not survive contact with the
files.

## A floor instead of a pin, and why that is not a smaller version of the same idea

Once nothing in the artifacts can be checked, the only thing left to check is the running
tool, before it runs — `require_pandoc()`, placed exactly where `require_typst()` sits, ahead
of the render loop rather than inside it, so a pandoc too old to trust fails with one clear
message instead of a raw `--sandbox: unrecognized option` partway through nine documents.

The floor itself was already sitting in the codebase, uncredited: `mycelium.ingest.parsers
.pandoc` refuses anything below major version 3 for the same reason — `--sandbox`, which both
that parser and this generator's own `_pandoc()` call unconditionally, arrived in pandoc 3.
Made the constant public rather than writing "3" twice, because the two floors are one fact
and a second copy is exactly the kind of number that drifts unnoticed.

## The pin that was already there

Reading `.github/actions/setup-pandoc` to see whether it recorded anything found that it
already does — version `3.11`, verified by digest, since PR #78 on 2026-09-07. That is five
days before roadmap 5.27 was filed and eleven before this item asked whether "pinning the
setup action" was one of the shapes worth choosing. It was already chosen, by someone solving
a CI reproducibility problem that had nothing to do with this corpus, and nobody had connected
the two. Worth being precise about what it actually covers: it is what CI's own
`PandocParser` tests run against, not a claim about which pandoc rendered the DOCX and HTML
that ship in `sources/` today — those predate the action, and nothing records what wrote them.

## What stays unrecorded, on purpose

`provenance.json` gets no new field. ADR-0098 refused one for typst because the artifact
already carries the fact and a manifest copy could only go stale next to a truth that already
exists. Here the refusal runs the other way: nothing carries the fact, so a field would be
the only copy of it, untethered from anything that could ever contradict it if it went wrong.
A number nobody can check is worse than no number — it reads as a guarantee it cannot back.

## Lesson

"Check whether the same fix works twice" is a real step, not a formality — it saved writing a
test for a fact that does not exist, and it is what turned up that half of the fix (the CI pin)
had already shipped, unconnected to the question that would eventually ask for it.
