# ADR-0099: Ask the compiler whether the prose survived, and escape only where it did not

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0093](0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md)
  (the same defect one level up — block syntax the source did not author),
  [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md) (the read-back
  invariant this generalises, and the item that found the symptom),
  [ADR-0090](0090-render-the-reference-back-where-its-label-sits.md) (the references this must
  not escape), [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) (the fidelity
  report, and what it cannot see), [ADR-0039](0039-measure-what-projection-costs.md) (the twin
  whose baselines this re-blesses), [ADR-0077](0077-let-the-chats-projector-neutralise-what-it-writes.md)
  (the rule four items older); D-010; threat model B11; roadmap 5.22, 5.25, 5.28

## Context

Roadmap 5.25 found it while building something else: an HTML source says
`<code>__token__</code>`, the projector flattened the span to text, the compiler read the
underscores as strong emphasis, and the indexed text became `token` — the corpus's own word
for the thing, gone, silently. 5.25 refused to fix it there because wrapping the words in a
code span moves a chunk's text and that item's whole argument was that it does not. 5.28 is
the fix, and it asks for the repair to be *measured over the corpora rather than listed*.

This is ADR-0093's defect one level down. That item escaped the line shapes a source's prose
must not assert — a fence, a heading, a bullet — because projected prose does not get to
assert the document's structure. The same sentence is true of inline syntax and nobody had
said it: a source's prose does not get to assert emphasis, a link, a code span or an entity
either (threat model B11).

**The projector already owned the right question and was not asking it of itself.** ADR-0096
built `_reads_back` to decide whether a code span may be written: parse the candidate with the
reader the build uses, and keep the span only if the compiler extracts the same words. That
invariant was applied to spans and never to the prose they sit in.

Applying it to every block the projector emits, against the *literal source characters* rather
than against the mis-parse, gives the measurement 5.28 asked for. On the vendored ingested
corpus, 81 documents:

| | blocks |
|---|---:|
| rendered | 2 699 |
| read back as the source's own characters | 2 657 |
| **do not** | **42, in 15 documents** |

The 42 are two shapes and both are the same defect. Emphasis eats its delimiters —
`__token__` → `token`, and worse, `__init__.py` → `init.py` in `build-backend`, where the
corpus is naming a Python file. And a PDF's text layer shows `[preview](../preview.md)`
literally, because the upstream rendering flattened a link; the compiler makes that a link
again and drops the target out of the indexed text.

## Decision

**The projector asks the compiler whether each block survived, and escapes only the blocks
that did not.** `_repaired` renders the block, parses it with the build's own reader, and
compares the extracted text with the characters it was handed. When they match — 2 657 blocks
of 2 699 — nothing happens: not one backslash is written and the evidence document stays as
readable as the source it came from. When they do not, the block is re-rendered with its prose
escaped and checked again.

**The escape covers the gaps, never the placements.** `_apply` already walks the stretches
between the references and code spans the projector deliberately wrote; those renderings are
syntax this module means, and they are left exactly as they are. Only the gaps — still the
source's own characters — are backslashed. That seam is what makes the repair possible at all:
a rendered link keeps its brackets while the prose around it stops pretending to be one.

**The escaped set is not a list and is deliberately not chosen.** It is every ASCII
punctuation character CommonMark can start an inline construct with — ``\ ` * _ [ ] < & ~`` —
because it is applied only where the compiler has already answered that the text does not
survive. ADR-0093 chose a list of block shapes and could defend each one; the equivalent here
would mean predicting which pairings CommonMark makes, and that prediction is exactly what was
wrong: nobody expected `__init__.py` to be strong emphasis.

**A block that still does not read back is counted, not hidden.** `Projection` gains `escaped`
and `unreadable` beside the existing reference and span counters, for the reason the others
exist: a silent drop is the failure this lane is built to prevent.

**And the residue is a different defect, named rather than absorbed.** Eight blocks in four
documents still do not read back after escaping, and every one of them is **leading
whitespace**: a PDF text layer renders a directory tree or an indented continuation line, and
CommonMark strips one to three leading spaces (four makes a code block). No backslash reaches
it — a backslash escape is only defined before ASCII punctuation — and the only repairs
available would substitute different characters, which is precisely the text-moving this lane
refuses. ADR-0093 recorded the four-space case as "a gap rather than a decision" and measured
it empty; it is not empty any more, and it is filed as roadmap 5.35 with the shape identified.

## Alternatives Considered

- **Escape a chosen list of inline shapes** — `__`, `**`, `` ` ``, `[` — the way ADR-0093
  chose block shapes, applied everywhere. Rejected on both halves. Everywhere is wrong: it
  would backslash 2 699 blocks to repair 42 and make every evidence document harder to read
  for nothing. And a list is wrong here in a way it was not there: a block shape is
  recognisable at the start of a line, while whether `_` opens emphasis depends on what
  follows it, what precedes it and what else is in the paragraph. The compiler already knows;
  asking it is cheaper and cannot be wrong.
- **Wrap the affected words in a code span**, which is what 5.25 wanted and could not do.
  Rejected for 5.25's own reason: a code span makes its contents literal, so it changes what
  the compiler extracts, and the projector's standing promise is that the block's text does
  not move. A backslash is inert to the reader; a backtick is not.
- **Escape per character rather than per block** — find the minimal set that makes the block
  read back. Rejected as machinery this does not need: it means a search per failing block,
  and the cost it would save is cosmetic. The consequence is stated instead: a block that
  asserted syntax it did not author has *all* of its prose punctuation escaped, so
  `uv_build` in the same paragraph as a stray `[hatchling](…)` is written `uv\_build`. The
  indexed text is identical either way; the evidence file is noisier in 34 places out of
  2 699.
- **Fix it in the parsers instead**, so the flattening never happens. Rejected — it is not
  ours to fix (D-007) and it is not always wrong: a PDF text layer genuinely contains those
  characters, and the projector's job is to carry them faithfully, not to guess what the
  upstream renderer meant.
- **Report it in the fidelity report and change nothing.** Rejected: the fidelity report
  accounts for *elements* between the source and KIR (ADR-0034), and this loss happens
  downstream of KIR, between the projection and the compiler. It is invisible there by
  construction, which is why it survived four milestones.

## Consequences

- **34 of the 42 blocks are repaired**, across 15 documents, at a cost of 823 backslashes in a
  corpus of 81 documents. `__token__` and `__init__.py` are in the index again, and so are the
  targets of the flattened links.
- **Our own score does not move at all.** On `uv-ingested/release`, every slice and every case
  is identical to six decimal places: overall 0.618671 before and after. The incumbent gains
  — grep 0.574590 → **0.575367**, its `fact` slice 0.4420 → 0.4446 on one case (`u-1008`
  0.3155 → 0.3333) — so our reported lead **narrows** from +0.0441 to +0.0433. A repair that
  restores words the corpus was losing and hands the whole measurable benefit to the
  incumbent is the direction ADR-0072 and ADR-0093 both noted: nobody fits a benchmark that
  way.
- **The carry says it from the other side.** Three anchors' coverage rose to exactly
  **1.0000** — `cli.html` 0.988, `python-versions` 0.9821, `scripts.pdf` 0.9697 — because the
  words the coverage metric was missing are the words the compiler was eating. One anchor
  moved chunk (`config-pdf#/1` → `#/2`) and `u-0015` follows it; the carry maps the same 62
  anchors and drops the same 3.
- **Both arms of the ingested baseline are re-blessed**, which needs two runs: `write_baseline`
  writes `data[manifest.retriever]`, so `--against grep --bless` refreshes the product's block
  and leaves the incumbent's untouched. That is by design and worth knowing — a re-bless is
  `--bless` once with the default retriever and once with `--retriever grep`.
- **Gate G3 disarmed itself correctly** before the bless: *"the corpus has changed since the
  baseline was taken, so these numbers are not comparable — reported, not enforced"*. Read
  before re-blessing, which is the order that makes the gate mean anything.
- **Gate G2's verdict is re-recorded in the same PR**, because a corpus is a ranking input
  (ADR-0068). The check it must satisfy is that nothing *else* moved, and it holds: the
  **retrieval identity is unchanged**, the decision is still `lexical`, every set's verdict is
  the one it had, and `uv/dev` and `uv/release` — the corpus this change does not touch —
  reproduce **byte-identically on both arms**. `uv-ingested` moves, which is the point of the
  change; its hybrid arm gains most (`release` 0.6091 → 0.6251) and still does not clear the
  +5 % bar. `ours/*` drifts down a little on the lexical arm (0.4995 → 0.4972 dev, 0.5232 →
  0.5206 release) because this PR adds a document to the corpus this repository *is* —
  reported, never gated (ADR-0053).
- **The `escaped` and `unreadable` counts are on the record** per projection, so the next
  reader can see how much of a corpus needed repair without re-deriving it.
- **Filed rather than absorbed:** roadmap 5.35 — the eight blocks whose leading whitespace
  CommonMark strips, which is the same class ADR-0093 left open and can no longer be called
  empty.

## References

- Spec: `.draft-specs/02-architecture.md` §5 (the evidence lane, and what it may not assert);
  `.draft-specs/03-data-model.md` §4 (KIR's text is verbatim).
- Decision log: D-007 (adapt engines, never patch them), D-010 (fix the product, not the
  benchmark).
- Threat model B11 (untrusted content written into tier 2 asserts nothing).
- Measured this session: 2 699 blocks, 42 failing, 34 repaired, 8 residual, 823 backslashes;
  `uv-ingested/release` mycelium unchanged, grep +0.000777.
- Re-runnable: `python tools/build_ingested_corpus.py --check`, then
  `python tools/build_ingested_cases.py --check`.
- [ADR-0093](0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md),
  [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md).
