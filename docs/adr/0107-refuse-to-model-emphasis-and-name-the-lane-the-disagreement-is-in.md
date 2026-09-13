# ADR-0107: Refuse to model emphasis, and name the lane the disagreement is actually in

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §4
- **Related:** [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md) (the adapter,
  and the per-kind field declaration this would have extended),
  [ADR-0094](0094-name-a-command-by-the-syntax-a-corpus-names-it-with.md) (why inline *code*
  earned a field and emphasis does not),
  [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md) (the span the
  projector writes back),
  [ADR-0100](0100-declare-what-a-lane-cannot-carry.md) (the lane-split this item was filed
  from, and the lesson about unkept written promises),
  [ADR-0039](0039-measure-what-projection-costs.md) (the twin whose disagreement is the
  subject); D-017, D-022; spec 03 §§3.1, 4; roadmap 5.29, 5.36, 5.40

## Context

Roadmap 5.36 was filed at 5.29, while establishing what the DOCX lane loses. docling *does*
expose `bold`, `italic`, `underline`, `strikethrough` and `script` per run and this project's
adapter reads none of them — and there is nowhere to put them: `KirNode` has `spans`, added at
5.23 for inline code alone, and nothing else.

The item carried its own prior — that this is correct and should stay — and one reason to
look anyway: *"`~~struck~~` survives as literal characters through markdown-it, which has no
strikethrough rule, and vanishes as formatting through docling, so the twin and its source
disagree about a document neither lane thinks it damaged."* It asked for that disagreement to
be measured across the three corpora before anything was decided, and said that if the count
were zero the answer was to record the refusal and close.

The count is not zero, and the mechanism is not the one the item names. Both halves of that
sentence are measurements, and they are what this ADR is for.

### What the two lanes actually disagree about

Eighteen constructs were put through both lanes end to end — the authored profile on one side,
and on the other the twin's own path, source Markdown through pandoc's `gfm` reader to HTML and
that HTML through docling. **Twelve diverge:**

| construct | profile KIR | twin KIR |
|---|---|---|
| `~~struck~~` | `A ~~struck~~ word.` | `A struck word.` |
| `<b> <strong> <i> <em> <u> <s> <del> <ins> <mark>` | `A <u>lined</u> word.` | `A lined word.` |
| `<sub> <sup>` | `Water is H<sub>2</sub>O.` | `Water is H 2 O.` |

**Six agree**, and they are the ones the item's prior was about: `**bold**`, `*italic*` and
`_italic_` all reach both indexes as the bare word, and `~struck~`, `x^2^` and `~/.local/bin`
are left alone by *both* readers — GFM's strikethrough needs the doubled tilde, and neither
subscript nor superscript is in `gfm`.

### How far it reaches in the corpora

| corpus | documents | `~~x~~` | inline HTML emphasis |
|---|---:|---:|---:|
| ours | 170 | **0** | **0** |
| uv-docs | 81 | **0** | **one** `<i>`, in one document |
| uv-docs-ingested | 81 | **0** | **0** |

The strikethrough the item was filed against occurs **nowhere**. The one real site is
`eval/corpora/uv-docs/docs/index.md`, whose hero caption is a raw HTML block:

```html
<p align="center">
  <i>Installing <a href="https://trio.readthedocs.io/">Trio</a>'s dependencies with a warm cache.</i>
</p>
```

The profile indexes that paragraph as its own characters, markup included. The twin, whose
HTML lane hands it to docling, indexes `Installing Trio 's dependencies with a warm cache.`
The two corpora genuinely describe that document differently, and neither lane reports damage —
exactly the shape 5.36 predicted, arrived at by a different route.

### The finding that decides it

**The KIR vocabulary is not the lever on either half, and adding an emphasis field would not
move one character of that document.**

For the eleven HTML constructs, the profile does not parse the markup *at all*. HTML is
disabled because authored content is untrusted (D-017), so the block never becomes inline
tokens and there is no emphasis to record — a field would be filled from `em_open` / `strong_open`
tokens that are never produced. Making KIR able to hold emphasis would require *enabling raw
HTML*, which is a security decision already taken in the other direction.

For the strikethrough, the field is not needed either. With the GFM `strikethrough` rule
enabled the adapter flattens the construct into node text like every other inline markup it
does not model — measured directly: `A ~~struck~~ word.` becomes `A struck word.`, spans empty,
no warnings, **no KIR change whatsoever**. One line in `profile_markdown_it` closes that half.

So 5.36 was filed as a vocabulary question and is not one. What it found is a *parser coverage*
question, and the two halves of it have different owners: one is D-017 and settled, the other is
the profile's own scope, which spec 03 §3.1 already fixes at *"CommonMark + GFM tables"* — so
the current behaviour is the specification's row implemented correctly, not an oversight.

### Whether it reaches a query

It does not reach *matching*. FTS5's `unicode61` tokenizer discards the punctuation, so a
corpus holding `~~--legacy~~` still answers a search for `struck` and for `legacy`; measured on a
two-document corpus, the struck and plain forms both rank for both queries. What differs is the
BM25 denominator — the markup contributes terms and length — and the passage a reader is
handed, which shows the markup. And `docs/index.md` **is judged by no case**, on either the
source set or the twin's, so the divergence moves no measured number today.

## Decision

**KIR gains no emphasis field, and the profile gains no strikethrough rule in this change.**

The vocabulary refusal is the easy half and the item's prior was right about it: emphasis is not
a *naming*. `spans` exists because a code span is how a documentation corpus says *this is a
command* (ADR-0094), and the symbol stage reads it. Bold and italic say nothing a query can use,
and the measurement above confirms the indexed text is identical with and without them on both
lanes. A field nothing reads is a contract to keep for nothing.

**The refusal is recorded against the evidence rather than against the hypothesis.** 5.36's
stated mechanism — strikethrough — does not occur in any corpus, and its stated cause — the
missing vocabulary — would not fix the divergence that does occur. Recording the refusal without
saying so would leave the next reader believing a reason that does not hold.

**The real question is filed rather than folded in.** Whether the authored profile should drop
HTML markup from the prose it indexes is roadmap **5.40**: it moves chunk text in
`docs/index.md`, which re-carries the twin's judgements and re-blesses two baselines, and it is a
retrieval change that deserves its own measurement. It is not urgent, because the one affected
document is unjudged — and that is a fact with an expiry date, which is why the guard below
asserts it.

**And the extent is asserted, not remembered.** Both halves of this argument rest on *how much*
diverges, and a re-vendored corpus can change that silently — the failure mode ADR-0100 named
one item ago, where a promise was written into a docstring and never kept.
`tests/test_eval_ingested_corpus.py` now pins the divergent set to exactly the one known
document and pins that document's absence from the judged sets;
`tests/test_markdown_adapter.py` pins the profile's side, so enabling strikethrough without
re-reading this decision fails a test rather than quietly closing one half of a disagreement.

**One documentation defect is fixed on the way.** `profile_markdown_it`'s docstring has said
since 2.4 that raw HTML *"reaches KIR as an `opaque` node instead"*. It does not, and cannot:
with `html: False` markdown-it emits no `html_block` token at all, the adapter's branch for one
is marked unreachable, and even that dead branch builds a **paragraph**. The adapter's own module
docstring has always said the true thing — *"it survives as literal text"* — so the repository
has been carrying both sentences, and the wrong one is in the file that defines the profile. It
is the sentence that sent this investigation looking for opaque nodes that were never there.

## Alternatives Considered

- **Add an emphasis field to `KirNode` and read docling's `Formatting`.** The change the item
  was filed to consider. Rejected on the measurement: it fixes nothing. The divergence that
  exists is in documents whose markup the profile never parses, so the field would be empty
  exactly where the disagreement is, and the lane that *can* fill it (docling) is the lane that
  already agrees.
- **Enable the GFM `strikethrough` rule now** — one line, verified to close that half with no
  KIR change. Rejected here, and this was the close one: spec 03 §3.1 fixes Profile v1 at
  "CommonMark + GFM tables", so widening it is a specification change, and the benefit on every
  corpus this project has is exactly zero occurrences. Doing it anyway would be changing a
  frozen contract to fix nothing measurable. The remedy is named here so that whoever meets the
  first strikethrough does not have to rediscover it.
- **Strip HTML markup from indexed prose in this change.** Rejected as scope: it moves chunk
  text, re-carries the judged cases and re-blesses both twin baselines, which is a retrieval PR
  with gates of its own, not a paragraph inside a refusal. Filed as roadmap 5.40 with the
  measurement attached.
- **Make raw HTML blocks `opaque` nodes**, as the profile docstring claimed they already were.
  Rejected, and worth stating because the docstring makes it sound like the obvious repair: it
  makes the disagreement *worse*. The caption's words are currently indexed on both sides; an
  opaque node would remove them from the authored side while the twin keeps them, turning a
  difference in markup into a difference in content.
- **Record the refusal and close, as the item's own escape hatch allowed.** Rejected because its
  precondition failed: the hatch was "it may be zero occurrences", and it is one document. A
  refusal recorded on a premise that had already stopped holding is the defect this project keeps
  finding in its own past work.
- **Guard nothing and rely on the ADR being read.** Rejected on the evidence of the previous
  item: ADR-0100 exists because `_inline_spans` promised a report for four milestones and nobody
  wrote one. A decision whose premise is a count needs the count asserted.

## Consequences

- **Nothing in the compiler changes, and no artifact moves.** No KIR field, no parser rule, no
  chunk text: the committed corpora, both twin baselines, gate G2's verdict and gate G3's
  enforcement are untouched, and gate G6's golden is byte-identical. This PR is a decision, two
  guards and a docstring.
- **The divergent set is now written down and checked**, so "which constructs do the two lanes
  read differently" has an answer in the repository instead of in a session's memory — with the
  eleven HTML tags named, which is the half nobody had looked at.
- **`docs/index.md`'s divergence is owned.** It is named in the test that pins it, in roadmap
  5.40, and here; it is no longer a thing that is true and unrecorded.
- **The guard will fail on a re-vendor that brings more**, and its message says to re-open 5.36
  rather than edit the expected set — which is the only way an extent-based argument can stay
  honest.
- **A wrong sentence leaves the profile.** The `opaque` claim is replaced by what the code does,
  and the adapter's neighbouring line about inline code flattening "into node text" is brought
  up to date with `spans`, which has recorded it since 5.23.
- **Known limit, stated:** the twin's `<sub>`/`<sup>` rendering inserts spaces (`H 2 O`), so
  those two constructs would diverge in *tokenisation* and not merely in markup. There are none
  in any corpus; if 5.40 is taken, it is the case to write a test for first.

## References

- Spec: `.draft-specs/03-data-model.md` §3.1 (Profile v1 — "CommonMark + GFM tables"), §4 (the
  closed node-kind vocabulary this declined to extend).
- Decision log: D-017 (all source content untrusted; HTML never interpreted), D-022 (the
  Obsidian-flavoured profile).
- The site: `eval/corpora/uv-docs/docs/index.md`, and its twin
  `eval/corpora/uv-docs-ingested/knowledge/evidence/index-html-b0ba5cdf.md`.
- Tests: `tests/test_markdown_adapter.py` (the profile's side),
  `tests/test_eval_ingested_corpus.py` (the extent, and the judged-set absence).
