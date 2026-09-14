# 2026-09-14 — the markup and the placeholder (roadmap 5.40)

- **Session scope:** roadmap 5.40 — drop raw HTML markup from the prose the authored profile
  indexes, without interpreting it, and close the one lane disagreement ADR-0107 measured.
- **PR:** #139 (`fix/strip-raw-html-markup`). Follows #138, merged as `45ec834`.
- **Milestone 5:** 5.40 done; 5.42 filed (re-bless `uv/release`, and decide what our own
  drifted baseline is for).
- **ADR:** [ADR-0110](../../../adr/0110-drop-the-markup-and-keep-the-words-on-evidence-a-placeholder-cannot-forge.md).

## The question the item asked was not the hard one

5.40 offered two details to settle, and the first was *"whether an HTML block should keep its
words or become an `opaque` node"*. ADR-0107 had already half-answered it — opaque turns a
markup difference into a content one — and the measurement confirmed it in a line. Keep the
words.

The hard part showed up in the first measurement and was not in the item at all. **`<word>` is
also how documentation writes a placeholder**, and the vocabulary is enormous: across the three
corpora, seventy-two of our 173 documents, twenty-three of uv's 81 and nineteen of the twin's
carry an angle-bracket run, and nearly all of them are `<package_name>`, `<version>`,
`<hostname>`, `<token>`, `<path>`, `<reason>`, `<short-kebab-description>` and ninety more.

Worse, the names collide. `<code>`, `<pre>`, `<script>`, `<source>`, `<path>`, `<link>`, `<i>`,
`<a>`, `<b>`, `<p>` are each a real HTML element *and* a placeholder somewhere in these
corpora. A tag-name whitelist — the obvious rule, the one I would have written from the item
alone — deletes `uv run <script>` from uv's scripting guide and `<code>` from `AGENTS.md`.
And "anything shaped like a tag" eats uv's `<2, and foo ~=1.2.3 is equal to foo >`, which is a
version range somebody wrote on purpose.

So the rule is built on evidence a lone placeholder cannot forge: a closing tag, a `name=value`
attribute, a matching close in the same block, or a comment's delimiters. `<link once released>`
— a real line from this repository's bug template — has bare words and no `=`, and stays. The
asymmetry is the point: leaving markup in costs a few noise terms; deleting a placeholder costs
the name of the thing the sentence is about.

## Three corrections the corpus made to the implementation

None of these came from reasoning. Each came from running the rule over 335 documents and
reading what moved.

**Pairing had to be per block, not per document.** ADR-0107's own table names `<i>` and `<u>`
in one cell and demonstrates `<u>lined</u>` in another. With document scope the demonstration
licensed deleting the inventory.

**Code spans had to be excluded, and the first version was not excluding them.** This
repository's roadmap writes `` `<p align="center">` `` five times and ADR-0107's table names
eleven tags in a span. The first run rewrote all of them, and the blast radius looked twice as
large as it was.

**A comment has to swallow the code it quotes** — the one place a code span *is* deleted. Three
of uv's TODO comments put a command in backticks, which splits the comment into parts, and a
rule that stopped at the span left two thirds of each behind. That is why the module scans the
block as one string with the literal positions marked rather than part by part.

## The number that counts, and the number that would have been wrong

Scored against the *committed* baseline, this change looks bad: ours/release 0.5232 → 0.5177,
the incumbent collapsing 0.2842 → 0.2466, and `r-0015` falling 1.0000 → 0.6309 with the M5
roadmap chunk overtaking it.

**None of that is this change.** Held against a corpus fixed with only the compiler varied —
which needed the maintainer's uncommitted analysis documents set aside first, and the three
changed source files swapped back to `HEAD` — the honest reading is:

| set | mycelium | grep |
|---|---|---|
| ours/release | 0.5206 → **0.5212** | 0.2466 → 0.2466 |
| ours/dev | 0.4972 → 0.4972 | 0.2742 → 0.2742 |
| uv/release | 0.6138 → 0.6138 | 0.5321 → 0.5321 |
| uv-ingested/release | 0.6144 → 0.6144 | 0.5754 → 0.5754 |

One case moves, `r-0006` 0.5743 → 0.5857, and the incumbent does not move at all. Everything
else in that first reading is corpus drift since the last bless — the standing state ADR-0053
named for a self-hosting corpus, four releases of accumulated growth presenting as a fall.
Attributing it to this change would have been the easiest wrong sentence in the PR, and it is
filed as 5.42 rather than left in the drawer.

## What was found because the item was done

`src/mycelium/markdown/` was not in `TUNING_PATHS`, so `verify.py` derived **`code`** for a
change that moves text in eleven documents across two corpora. The retrieval gates, the three
ablations and gate G2 would not have run — locally or in CI, since both callers ask the same
file. `chunking.py` has been in that list since it was written because it decides where a
chunk ends; `markdown/` decides what is *in* one, which is the same question a stage earlier.
Fixed here, and the mode became `retrieval` immediately.

## What was not done, and why

**No baseline is blessed.** ADR-0056's rule is that a bless never rides with a retrieval
change, because that conjunction is the one that can fit the retriever to the set. G3 therefore
disarms on `uv/release` and 5.42 re-arms it — safely, because the measurement says nothing
moved there, so the follow-up is digest bookkeeping and reviewable as such.
`uv-ingested/release` needed nothing at all: its corpus is byte-identical and G3 enforced and
passed throughout, which is the cleanest evidence that the twin was already right and the
authored lane was the one out of step.

**`<sub>` and `<sup>` are left diverging**, and the divergence changed shape rather than
closing: they now agree in markup and disagree in tokenisation, because stripping gives `H2O`
while the twin's renderer inserts spaces and gives `H 2 O`. Inserting a space to match would
assert a word boundary HTML does not have, and would break `un<b>bold</b>ing`. Zero
occurrences anywhere, pinned by a test.

## Lesson

A rule that removes noise is a rule that deletes text, and the corpus is the only place to find
out what it deletes. Every wrong version of this rule looked right in a docstring — the
whitelist, the document-wide pairing, the tag-shaped regex — and each one was killed by a
single real line: `uv run <script>`, ADR-0107's own table, a version range in uv's dependency
page. Reading the diff over 335 documents took less time than any of the arguments would have.
