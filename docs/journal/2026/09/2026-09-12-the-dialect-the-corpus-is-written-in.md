# 2026-09-12 — the dialect the corpus is written in (roadmap 5.24)

- **Session scope:** roadmap 5.24 — why ten blocks in the ingested twin are code blocks that
  should not be, filed at 5.22 with three suspects and an instruction to read the evidence
  before changing anything.
- **PR:** #122 (`fix/ingested-code-blocks`). Follows #121 (5.23), merged as `63ffc25`.
- **Milestone 5:** 5.24 done; 5.26 and 5.27 filed.
- **ADR:** [ADR-0095](../../../adr/0095-read-the-corpus-in-the-dialect-it-is-written-in.md).
  **Bug:** [BUG-0025](../../../bugs/2026/09/BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md).

## The instruction was the whole item

5.24 offered three suspects — docling's HTML backend, our adapter, or an unreported fidelity
loss — and then said: *decide by reading the docling output for one of the nine before
changing anything*. Reading it eliminated all three in about ten minutes, which is the
strongest argument for that instruction I have met so far.

`gitlab.html`, the shape the item named, is 2 859 bytes. It contains one `<pre><code>`
element, and inside that element are the `!!! note` admonition, the `## Caching` heading, its
prose, and the YAML block under it. So there was nothing for docling to mis-read: the HTML
says "this is all one code block". The adapter mapped it to a KIR `code_block`, correctly.
The projector fenced it faithfully. And the fidelity report said no element was lost —
correctly, because none was. Every stage after the rendering did its job.

Which left the rendering, and the rendering is ours.

## What was actually wrong

`tools/build_ingested_corpus.py` calls `pandoc --from markdown`. That is pandoc's *own*
extended dialect, and the corpus is mkdocs-material Markdown. The two disagree about exactly
one thing that matters here: a fenced block's attributes. mkdocs writes

```text
```toml title="pyproject.toml" hl_lines="4"
```

and pandoc's `markdown` wants those in braces, so it refuses the line as a fence opener and
reads it as prose. The *closing* fence is then the next unambiguous one — so it **opens** a
block instead of shutting it, and every boundary after it is inverted until pandoc meets a
fence it can read. Headings, prose and links fall inside code blocks; code falls out of them.

One line reproduces it:

```bash
printf 'Before.\n\n```yaml title="x.yml"\nkey: value\n```\n\n## A heading\n\nAfter.\n' \
  | pandoc --from markdown --to html
```

Measured properly — matching heading *text* between each source document and its rendering,
across all 81 — the committed corpus had lost **127 of the Markdown's 554 headings and
invented 59 others, across 21 documents**. The PDFs were the worst: `python-versions` −25,
`config` −17, `indexes` −14, because typst markup comes out of the same broken parse. Under
`gfm` the same 81 documents render with **0 lost and 0 invented**.

So the item's count was a symptom, not the scope. Counted its way — blocks swallowing a
heading the source has — it is 22 blocks across 10 documents, not 10 across 9.

## The detector I got wrong first

Worth recording because it nearly became the finding. My first pass counted any `#`-led line
inside a code block and reported 35 blocks across 16 documents. Most of those were shell and
YAML comments — `# Pre-install keyring`, `# ...`, `# e.g., using a hash from a previous
release` — which are exactly what a code block *should* contain. The sharper test is whether
the line is also a heading in the twin's Markdown original, and that is the test that makes
the number mean something. A detector that flags real code as a defect would have sent this
item after the adapter.

## Why the fidelity report is not the answer

The item's third suspect was that this is a loss the fidelity report should count, and it is
worth saying why it is not, because the reasoning generalises. ADR-0034 computes that report
from the parse: it accounts for what reached KIR against what the engine reported. At that
boundary nothing was missing. The loss happened between the Markdown and the rendering — one
step before anything the product can see. Only the generator holds both sides, so only the
generator can compare them. Teaching the fidelity report to allege this would put a guess
where a measurement belongs.

That is where the guard went instead. `refuse_unreadable_sources()` runs before `--render`
writes a byte, and for each document compares the ATX headings a person would count against
the `Header` blocks pandoc's own AST reports under the configured reader. Any heading lost or
invented refuses the whole run and names it. It exits 1 under `markdown`, listing the 21
documents, and 0 under `gfm` — I checked both, because a guard that passes under the bug it
was written for is the vacuous test this project has already been bitten by (BUG-0020).

## 5.22 made it worse by making the projector better

The item noticed this and it deserves its own line. Before 5.22 those over-large blocks were
being split by unescaped markers in flattened prose — an accident, doing real work. Teaching
the projector to pick a fence long enough to contain its content removed the accident, and
the damage that had been there all along became visible. A fix that makes a symptom worse is
usually a fix that stopped hiding something.

## What it cost

The corpus was re-rendered whole — the documented deliberate act — re-ingested, its judged
anchors re-carried, and both baselines re-blessed. No document changed format or parser, so
ADR-0056's append-only rotation is untouched; 71 of 81 renderings carry new bytes, and since
every evidence file is named after its source's digest, every filename moved. 62 anchors
re-mapped with the same 3 known drops as before.

| slice | Mycelium | `grep` |
|---|---|---|
| conceptual | 0.6574 → 0.6574 | 0.6497 → 0.6497 |
| exact | 0.7893 → **0.7602** | 0.7463 → 0.7492 |
| fact | 0.5027 → 0.5048 | 0.4379 → 0.4420 |
| relationship | 0.5503 → **0.6473** | 0.5494 → 0.5494 |
| symbol | 0.5832 → 0.5832 | 0.4980 → **0.5915** |
| overall | 0.6018 → 0.6130 | 0.5564 → 0.5746 |

**The lead narrows, +0.0454 → +0.0384.** The incumbent gains more than we do, which is the
only direction that would convince me nobody fitted this. Restoring headings gives our
field-weighted retrieval its section boundaries back (`relationship` +0.0970) and gives a
term-counting baseline the command names that had been buried inside fenced text
(`symbol` +0.0935, to them).

`exact` fell on exactly one case, `u-1003`, and I filed it at 5.26 rather than touching the
judgement in the change that moved the corpus. That conjunction is what
`check_frozen_release_sets.py` exists to refuse, and the temptation to "just re-anchor it
while I am here" is precisely the thing the guard is guarding against.

## A small thing that bit twice

`typst` — needed for the nine PDF renderings — is declared in no manifest and named only in
an error message, so `uv sync` removes it. I reinstalled it to do this work, as the
2026-09-10 session did. Filed as 5.27, with the note that typst's *version* is part of what a
PDF rendering is, so pinning it is the half that actually protects reproducibility.

## Lesson

The three suspects were all downstream, and all three were innocent, because the question
"which of our components broke this?" quietly assumes the input was sound. The corpus's
inputs are made by a tool in `tools/`, which is not a component anybody thinks of as part of
the system — and it was the only thing that could see both the document and what it had
turned it into. When every stage of a pipeline is behaving correctly and the output is still
wrong, the error is in what was fed to the first stage.
