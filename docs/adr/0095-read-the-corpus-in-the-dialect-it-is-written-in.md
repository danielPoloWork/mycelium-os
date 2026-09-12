# ADR-0095: Read the corpus in the dialect it is written in, and let the generator check that it did

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0039](0039-measure-what-projection-costs.md) (the twin, and why its
  renderings are committed), [ADR-0056](0056-make-the-format-assignment-append-only.md) (the
  rotation this re-render preserves), [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md)
  (the fidelity report, and what it can and cannot say), [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md)
  (adapt an engine, never patch it), [ADR-0093](0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md)
  (roadmap 5.22, which made the symptom visible), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (judgements frozen before the corpus moved); D-007, D-010; roadmap 5.22, 5.24, 5.25;
  [BUG-0025](../bugs/2026/09/BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md)

## Context

Roadmap 5.24 was filed at 5.22 with a symptom and three suspects: *"ten blocks across nine
ingested documents are code blocks that should not be … The question is whether this is
docling's HTML backend mis-reading a `<div class="admonition">`, our adapter mapping it
wrongly, or a fidelity loss that should be reported rather than fixed."* It closed with an
instruction — *decide by reading the docling output for one of the nine before changing
anything* — and a constraint: D-007 puts parser repair out of scope.

Reading the docling output eliminated all three suspects in one step. For
`docs/guides/integration/gitlab.md` the **rendered HTML already contains** a single
`<pre><code>` element holding the `!!! note` admonition, the `## Caching` heading, its prose
and its YAML block. docling read that element as a code block, which is what it is; the
adapter mapped it to a KIR `code_block`, which is correct; the projector fenced it faithfully;
and the fidelity report reported no loss, correctly, because nothing *was* lost between the
rendering and KIR. For `docs/concepts/projects/dependencies.md` the DOCX carries the same
heading inside a paragraph styled `SourceCode`. Every stage downstream of the rendering
behaved exactly as designed.

The loss is one step earlier, in a place no suspect list included: **we made the renderings,
and we read the corpus in the wrong dialect.** `tools/build_ingested_corpus.py` calls
`pandoc --from markdown`, pandoc's own extended dialect. The corpus is mkdocs-material
Markdown, whose fenced blocks carry bare attributes — ```` ```toml title="pyproject.toml"
hl_lines="4" ````. pandoc's `markdown` requires those in braces and rejects the bare form, so
it reads the **opening fence as prose**; the closing fence is then the next unambiguous one
and *opens* a block instead of shutting it. Every boundary after it is inverted until a fence
pandoc can read. Headings, prose and links fall inside code blocks; code falls out.

Measured across the corpus's 81 documents, by matching heading text between each source and
its rendering:

| reader | headings lost | headings fabricated | documents affected |
|---|---:|---:|---:|
| `markdown` (what was committed) | **127** | **59** | **21 of 81** |
| `gfm` | 0 | 0 | 0 |

The corpus has 554 headings; the committed renderings carried 486 of them and invented others
in their place. The worst were PDFs — `python-versions.md` lost 25 headings, `config.md` 17,
`indexes.md` 14 — because typst markup is generated from the same broken parse.

Two facts make this worse than a cosmetic defect. First, **the twin exists to measure what
projection costs retrieval** (ADR-0039); a fifth of its structure was destroyed *before*
ingestion began, so every such measurement since roadmap 4.10 has been partly measuring this
bug and attributing it to projection. Second, roadmap 5.22 made the symptom *worse* while
making the projector *better*: before it, an unescaped marker in flattened prose happened to
split those over-large blocks, and teaching the projector to pick a fence long enough to
contain its content removed the accident that was concealing the damage.

## Decision

**The corpus is read in `gfm`, because that is the dialect it is written in.** A fenced
block's info string is arbitrary text in CommonMark, in GitHub Flavored Markdown, in what
mkdocs renders, and in this project's own markdown-it reader when it compiles the very same
files. pandoc's `markdown` is the outlier, and it was chosen by default rather than by
decision. This is not parser repair and D-007 is not in tension with it: nothing about pandoc
changes, we stop asking it the wrong question.

**The generator refuses to render a corpus whose structure its reader cannot see.**
`refuse_unreadable_sources()` runs *before* anything is written — so a failure leaves no
half-rendered tree — and for every document compares the ATX headings a human reading the
Markdown would count against the `Header` blocks pandoc's own AST reports under the configured
reader. Any heading lost or invented refuses the whole run, naming the document and the
heading. The check questions the **reader**, through `--to json`, rather than a rendering:
the defect lives in the reader, and going through a writer would add a second thing to blame.

**The whole corpus is re-rendered, re-ingested, re-carried and re-blessed**, which is the only
way the decision reaches the corpus on disk. The format rotation is untouched — `--render`
rewrites `format-rotation.json` from the recorded order, so the append-only rule of ADR-0056
holds and **no document changed format or parser**. 71 of the 81 renderings carry new bytes;
every evidence filename moves with its source digest; `tools/build_ingested_cases.py` carries
the frozen judgements across by text coverage, as always, and nothing is re-judged.

**The fidelity report is not extended to cover this, and that is deliberate.** It would be
the wrong instrument and the claim would be false. ADR-0034 computes it from the parse, so it
accounts for what arrived at the KIR boundary against what the *engine* reported — and at
that boundary nothing was lost. Only the generator holds both the Markdown and its rendering,
so only the generator can compare them. Teaching the fidelity report to allege a loss it
cannot observe would put a number in a document where a guess would have to stand in for a
measurement.

## Alternatives Considered

- **Rewrite the fence attributes into pandoc's brace syntax and keep `markdown`.** Built and
  measured rather than argued away: it changes 33 renderings instead of 71, and it leaves
  **3 documents** structurally wrong against `gfm`'s 0 — it fixes the fences and not the
  admonition bodies. Rejected on both counts, and on a third: it edits the corpus before
  rendering it, so the twin would be the ingestion of a document nobody wrote. The renderer's
  existing image substitution is the precedent for such a transform and also its limit — that
  one exists because the corpus dropped its image files, and it replaces a dangling reference
  with the alt text the source already supplies.
- **`commonmark_x`.** Equivalent on the fences and equal to `gfm` on this corpus. `gfm` is
  chosen because it is the dialect this corpus is *published* in — the documents render on
  GitHub and in mkdocs — so the name records a fact about the source rather than a preference.
  `commonmark` proper is refused: it has no YAML metadata block, so it reads the pinned
  `mycelium_id` frontmatter as a heading.
- **Report it as a fidelity loss and change nothing.** One of the item's three suggestions.
  Rejected above: the fidelity report cannot see this, and a report that named it would be
  asserting a loss it did not measure.
- **Split the over-large code blocks in the adapter.** Rejected as the guess it is. A
  `<pre><code>` holding a heading is genuinely a code block in the document that was handed to
  us; re-deriving the structure its author *meant* is exactly the plausible-looking wrong
  answer this project refuses elsewhere (ADR-0018's ambiguous wikilink, ADR-0035's uncited
  claim). It would also have fixed a symptom while leaving 127 headings missing.
- **Leave the corpus and fix only the generator.** Rejected: the corpus on disk is the
  instrument, and a repaired tool with a broken corpus measures exactly as badly as before.
- **Re-render only the 21 affected documents.** Rejected: the reader changes what it reads
  everywhere — smart quotes among other things — so a corpus half-read in one dialect and
  half in another would be a third thing, reproducible by nobody, and `--check` would be
  comparing against a mixture.

## Consequences

- **The defect is gone, counted the way it was filed**: blocks that swallow a heading the
  source document has go from 22 across 10 documents to **0 across 0**.
- **The numbers move, and the incumbent gains more than we do.** Frozen release set, matched
  judgements, both retrievers re-blessed on the rebuilt corpus:

  | slice | Mycelium | `grep` |
  |---|---|---|
  | conceptual | 0.6574 → 0.6574 | 0.6497 → 0.6497 |
  | exact | 0.7893 → **0.7602** | 0.7463 → 0.7492 |
  | fact | 0.5027 → 0.5048 | 0.4379 → 0.4420 |
  | relationship | 0.5503 → **0.6473** | 0.5494 → 0.5494 |
  | symbol | 0.5832 → 0.5832 | 0.4980 → **0.5915** |
  | **overall** | **0.6018 → 0.6130** (+0.0112) | **0.5564 → 0.5746** (+0.0181) |

  The reported lead narrows **+0.0454 → +0.0384**. That direction is the check on this
  change: a corpus repair made to flatter the product does not hand the incumbent the larger
  half. `relationship` is where we gain (+0.0970) and `symbol` is where the incumbent does
  (+0.0935) — restored headings give field-weighted retrieval its section boundaries back,
  and give a term-counting baseline the command names that were buried in fenced text.
- **`exact` falls 0.7893 → 0.7602 and is named rather than absorbed.** It is one case,
  `u-1003` (0.6309 → 0.5000); the other four in the slice are unmoved, three of them at
  1.0000. Its judged passage is in `docs/concepts/indexes.md`, a PDF whose headings the old
  rendering flattened, so the anchor it carries onto now names a differently-bounded chunk.
  Filed as roadmap **5.26** rather than adjusted here, because moving a judgement in the
  change that moves the corpus is the conjunction `tools/check_frozen_release_sets.py` exists
  to refuse (ADR-0027).
- **Gate G3 reports rather than enforces on this set for one run**, because the carried
  anchors moved and the means are over different case populations. The bless re-arms it; both
  retrievers now share one snapshot, one corpus digest and one cases digest, where before the
  bless the `grep` row still described the corpus that had just been replaced.
- **Every evidence filename changed**, since each is named after its source's digest —
  222 files in the diff. The judged anchors were re-carried mechanically, 62 mapped and the
  same 3 dropped as before (`features.md#tools/0` at coverage 0.42 and its two siblings, the
  drop ADR-0062 already records); **no case gained or lost a drop**.
- **Historical records are not rewritten.** ADR-0079, ADR-0090, ADR-0093 and BUG-0024 quote
  evidence filenames that no longer exist. They are records of what was measured when it was
  measured, and a record that edited its own history would be worth less than one that shows
  the change (the rule ADR-0062 set, and roadmap 5.8 applied to the superseded layout ADRs).
- **A generator-only dependency is undeclared and bit twice.** PDF rendering needs the
  `typst` package, which the generator names in an error message and no manifest declares, so
  `uv sync` removes it; this session had to reinstall it before re-rendering, as the
  2026-09-10 session did. Filed as roadmap **5.27**.
- **The reader is now a named constant with a docstring that says why**, and the guard makes
  the choice self-enforcing. A future contributor who prefers `markdown` gets a refusal
  listing the 21 documents it cannot read.

## References

- Spec: `.draft-specs/02-architecture.md` §5 (the evidence lane), `.draft-specs/04-retrieval-and-evaluation.md`
  §7.1 (frozen sets), §7.4 (the incumbent).
- Decision log: D-007 (adapt engines, never write or patch parsers), D-010 (fix the product,
  not the benchmark).
- Re-runnable: `python tools/build_ingested_corpus.py --render` (refuses under a reader that
  cannot see the corpus), then `--check`; `python tools/build_ingested_cases.py --check`;
  `mycelium eval eval/corpora/uv-docs-ingested --against grep`.
- The one-line reproduction, and the chain it breaks, are in
  [BUG-0025](../bugs/2026/09/BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md).
