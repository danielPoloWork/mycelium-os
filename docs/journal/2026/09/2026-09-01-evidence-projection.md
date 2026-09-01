# 2026-09-01 — the document you can read (roadmap 4.3)

- **Session scope:** roadmap 4.3 — evidence-lane projection with provenance frontmatter,
  fidelity reports, per-document loss budgets (spec 02 §5, spec 03 §3, D-020/D-021).
- **PR:** #53 (`feat/evidence-projection-and-fidelity`). Follows #52 (4.2), merged as
  `101d7f5`.
- **Milestone 4:** 4.1–4.3 done; 4.4–4.9 open.

## The spec has a gap in its own contract, and this item is where it bites

Spec 03 §3 wants five things filled on an ingested document: the source digest, the
connector, the connector version, the acquisition time, and the fidelity report. The same
section defines the frontmatter contract as *the only machine-read metadata a document may
carry* — and it stops at `source`. A projected file therefore has no way to tell the compiler
any of it, which is why an `origin: ingested` document has been compiling with an
almost-empty `Provenance` since 2.7.

The obvious fix is four more frontmatter keys. I rejected it: four fields that a tool writes
and nothing validates will drift the moment someone edits one, and the whole point of §3's
closed field set is that it stays closed. Instead **one** key, `source_digest`, and the
compiler reads the rest out of the tier-1 custody record 4.2 built. Four facts from one link,
and they cannot disagree with the evidence they describe because they *are* the evidence's own
record. A projected document compiled on a machine without `.mycelium/` keeps the digest and
loses the rest — which is honest: there is no fidelity report to point at where there is no
evidence.

## The budget was the decision worth taking slowly

The M4 gate says *"every element represented / opaque / dropped-by-policy /
failed-and-reported"*; spec 02 §5 names a budget, `[ingest] max_failed_elements`. Neither says
what an element is or which bucket the budget bounds, and the obvious reading — count every
imperfection — produces a budget that is useless. A normal PDF drops running headers by
policy. Every DOCX with a raw block degrades one element. At 5 % the default would fire on
healthy documents, and the first thing every operator would learn is to raise it.

So the buckets are `represented`, `degraded` (structure simplified, content kept) and `lost`,
and **only `lost` is charged**. Reference nodes are not elements — their text is already
inside the block that contains them, the exclusion the chunker makes for the same reason, and
counting them would inflate the denominator and shrink every ratio. A parser's declared
policies are not per-element counts either; they are properties of the parser, recorded once
in the KIR's warnings and carried into the report verbatim. I considered emitting a node per
dropped thematic break so a counter could tick, and refused: that puts noise in a document a
person reads to satisfy a metric.

Which left a real problem: with 4.1's adapters, would `lost` ever be non-zero? Pandoc's block
vocabulary is fully mapped, so a text-less opaque node needs a *future* pandoc. The answer was
already in the PDF parser — a page with no text layer, which until now produced only a
warning. Making it an opaque `lost` node gives the budget something true to count, and gives
the operator the behaviour that matters: **a PDF of scans is refused rather than projected as
an empty document that claims to be evidence.** Its bytes and its report are in custody
first, so you can see why, and the budget can be raised to 1.0 if you want it anyway.

The report is a **pure function of the KIR**, which is what makes it worth storing rather
than logging: anyone holding the KIR blob can recompute it and check it against the digest the
document record carries. Nothing in it is a judgement a parser made and forgot.

## The projector found two of its own bugs

The load-bearing test is the chunker's no-content-loss invariant, transplanted: every KIR
node's text must survive into the projected Markdown, for all five fixture routes. It failed
twice, and both were real:

1. **A blockquote's paragraph rendered twice** — once inside the quote, once as prose —
   because the block loop rendered every node rather than only *section-level* ones. The fix
   is the test the chunker already applies: a node is rendered in its own right when its
   parent is nothing or a heading, and by its container otherwise.
2. **A definition list's definitions were rendered by nobody.** Pandoc maps them to a list
   whose item carries the term and whose *definition* is a paragraph parented to the item — so
   it was neither section-level nor a nested list. Items now render their child blocks as
   indented continuations.

Loss shows up in the projection as `[!missing]`, a Profile v1 callout: atomic in the chunker,
legible in Obsidian, and impossible to mistake for the document's own prose. An HTML comment
would have been tidier and wrong — the profile disables raw HTML, so it would have survived as
literal text and been indexed as content.

## An import circle, and what it was telling me

Making the build read a custody record closed a loop: custody needed the CAS layout and the
durable-write primitives, both inside `mycelium.build`, whose package init imports the
compiler, which imports the configuration, which asks the plugin registry which parsers
exist, which reaches custody. Two fixes, both of which are better designs rather than
workarounds:

- **`mycelium.layout`**, a leaf module that imports nothing from `mycelium`, holding
  `CAS_DIRNAME`, `CUSTODY_DIRNAME` and the atomic writes. Those were never build concepts;
  they are what a content-addressed store on a filesystem is made of.
- **`MyceliumConfig.ingest` is a `default_factory`.** A section instantiated in a class body
  runs its validators while its own module is still executing, which was the other half.

## Verified end to end

```
ok   custody: 3 tier-1 blob(s) per source — original, KIR, fidelity report
     source.docx        -> knowledge/evidence/source-docx-9a18e59e.md   21 elements, 0 lost
     no-text-layer.pdf  REFUSED: 1 of 1 elements did not survive parsing (100%)
```

and after `mycelium build`:

```
knowledge/evidence/text-layer-pdf-d2caebec.md  trust=ingested  status=evidence
   origin=ingested connector=file ingested_at=2026-09-01T08:22:40Z
   source_digest=d2caebec7ea5 fidelity_report=b5f34aa9b71f
```

That last block is spec 03 §3's document record for an ingested document, complete for the
first time.

## What this deliberately does not do

No LLM synthesis lane (4.4), no grounding or promotion (4.5), no secret scan and no decision
about what happens to a failed document (4.6). `mycelium ingest` reports per source and exits
1 if any failed; what to *do* with the failure is 4.6's question.
