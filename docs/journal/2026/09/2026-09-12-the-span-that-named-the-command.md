# 2026-09-12 — the span that named the command (roadmap 5.25)

- **Session scope:** roadmap 5.25 — the ingested twin names one command in six because
  projection drops the code spans. Filed at 5.23 with a one-sentence plan.
- **PR:** #123 (`feat/project-spans-as-spans`). Follows #122 (5.24), merged as `781df66`.
- **Milestone 5:** 5.25 done; 5.28 and 5.29 filed.
- **ADR:** [ADR-0096](../../../adr/0096-write-the-span-back-and-pin-the-arm-that-judges-it.md).

## The plan was one sentence and it was wrong

5.25 said: *"KIR now holds them (`KirNode.spans`, ADR-0094), so the projector can write a span
back as a span the way ADR-0090 wrote a link back as a link"*. Ten minutes of checking killed
it. `KirNode.spans` is populated by the markdown-it adapter and the pandoc adapter. The twin is
parsed by **docling** and the PDF text-layer reader. Both emit zero spans. There was nothing to
write back, and the projector was not where the work was.

This is the second item running whose premise did not survive being checked, and both times the
check was cheap. 5.24's three suspects were all innocent; 5.25's "KIR now holds them" was true
of two adapters and not of the two that matter here.

## Where the naming actually goes

docling does carry it, for HTML. An inline `<code>` inside a `<p>` arrives as a `code`-labelled
`CodeItem` **inside an `InlineGroup`**, and our adapter's inline-group branch joined the runs'
text and discarded which of them were code. So the signal reached us and we dropped it.

The other two lanes lose it earlier, and I measured rather than assumed:

| lane | what carries it | what arrives |
|---|---|---|
| HTML | `<code>` in a `<p>` | a `code` run of an inline group — recoverable |
| DOCX | pandoc's `VerbatimChar` run, 224 in one document | docling's formatting: bold, italic, underline, strikethrough, script. No monospace |
| PDF | nothing | a text layer has no inline structure |

So this item repairs HTML and reports the rest (5.29). Inferring a DOCX naming from shape — a
token with a dot in it, a word starting with two dashes — is the plausible-looking wrong answer,
and D-007 puts patching docling out of scope.

## The bound I built, measured, and did not ship

The first version put every `code` run of an inline group into `spans`, and three chunks moved.
Two were `__token__` and `__pycache__` — projected prose was reading the underscores as emphasis
and indexing `token`, so wrapping them *repaired* the text. The third was worse: docling had
nested a `<pre><code>` **block** inside an inline group, and the span swallowed a whole sentence
including a Markdown link, so the link's target entered the indexed text and a heading slug
changed.

docling offers nothing to separate those: same label, same `code_language`, same
`content_layer`, no provenance. So I measured the two populations from the HTML itself, where
the distinction is ground truth. Inline `<code>`: 1 368 of them, 1 to **55** characters, zero
newlines. `<pre><code>`: 531, median 95, 62 % holding a newline. They separate — a length bound
would work.

I did not ship it. The property I actually need is *the block's text does not move*, which is
testable exactly, and a length constant fitted to this corpus would guard it only by proxy —
and would miss `__token__`, which is short. So the projector asks the compiler instead: parse
the block before and after, compare the block nodes' text, keep only what reads back
identically. No constant, and it catches both shapes.

## A check that was wrong in an instructive way

My first round-trip check compared *all* KIR nodes, references included. A rendered link adds a
`link` node the bare text does not have, so every span in a block that also held a link failed:
253 dropped instead of 66. The check was asking a question next to the one it meant. Comparing
only block nodes — which is what a chunk's text is — fixed it.

Final: **1 217 of 1 289 spans carried**, 66 refused for sitting inside a link label, 6 by the
round-trip. Commands minted by the twin: **11 → 59**, against uv's 69. `uv python pin` — the
command the item named, because `u-1019` cannot be answered without it — is among them, with a
judged-relevant site at lexical rank 1. Zero chunks moved text, zero anchors moved, and gate G3
reports *"same corpus, same boundaries, same judgements"*.

## The consequence the item did not plan for

With the namings carried, the symbol leg fires on all four of the twin's judged `symbol` cases
where it could fire on **none**. Its own ablation then earns the default on a held-out set:
`uv-ingested/release`, +5.6 % on the slice and +0.9 % overall, nothing regressing. ADR-0080's
rule is *the default follows the ablation*, and `--check` enforces it, so the flag flips on —
the first optional leg in this project ever to earn one.

I want the caveat on the record next to the result, because the number is thin: on the release
sets it is one case (`u-1025` 0.5000 → 0.6309), `ours/*` and `uv/release` are byte-identical
with the leg on, and the set that gains is the *twin* of the set that does not. What the leg
demonstrably does is compensate for what ingestion costs. That is a real benefit and a narrower
claim than "the leg is good". The honest thing was to follow the bar that was written before
the measurement rather than to re-read it now that I do not love the result — which is the same
refusal this project has made fourteen times in the other direction.

## The guard that could only give one answer

Flipping the flag made `measure_symbol_leg.py --check` report *"does not earn the default on any
set"*. The control arm is `build_retriever("mycelium")`, which runs `RetrievalConfig()` — the
shipped product. So the moment the leg ships, the control acquires the leg under test and the
ablation measures zero. The guard could accept `off` and never `on`.

The graph ablation is built the same way and has the same latent defect; it has simply never
had a leg earn its default. Both now score against a `lexical` retriever that pins every
optional leg off. While a leg ships off it is byte-identical to `mycelium`, which is why the
defect survived 5.3, 5.9 and 5.23 unnoticed and why no historical number moves.

## Lesson

An ablation arm that inherits a default cannot judge that default. It reads as correct for as
long as the answer is "no" — which, for three items, it was.
