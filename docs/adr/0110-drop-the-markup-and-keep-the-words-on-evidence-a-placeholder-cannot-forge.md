# ADR-0110: Drop the markup and keep the words, on evidence a placeholder cannot forge

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§3.1, 4
- **Related:** [ADR-0107](0107-refuse-to-model-emphasis-and-name-the-lane-the-disagreement-is-in.md)
  (the item this closes, and the guards it left),
  [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md) (the adapter and its
  flattening), [ADR-0094](0094-name-a-command-by-the-syntax-a-corpus-names-it-with.md) (why
  inline code is recorded and must not be touched),
  [ADR-0039](0039-measure-what-projection-costs.md) (the twin whose disagreement is the
  subject), [ADR-0053](0053-say-which-sets-a-gate-can-live-on.md) /
  [ADR-0056](0056-make-the-format-assignment-append-only.md) (why no baseline is blessed
  here), [ADR-0059](0059-run-the-gates-the-change-implicates.md) (the ladder this change
  found a hole in); D-010, D-017, D-022; spec 03 §§3.1, 4; spec 04 §3; roadmap 5.36, 5.40, 5.42

## Context

Raw HTML is never parsed by the authored profile — `html: False`, because all source content
is untrusted (D-017) — so a document that wraps a caption in `<p align="center">` reaches the
adapter as one paragraph whose text *is* the markup. Every tag name, attribute name and
attribute value becomes a term of that chunk, and its BM25 length counts them.

Roadmap 5.40 was filed at 5.36 with the one site ADR-0107 measured:
`eval/corpora/uv-docs/docs/index.md`, whose hero caption the profile indexes as
`<p align="center">`, `<i>`, `<a href="…">` and a CDN URL while the ingested twin, whose HTML
lane hands it to docling, indexes `Installing Trio 's dependencies with a warm cache.` The two
corpora genuinely describe that document differently and neither lane reports damage.

The item named the hard part without knowing how hard it was: *"whether an HTML block should
keep its words or become an `opaque` node"*. Measuring first answered a different question.

### `<word>` is how documentation writes a placeholder

Every `<…>` that survives into KIR node text, across the three corpora (2026-09-14):

| corpus | documents | documents with an angle-bracket run |
|---|---:|---:|
| ours | 173 | 72 |
| uv-docs | 81 | 23 |
| uv-docs-ingested | 81 | 19 |

Almost all of them are placeholders, and the vocabulary is large: `<package_name>`,
`<version>`, `<hostname>`, `<token>`, `<user>`, `<path>`, `<extra>`, `<root>`, `<index url>`,
`<reason>`, `<slug>`, `<milestone>`, `<short-kebab-description>` — ninety-odd distinct names.
**Their names collide with real elements.** `<code>`, `<pre>`, `<script>`, `<source>`,
`<path>`, `<link>`, `<i>`, `<a>`, `<b>`, `<p>`, `<var>`, `<data>`, `<map>` are all both a
documentation placeholder somewhere in these corpora and an HTML element. So a tag-name
whitelist cannot separate them: it would delete `uv run <script>` from uv's scripting guide
and `<code>` from this repository's own contract.

Nor can "does it look like a tag". uv's dependency page contains
`<2, and foo ~=1.2.3 is equal to foo >`, which is a version range a reader wrote; the ADR
template contains `<Short, descriptive title in imperative or noun form>`; and prose says
`0 < n and n > 1`.

### What the two lanes actually carry

ADR-0107 measured twelve constructs the lanes read differently. Ten are raw HTML tags. The
whole of their extent in the corpora is: `docs/index.md`'s three hero blocks, six
`<a id="…"></a>` anchors in this repository's i18n index, and one `<img>` in its README.

There is a second, larger population the item did not name and the same rule reaches: **HTML
comments**. uv's documentation carries thirteen — `<!-- prettier-ignore -->`, five TODO notes,
and four commented-out `docker run` reproductions — and this repository's specification
carries three. Their content is invisible on the rendered page and absent from the twin, and
today every word of it is a term. Indexing a comment lets a search return a passage whose
text the reader cannot find on the page, which is the defect this item is about in its purest
form.

## Decision

**The markup is deleted from the prose KIR stores; the words stay.** Nothing is parsed:
`mycelium.markdown.markup` resolves no entity, follows no `href`, honours no `src`, and turns
no tag into a node. A run of characters is recognised as markup and removed, and what is left
is what a reader of the rendered page sees — which is what the twin indexes and what a query
should match. The profile option stays `html: False`; this is a step further from
interpreting HTML, not a step toward it.

**A run is markup only on syntactic evidence a lone placeholder cannot produce:**

| form | why a placeholder cannot forge it |
|---|---|
| `</name>` | prose does not write a closing tag |
| `<name attr="value">` | an attribute needs `=`; `<link once released>` — this repository's bug template — has bare words and stays |
| `<name>` … `</name>` in the same block | a placeholder has no matching close |
| `<!-- … -->` | a comment's delimiters, and its content with them |

Everything else is kept, and **the asymmetry is deliberate**: leaving markup in costs a few
noise terms, and deleting a placeholder costs the name of the thing the sentence is about.

**The scope of pairing is the block, not the document.** ADR-0107's own table names `<i>` and
`<u>` in one cell and demonstrates `<u>lined</u>` in another; document scope let the second
delete the first. Measured on the corpus, not reasoned about — the first implementation had
document scope and ate that cell.

**Inline code is never reached by the tag rules, and a comment is the one exception.** A
documentation corpus explains HTML by quoting it: this repository's roadmap writes
`` `<p align="center">` `` five times, ADR-0107's table names eleven tags in a code span, and
`spans` already records what was written as code (ADR-0094). So the adapter hands the module
the block's parts with the code spans marked and a tag is deleted only where no character of
it is literal. A *comment* deletes what it quotes, because three of uv's TODO comments put a
command in backticks and a rule that stopped at the span would leave two thirds of each
behind.

**A block that was only markup leaves no node.** Every CommonMark paragraph has content, so a
blank one was a wrapper and nothing else; keeping an empty node would put blank lines into the
chunk its content used to justify. A paragraph holding a reference — an image with no alt
text — is not empty and stays, because it is an edge source (spec 03 §6). The layout
whitespace goes with the wrapper it positioned, so a caption on its own line inside
`<p align="center">` does not open its block with a blank line.

**No baseline is blessed in this change, and that is the rule rather than an omission.**
ADR-0053 as narrowed by ADR-0056: *a bless may never ride with a retrieval change, because
that conjunction is the one that could fit the retriever to the set.* This is a retrieval
change. So gate G3 disarms itself on `uv/release` — "the corpus has changed since the baseline
was taken" — and the re-bless is **roadmap 5.42**, its own PR with the diff in its body. What
makes that safe to defer is measured rather than hoped: on `uv/release` **no case and no slice
moves at all**, both retrievers, so the follow-up is digest bookkeeping and reviewable as
such. `uv-ingested/release` is byte-identical and G3 **enforces and passes** there unchanged.

**`src/mycelium/markdown/` joins `TUNING_PATHS`.** Deriving the verification mode for this
change produced `code` — so the retrieval gates, the three ablations and gate G2 would not
have run on a change that moves text in eleven documents across two corpora. `chunking.py`
has been in that list from the start because it decides where a chunk ends; `markdown/`
decides what is in one, which is the same question one stage earlier. The hole was found by
this item and is closed with it.

## Alternatives Considered

- **Make a raw HTML block an `opaque` node**, as `profile_markdown_it`'s docstring wrongly
  claimed it already was until ADR-0107 fixed the sentence. Rejected there and again here: the
  caption's words are indexed on *both* sides today, so removing them from the authored side
  turns a difference in markup into a difference in content — the disagreement gets worse.
- **A whitelist of HTML element names.** The obvious rule, and the measurement kills it:
  thirteen element names are also placeholders in these corpora, including `<script>` in uv's
  scripting guide and `<code>` in `AGENTS.md`. It would delete the subject of those sentences.
- **Delete anything shaped like a tag.** Eats `<package_name>`, `<2, and foo ~=1.2.3 …>` and
  the ADR template's own prompts. The false-positive cost is a name a reader needs; the
  false-negative cost is a handful of noise terms. Not a close call.
- **Enable markdown-it's `html: True` and let the parser identify the tags.** Tempting,
  because CommonMark's HTML grammar is a conformant answer to "is this a tag". Rejected on
  both counts: a whole `<p …>` block arrives as one raw token whose inner tags still need
  removing by hand, so it buys no accuracy — and its inline grammar accepts *any*
  `[A-Za-z][A-Za-z0-9-]*`, so `<package_name>` outside a code span becomes markup. It would
  flip a security-adjacent option to make the rule worse.
- **Leave comments indexed** and treat only tags. Rejected: the comment is the case where
  100 % of the run is invisible to the reader, and it is sixteen blocks against the tags'
  nine. Including them is the same argument, applied where it is strongest.
- **Insert a space where a tag was**, so `H<sub>2</sub>O` matches the twin's `H 2 O`.
  Rejected: it would break `un<b>bold</b>ing` into three tokens, and it asserts a word
  boundary HTML does not have. The `<sub>`/`<sup>` divergence is stated as a limit instead.
- **Bless the moved baselines here** so gate G3 is not left disarmed. Rejected on ADR-0056's
  rule, which is exactly about this conjunction. Filed as 5.42 instead, with the measurement
  that makes the deferral safe.
- **Strip comments from the source before parsing**, which would catch one that spans a blank
  line. Rejected: it would reach inside fenced code blocks, where a corpus that documents HTML
  keeps real examples, and the rule would stop being a property of *indexed text*.

## Consequences

- **Measured, on a corpus held fixed while only the compiler varied.** `ours/release`:
  **0.5206 → 0.5212** (+0.0007), one case — `r-0006` 0.5743 → 0.5857 — and the incumbent
  **does not move at all** (0.2466 → 0.2466), so the reported lead widens +0.2740 → +0.2747.
  `ours/dev`: nothing moves, either retriever. `uv/release` and `uv-ingested/release`: nothing
  moves, either retriever. A change that removes 355 whitespace-separated runs from thirteen
  documents and moves one judged case is a change that removed noise.
- **The control matters more than the number.** Read against the *committed* baseline instead,
  `ours/release` appears to fall 0.5232 → 0.5177 with grep collapsing 0.2842 → 0.2466 and
  `r-0015` going 1.0000 → 0.6309. **None of that is this change.** It is corpus drift since the
  last bless — the standing state on a self-hosting corpus that ADR-0053 named — and the
  isolated measurement above shows grep identical to four decimals. Attributing it here would
  have been the easiest wrong sentence in this PR.
- **The lane disagreement is closed, and asserted end to end.** Both lanes now index
  `Installing Trio's dependencies with a warm cache.`, one character apart — docling spaces
  the possessive, and `unicode61` splits `Trio's` into `trio` and `s` either way, so the terms
  are the same. ADR-0107's `KNOWN_DIVERGENT` set is now **empty**, which is the claim.
- **Two constructs still diverge, both with zero occurrences, and the guard still pins that.**
  GFM strikethrough, because Profile v1 is CommonMark plus GFM tables (spec 03 §3.1) and
  ADR-0107 declined to widen a frozen contract for a construct no corpus contains; and
  `<sub>`/`<sup>`, which now agree in markup and disagree in *tokenisation* — stripping gives
  `H2O`, one token and what a browser renders, while the twin's renderer inserts spaces and
  gives three. A smaller disagreement than before, and a different one.
- **No element semantics are modelled.** A `<script>` body's words are indexed like any other
  words, because telling them apart needs the parse D-017 refuses. Nothing is executed, and
  the option that would make execution conceivable stays off.
- **Gate G6's fixture gains a section** exercising every branch — a wrapper block, a caption
  pair, a comment, a placeholder, a comparison and a quoted tag — so the rule is pinned
  byte-for-byte. The golden moves by exactly one chunk (31 → 32) and two digests; every other
  chunk, document and symbol is identical.
- **`PARSE_STAGE_VERSION` 2 → 3**, so every document holding a tag or a comment re-parses on
  the first build after the upgrade, through the unchanged chunk and assemble caches.
- **Gate G2's verdict is re-recorded**, because the `uv` corpus's fingerprint moved and the
  recorded verdict no longer described the product (ADR-0068's currency check said so by
  name). The shipped default is unaffected by this change on its own merits.
- **A known limit, stated:** a comment that spans a blank line is two paragraphs to
  CommonMark, and neither half carries both delimiters, so it stays. There are none in any
  corpus; the alternative reached into fenced code and was refused.

## References

- Spec: `.draft-specs/03-data-model.md` §3.1 (Profile v1), §4 (the node vocabulary this did
  not touch); `.draft-specs/04-retrieval-and-evaluation.md` §3 (the field-weighted index whose
  lengths these terms were inflating).
- Decision log: D-010 (fix the product, not the benchmark), D-017 (all source content
  untrusted, HTML never interpreted), D-022 (the Obsidian-flavoured profile).
- The site: `eval/corpora/uv-docs/docs/index.md` and its twin
  `eval/corpora/uv-docs-ingested/knowledge/evidence/index-html-b0ba5cdf.md`.
- Re-runnable: `mycelium build eval/corpora/uv-docs --no-pin`, then
  `mycelium eval eval/corpora/uv-docs --set eval/release.jsonl --against grep`.
- Tests: `tests/test_markdown_adapter.py` (the rule, case by case),
  `tests/test_eval_ingested_corpus.py` (the extent, and the two lanes compared end to end).
