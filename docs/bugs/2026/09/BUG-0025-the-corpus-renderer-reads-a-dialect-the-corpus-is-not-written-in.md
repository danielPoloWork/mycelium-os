---
id: BUG-0025
title: the ingested corpus is rendered by a pandoc dialect that cannot read its fenced blocks, losing 127 headings and inventing 59
status: fixed
severity: high
reporter: internal
discovered: 2026-09-12
affected-versions: "0.2.0 onwards (introduced by PR #57, roadmap 4.10)"
fixed-in: "0.5.0"
---

# BUG-0025: the ingested corpus is rendered by a pandoc dialect that cannot read its fenced blocks, losing 127 headings and inventing 59

- **Component:** `tools/build_ingested_corpus.py` (the corpus generator, not the product)
- **Found by:** roadmap 5.24, filed at 5.22
- **Fixed by:** PR #122, roadmap 5.24,
  [ADR-0095](../../../adr/0095-read-the-corpus-in-the-dialect-it-is-written-in.md)

## Summary

`tools/build_ingested_corpus.py` rendered the vendored `uv` documentation into DOCX, HTML and
PDF with `pandoc --from markdown` — pandoc's *own* extended dialect. The corpus is
mkdocs-material Markdown, whose fenced blocks carry bare attributes:

```text
```toml title="pyproject.toml" hl_lines="4"
```

pandoc's `markdown` dialect spells a fenced block's attributes in braces
(`` ```{.toml title="x"} ``) and rejects the bare form. It therefore reads the **opening
fence as prose** — and the *closing* fence, being the next unambiguous one, opens a block
instead of shutting one. Every block boundary after it is inverted until the next fence that
pandoc can read: headings, prose and links fall **inside** code blocks, and code falls out of
them.

Measured over the corpus's 81 documents: **127 headings lost and 59 fabricated, across 21 of
them**. Under `gfm` — which allows an arbitrary info string, as CommonMark specifies, as
GitHub and mkdocs render, and as this project's own markdown-it reader does — the same 81
documents render with **0 lost and 0 fabricated**.

## Reproduction

```bash
printf 'Before.\n\n```yaml title=".gitlab-ci.yml"\nkey: value\n```\n\n## A heading\n\nAfter.\n' \
  | pandoc --from markdown --to html
```

The fence becomes `<p><code>yaml title=".gitlab-ci.yml" key: value</code></p>`. With a real
document the damage follows: on `docs/guides/integration/gitlab.md` the rendering put
`## Caching`, its prose and its YAML block inside one `<pre><code>` element, and invented an
`<h1>` out of fence content further down. Swapping `--from markdown` for `--from gfm`
reproduces the source's four headings exactly.

## Why nothing downstream could see it

This is the part worth keeping. Every stage after the renderer behaved correctly:

- **docling** read `<pre><code>` as a code block, because that is what the HTML said.
- **The adapter** mapped it to a KIR `code_block`, correctly.
- **The projector** fenced it faithfully — and after roadmap 5.22 taught it to pick a fence
  long enough to contain its content, it fenced *all* of it, which is why the symptom got
  worse when the projector got better.
- **The fidelity report** correctly reported no loss: nothing *was* lost between the
  rendering and KIR. It accounts for the parse, and the parse was faithful.

The loss happened one step earlier than anything in the product can observe, between the
Markdown and the rendering, and only the generator sees both sides.

## Symptom as filed

Roadmap 5.24 filed this as *"ten blocks across nine ingested documents are code blocks that
should not be"*, found at 5.22, and offered three hypotheses: docling's HTML backend, our
adapter, or an unreported fidelity loss. All three are wrong, and the item said to read the
docling output before changing anything, which is what found that. The true scope is also
larger than the symptom: counted as blocks that swallow a heading the source document has,
it is **22 blocks across 10 documents**; counted as structure, 127 headings.

## Fix

`READER = "gfm"` in the generator, the whole corpus re-rendered, re-ingested, its judged
anchors re-carried and both baselines re-blessed. A new pre-render guard,
`refuse_unreadable_sources()`, compares every source document's ATX headings against the
headings pandoc's own AST reports under the configured reader, and **refuses to render
anything** if a document's structure does not survive — so the dialect cannot drift back
silently. It exits 1 under `markdown` and 0 under `gfm`, which is the test that it is not
vacuous.

## What the fix cost, and who gained

Re-rendering moved 71 of the 81 renderings and every evidence filename with them (each is
named after its source's digest). On the frozen release set, matched judgements, both
retrievers re-blessed:

| slice | Mycelium before → after | `grep` before → after |
|---|---|---|
| conceptual | 0.6574 → 0.6574 | 0.6497 → 0.6497 |
| exact | 0.7893 → **0.7602** | 0.7463 → 0.7492 |
| fact | 0.5027 → 0.5048 | 0.4379 → 0.4420 |
| relationship | 0.5503 → **0.6473** | 0.5494 → 0.5494 |
| symbol | 0.5832 → 0.5832 | 0.4980 → **0.5915** |
| **overall** | **0.6018 → 0.6130** | **0.5564 → 0.5746** |

The incumbent gains more than we do (+0.0181 against +0.0112) and **the reported lead
narrows, +0.0454 → +0.0384**. A corpus repair made to flatter the product does not do that.

## Prevention

- The pre-render guard above, which would have caught this on the day the corpus was first
  rendered.
- The lesson generalised: a generator that transforms a corpus is the only thing that can
  compare the corpus with its transformation, so structural claims belong there. The fidelity
  report cannot make them — by construction it can only account for what arrived.
