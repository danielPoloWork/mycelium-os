# ADR-0050: Report what each query term reached, surface and stem apart

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.21; RFC-0001; spec 04 §§1-3, spec 05 §§1, 3.4; D-010, D-011, D-017;
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md)

## Context

Retrieval ranks. It never reports what it failed to find, and it cannot: a query term that
matches nothing contributes nothing to a BM25 score, which is arithmetically identical to a
term that matched and lost. The two are indistinguishable from the outside, and the
difference is the whole diagnosis.

Roadmap 4.17 paid for that. A judged case, `r-0011`, had been scoring 0.395 on this
repository's release set for two milestones. Its query is *"who signs off that a
contribution may be contributed"*, and of its five content words **two matched nothing at
all** — the corpus says *signed off* and *contribution*, and FTS5's `unicode61` tokenizer
did no stemming, so `signs` and `contributed` reached zero documents. The only word
reaching the answer was `off`. Finding that out took writing a leave-one-out script and an
afternoon; nothing in the product said it (ADR-0044).

`mycelium_explain` is the surface where it should have said it. Spec 04 §2 makes it the
debugging and trust surface, and spec 05 §3.4 has it return the retrieval plan, per-stage
timings and per-candidate signal scores — everything about the documents that *did* come
back, and nothing about the query that went in.

Roadmap 4.19 then made the question harder rather than easier. The index now carries a stem
column beside each surface column (ADR-0048), so `signs` today reaches the document through
`sign`. A single "did this term match" number would now answer *yes* for exactly the term
whose failure 4.17 spent an afternoon finding — and would make 4.19's own before/after
invisible.

## Decision

Every query word gets counted, and the count is reported as **three distinguishable
outcomes**: matched as the author wrote it, reached only by its stem, or reaches nothing in
this corpus in any inflection.

`SqliteStore.term_hits(query, filters=...)` returns one `TermHits` per distinct query
word — in query order, deduplicated, under the same filters the search ran — carrying four
integers (documents and chunks, surface and stem) and the three verdicts derived from them.
`search(..., explain=True)` attaches them to `SearchOutcome.terms`, adds a `terms` entry to
`timings_ms`, and appends a note when any word is dead. `mycelium search --explain` prints
them worst-first with dead terms as warnings; `mycelium_explain` returns them as `terms`.

Four choices inside that, each of which could have gone the other way:

**Surface and stem stay apart.** Collapsing them would report the 4.17 case as healthy. Kept
separate, the same row says both things at once: *`signs`: 0 documents; stem "sign": 8* is
the finding and the rescue in one line, and it is what makes an ADR-0048 before/after
legible to whoever runs the command rather than to whoever wrote the ADR.

**Documents and chunks are both counted.** They answer different questions — *how much of
the corpus is about this* and *how many passages can rank for it* — and a term matching one
document across nine chunks is a different situation from nine documents with one each.

**The report is off by default.** It costs two index queries per term. The evaluation
harness runs thousands of queries and measures p95 against a 150 ms budget (spec 04 §1,
gate G5); a diagnostic that taxes the number it exists to explain is a bad diagnostic. It
is computed for `--explain` and for `--json`, and for nothing else.

**`--json` gets it unconditionally.** `--json` is a format, not a request for extra work —
but the JSON document already carries a per-result `explain` block whether or not
`--explain` was passed, so a machine-readable document that is self-explanatory by default
is the convention this surface already has. Making the field appear only under a second flag
would break that consistency for a millisecond.

## Alternatives Considered

- **Report only "this term matched nothing".** The one bit 4.17 actually needed, and the
  cheapest thing to build. Rejected because the counts are what turn the bit into a
  judgment: *`off`: 29 documents, `signs`: 0* says the query is standing on a stopword,
  which the boolean cannot. And with stems in the index the bit alone is now wrong more
  often than right.
- **Fold the term report into `search_chunks`, so every query carries it.** One code path,
  no flag, nothing to remember. Rejected on latency: it would multiply the index work of
  every search by the number of query words, including inside the harness whose p95 is a
  CI gate.
- **Report FTS5's own term statistics instead of counting.** SQLite exposes per-term
  document frequencies to a custom ranking function. Rejected: reading them means writing an
  extension function and running the query anyway to apply the filters, and the numbers
  would then describe the whole index rather than the filtered corpus the operator searched.
- **Count against the unfiltered corpus.** Simpler, and one number per term for all queries.
  Rejected because it answers a question nobody asked: an operator whose `--collection`
  filter left them with nothing needs counts that agree with the search they ran.
- **A separate `mycelium explain` command.** Spec 05 §1's CLI table has no such command and
  `--explain` already exists on `search`; adding a command to carry one table would be a new
  public surface for no new capability.
- **Suppress stopwords from the report.** `a`, `the` and `that` dominate the table and are
  never the answer. Rejected: which words are noise is corpus-dependent, a stopword list is
  a tuning parameter nobody measured, and sorting worst-first already puts the informative
  rows at the top where they are read.

## Consequences

- **The 4.17 diagnosis is now one command.** On a two-document corpus that says *signed
  off* and *contribution*, `mycelium search "who signs off a kubernetes contribution"
  --explain` reports all three outcomes at once: two words matching nothing in any
  inflection, `signs: 0 doc(s); stem "sign" 1 <- only via its stem`, and the stopwords the
  query was standing on instead.
- **The worked example cannot come from this repository, and that is the finding.** The
  first draft of this ADR demonstrated the stem-only row with a word from an `unanswerable`
  judged query, and `test_no_corpus_document_answers_an_unanswerable_case` failed — writing
  the word into a document makes that case answerable and gate G4 red on the prose rather
  than on the retriever. ADR-0048's first draft did the identical thing, which is what put
  that test there. It is a standing property of a corpus that documents its own evaluation,
  and it applies twice over here: any example word printed in these docs *becomes* present,
  so an example claiming a zero count on this corpus is stale the moment it is written.
  Hence a fixture corpus, which is also what the tests use.
- **`mycelium_explain` gains a `terms` field.** MCP tool contracts are one of the five
  contracts that freeze at 1.0 (architecture §10); this is a pre-1.0 addition, additive, and
  recorded here because that freeze is what makes additions worth naming.
- **`SearchOutcome` gains `terms` and `dead_terms`**, empty unless asked for. `mycelium.eval`
  and the MCP search tool are unaffected: neither passes `explain=True`.
- **Cost, measured:** the `terms` stage is 1 ms on this repository's 105-document corpus for
  a nine-word query, against a 2 ms lexical leg. It is linear in query length, which is why
  it stays behind the flag rather than becoming free-because-small.
- **The report describes the lexical index only.** There is no such thing as a term hit in
  the vector leg, and inventing one would be a story rather than an audit. A hybrid query's
  report is about the half of it that can be counted, and says so by being labelled per
  term rather than per leg.
- **Stopword rows are noise, deliberately kept.** A reader sees `a: 110 doc(s)` at the
  bottom of the table. That is the honest shape of the query, and hiding it would require
  deciding what counts as a word worth reporting.

## References

- ROADMAP 4.21 (this item), 4.17 (where the cost was paid), 4.19 (the stemming this must
  stay legible across).
- Spec 04 §1 (the p95 budget this stays out of), §2 (explain as the debugging and trust
  surface), §3 (field weights and fusion); spec 05 §1 (CLI conventions), §3.4 (the
  `mycelium_explain` contract).
- [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) — the investigation that
  needed this and did not have it.
- [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) — why surface and stem are two
  signals rather than one, here as there.
