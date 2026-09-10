# ADR-0076: Let the corpus declare its entities, and refuse to guess the rest

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §6
- **Related:** [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md) (the
  `mentions` type deferred to here, and the resolve-or-emit-nothing rule this reuses),
  [ADR-0018](0018-build-the-graph-from-authored-links.md) (the per-document / global seam),
  [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md) (the
  sibling stage, and the same measure-then-choose method),
  [ADR-0046](0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md) (the
  derived identity this needs), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (optional capability, stated degradation), [ADR-0012](0012-adopt-the-g6-determinism-gate.md)
  (the golden this changes the shape of), [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md)
  (the verdict a store-schema bump makes stale); spec 02 §4.1, spec 03 §§2, 3.1, 6, 7, 8, 9,
  spec 05 §2, spec 06 §3; D-014, D-022, D-028; roadmap 5.4, 5.12

## Context

Spec 02 §4.1 draws the `extract` stage producing *symbols, links, entities°*, with the degree
sign marking the optional one. Spec 03 §6 gives the record its fields and one instruction —
*"optional stage, off by default in v1 … same status discipline"* — and spec 03 §9 puts
`entities.jsonl` in the bundle *"if present"*. Roadmap 5.4 is that stage. ADR-0074 left it one
inheritance: `mentions`, the eighth and last of D-014's edge types, deferred here rather than
mined out of prose without a vocabulary to mine against.

The hard part is not the plumbing. It is that "entity extraction" in the RAG literature means
an LLM reading prose and inventing nodes, which this project has refused at every turn: the
build makes no network call (D-013/D-017), it is byte-identically reproducible (G6), and spec
06 §3 defers the formal ontology *and* the entity acceptance workflow to post-1.0, behind a
trigger that has not fired. So the question is what a deterministic, offline entity stage can
honestly extract — and the answer had to come from the corpora rather than from taste.

**Measured on 2026-09-10, across the three corpora the evaluation runs on** (this repository's
134 documents, the vendored uv documentation's 81, and its ingested twin's 81):

| candidate vocabulary | ours | uv | uv-ingested |
|---|---:|---:|---:|
| frontmatter `tags` | 0 | 0 | 0 |
| frontmatter `aliases` | 0 | 0 | 0 |
| inline `#tag` | 77 distinct, **1** with a letter | 6, **0** | 2, **0** |
| document titles | 134 | 81 | 81 |

The inline tags are GitHub issue references — `#1`, `#313`, `#2252` — 84 of the 85 across all
three. Titles are the only vocabulary that exists in quantity, and matching them in prose
produces 227, 197 and 163 hits whose most frequent members are `README` (42),
`Documentation` (41), `Changelog` (28), `Projects` (23) and `Tools` (21): ordinary words, not
references to a document.

## Decision

**An entity is a name the corpus declares, and never one guessed from its prose.** Two
authored declarations, both already parsed, both in the Mycelium Markdown Profile (spec 03
§3.1): a **tag** (frontmatter `tags`, or an inline `#tag`) is a label a human attached, kind
`tag`; an **`aliases`** key is a document saying the thing it is about answers to other names,
kind `topic`, whose entity takes the document's title as its name and the aliases as its
`aliases`. Every entity is `status: authored`, because a human wrote every one of these
declarations — and it is the *mentions* over them that are `extracted`, which is spec 03 §6's
status discipline landing exactly where it was aimed.

**Document titles are refused as a vocabulary, on the measurement above.** A table whose
most-cited members are `README` and `Documentation` is not a knowledge graph, and it is wrong
in the way that reads as coverage. A title becomes a name only when its own document says so
by carrying an `aliases` key — which is one keystroke for an author who means it, and silence
from every author who does not.

**`mentions` follows ADR-0074's rule: it resolves against the declared vocabulary or produces
nothing.** The edge runs from `doc:<path>` to `ent:<slug>`, is `extracted`, and carries the
chunk it was found in, so `mycelium neighbors` answers *what does this document talk about*
and *what talks about this* on one node in opposite directions. Four rules remove a class of
false edge each: a document that *declares* an entity does not also mention it (the
declaration already says so, through `doc_refs`); one edge per document and entity, at its
first occurrence; code passages are not prose, because a name in a fence is a token in a
program and the symbol table owns those (ADR-0073); and a name shorter than four characters is
not searched for, because below that the ordinary word wins — `api`, `uv` and `ci` occur in
prose constantly without naming the thing the tag names. The floor applies to the *scan*, not
to the record: a short tag keeps its entity and its `doc_refs`.

**One entity, several names.** Two surface forms that slug alike are one record carrying both,
not two records: `Event Bus` and `event-bus` are the same thing, and the form that did not
become the name is kept in `aliases` so the collision is visible in the record rather than
lost. A slug declared by any `aliases` key is a `topic` and takes its document's title as the
display name; otherwise it is a `tag` and takes the first surface form in path order.

**`entity_id` is derived from the slug, not minted.** Spec 03 §2 asks for a ULID, and a minted
one would differ on every build — two builds of one corpus would fold different manifests, and
the build has nowhere to persist a mint because it may not write to tier 2 (ADR-0009).
ADR-0046 already solved this for documents and its mechanism is reused verbatim. The cost is
the same one ADR-0046 named: a derived id does not survive a rename of what derives it, so
re-slugging an entity is a new id. Stated rather than hidden.

**Declaration is per document and cached; resolution is global and runs every build.**
ADR-0018's seam, cut a third time, and here it earns something specific: the declarations are
a few frontmatter fields, so they are extracted and stored in `doc_state` **whatever the flag
says**. The flag therefore gates *publication* alone, and turning the stage on publishes the
table on the next build without recompiling a document — which is a test.

**The stage is off by default, in a new `[entities]` section with exactly one key.** Spec 05
§2's printed file predates the stage and spec 03 §6 does not say where the switch lives; it
lives here, and it is one boolean because the stage has one decision to offer. What it
extracts is deliberately not tunable: a knob that widened the vocabulary would be a knob that
invented entities.

**The determinism fixture switches the stage on.** A golden blessed under the defaults could
never see a change to a stage the defaults leave off — the gate would be blind to a whole
stage of the compiler, which is the opposite of what ADR-0012 built it for. So the fixture
gains a `mycelium.toml`, the golden records every entity (including its derived `entity_id`)
and every `mentions` edge, and the tools that build the workspace copy the file.

**Two things this ADR deliberately does not do.** No entity participates in retrieval: that is
a ranking change with gates of its own, and the symbol leg is already queued as 5.9 with the
same argument. And no `Extractor` Protocol is added: ADR-0073 deferred it to "the second
extraction kind", ADR-0074 delivered that, and this is the third — but spec 05 §4.1's sketch
returns links, symbols *and* entities from one call, which is a shape worth designing against
all three implementations at the 1.0 freeze (roadmap 6.1) rather than around whichever landed
last.

## Alternatives Considered

- **Match document titles in prose.** The only vocabulary with real numbers, and the obvious
  "unlinked mentions" feature. Rejected on its own measurement: 587 hits across three corpora
  dominated by `README`, `Documentation`, `Projects` and `Tools`. It would have been the
  largest table in this PR and the least true.
- **An LLM extractor, reusing the `[synthesis] provider` seam.** It is the technique the field
  means by the words, and the provider consent already exists (B10). Rejected: the build is a
  pure function (D-008) with a byte-identical rebuild gate, and a non-deterministic stage
  inside it would either break G6 or need the embedder's `deterministic: false` escape — for a
  capability spec 06 §3 defers to post-1.0 behind an unfired trigger.
- **Capitalised-noun-phrase heuristics.** Dictionary-free NER, no dependency. Rejected: it
  invents `The Following` and `See Also`, and no amount of stop-listing turns a guess into a
  declaration.
- **Emit an entity per document title and let `mentions` sort it out.** Rejected for the same
  reason as the first alternative, plus a second: a document is already a node, so a 1:1
  entity beside it is a synonym for `links_to` without a link.
- **Make the mention floor configurable.** Rejected as a fitted parameter with no measurement
  behind it — the refusal ADR-0031 and ADR-0041 have made fourteen times. It is a module
  constant with its reason written next to it, like `MAX_FENCE_BYTES`.
- **Store the entities in the snapshot state and restore them literally.** Rejected exactly as
  ADR-0018 rejected it for edges: they are a pure function of the declarations already in the
  state, and re-resolving *and reproducing the published digest* proves the restore where a
  copy would only prove the copy worked. Whether the stage ran is read from the manifest's
  `artifact_digests`, not from today's configuration, so flipping the flag never makes an
  older snapshot unrestorable.
- **Keep the ASCII letter test.** The first implementation filtered numeric tags with
  `[^A-Za-z]*`, which threw away the multilingual fixture's own `設計` tag as though it were an
  issue number. Replaced with `str.isalpha`. The corpus is multilingual by decision (D-028) and
  the anchor slugger keeps non-Latin scripts intact; an ASCII filter would have made the stage
  quietly Latin-only. The fixture caught it, which is what that fixture is for.
- **Give each alias its own entity.** The first implementation did, and turned
  `aliases: [Arch, the design]` into three entities. Rejected on re-reading spec 03 §6: the
  record has an `aliases` field precisely so that it does not.

## Consequences

- **Measured yield, published rather than implied.** With the stage switched on: this
  repository declares **one** entity — `ent:nnn`, from the `#NNN` placeholder in the
  bug-ledger template — and **zero** mentions; the uv documentation and its ingested twin
  declare **nothing at all**. That is the evidence behind "off by default", and it is a fact
  about these corpora rather than about the mechanism: they are a Git repository's docs tree
  and a vendored documentation site, and neither uses tags or aliases. An Obsidian vault, which
  is the corpus D-022 shaped the profile for, uses both heavily. The determinism fixture, which
  does use them, yields 8 entities and 5 `mentions` edges.
- **Cost, measured: nothing to speak of.** The `entities` stage reports **0 ms** in the
  manifest timings on all three corpora, and a warm rebuild is 0.89 s / 0.43 s / 0.32 s. The
  scan is one compiled alternation over the corpus's passages, and it runs only when the flag
  is on.
- **Store schema v5 → v6** adds the `entities` table (spec 03 §8's layout does not draw one,
  because the stage that fills it is optional). Existing stores are recreated on the first
  build (D-016, automated since ADR-0015) — no operator action.
- **The extract stage version goes 2 → 3**, so the first build after upgrading recompiles every
  document to write its declarations. The parse and chunk caches still serve.
- **`SnapshotCounts` gains `entities`**, defaulting to 0 so a manifest written before this
  item still validates. `artifact_digests["entities"]` and the bundle's `entities.jsonl` are
  present **only when the stage ran**, which is spec 03 §9's own "if present" rule used as the
  signal for both.
- **`EntitySlug` was widened** from `^[a-z0-9]+(?:-[a-z0-9]+)*$` to what `heading_slug`
  actually produces. It could not accept `設計`. Widening cost nothing because no entity had
  ever been minted, so there was no data under the narrower rule.
- **Gate G2's verdict was re-recorded, and this is a false positive worth naming.**
  `retrieval_identity()` includes the store's `SCHEMA_VERSION` as its proxy for *what BM25 can
  see*; adding an unrelated table moves it, so the verdict went stale without a single ranking
  input changing. Re-recording proves the point: **all four `uv` and `uv-ingested` set numbers
  reproduce byte-identically**, and only `ours/*` moved, by the corpus growth this repository's
  own documentation always produces (ours/release lexical 0.5263 → 0.5305, hybrid 0.6105 →
  0.6046; the default stays `lexical`). Narrowing the fingerprint to the FTS schema is filed as
  roadmap 5.12 rather than done here, because it is a change to a tuning path made for one
  PR's convenience.
- **Threat model:** no new boundary. The scan reads document text already inside B4/B11, and
  its pattern is built from escaped literals. One STRIDE row is added under B11: a *projected*
  document cannot declare an entity, because the projector renders no tags and writes only
  provenance frontmatter — so ingested content cannot inject a name into the vocabulary.
- **Known limits, on the record.** A name inside an unbroken run of Chinese or Japanese
  characters is not matched, because the word boundary is `\w`-based and those scripts do not
  separate words. A four-character floor silences short tags in the scan. And an author who
  declares a generic alias (`the design`) gets generic mentions — which is the author's
  decision showing through, and the difference between this design and the one it refused.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (identity), §6 (the record, the status discipline),
  §8 (the layout that does not draw this table), §9 (`entities.jsonl` "if present");
  `.draft-specs/02-architecture.md` §4.1 (the optional stage);
  `.draft-specs/06-roadmap-and-governance.md` §3 (ontology and acceptance workflow, deferred).
- Decision log: D-014 (controlled vocabulary, no ontology), D-022 (the Obsidian-flavoured
  profile these declarations come from), D-028 (the corpus is multilingual).
- Re-runnable: add `[entities] enabled = true` to a corpus's `mycelium.toml`, `mycelium build`,
  then `mycelium export` and read `records/entities.jsonl`; `mycelium neighbors <doc>` shows
  the `mentions` edges.
- Tests: `tests/test_entities.py`; gate G6 in `tests/test_determinism.py` with
  `tests/fixtures/determinism/golden.json` and its new `mycelium.toml`.
