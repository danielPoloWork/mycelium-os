# ADR-0091: Widen the heading rule, and refuse to guess which section documents a name

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§2, 6
- **Related:** [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)
  (the one-word heading rule this widens), [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md)
  and [ADR-0065](0065-one-section-cannot-document-two-commands.md) (what a `symbol` judgment
  names — the rule this was asked to meet), [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (the symbol leg, the shared identifier rule, and the finding this item was filed from),
  [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (a leg adds, it never promotes), [ADR-0031](0031-refuse-three-rerankings.md) and
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md) (the shape of a measured
  refusal), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (which sets a gate can live on); spec 03 §§2, 6, spec 04 §§2-3, §7.1; D-010; roadmap 5.1,
  5.9, 5.19, 5.23

## Context

Roadmap 5.19 was filed by 5.9 with a diagnosis and three candidate fixes. ADR-0080 had
already named the problem in its own title — *the table points at naming sites* — and left the
repair to this item. The diagnosis: ADR-0062 settled that a `symbol` judgment names *the
section that documents the named thing*, while ADR-0073's extractor takes `defined_in` from the
heading that *spells* it, and on every firing the symbol leg had, those were different chunks. The candidates were (a) the section
with the most prose about the name, (b) a `doc_refs` ordering that puts documentation ahead of
listings, or (c) a second field, so `defined_in` stays a naming fact and the documenting site
becomes its own. The item said to decide from the documents.

Decided from the documents, **all three candidates fail, and the diagnosis is half right**.

**What the extractor could see was only ever the tour.** Of uv's seven one-word headings, four
sit under *Working on projects ▸ Project structure* and three under *Installing uv ▸
Installation methods* — a layout tour and an installation list. The reference sections that
explain the same files are `## The pyproject.toml`, `## pylock.toml format`,
`## requirements.txt format`, `## manylinux_compatible enforcement`, `## uv.lock output`, and
the one-word rule cannot see any of them. That is the real defect, and it is not about
ordering: on `u-0021` the judged grade-2 anchor is
`docs/concepts/projects/layout.md#the-pyproject-toml/0`, a section the table did not hold at
all. Candidate (b) cannot reorder a list that has one entry — every `sym:doc:` symbol on every
corpus had exactly one `doc_ref` — and candidate (c) cannot fill a field with a site nothing
extracted.

**And the ranking candidate loses on measurement.** With the widened rule uv's
`pyproject.toml` has four sites, so the signals a per-document extractor could rank them by
can finally be compared against a judgment:

| site | tokens | mentions | judged |
|---|---:|---:|---|
| `docs/concepts/projects/layout.md#the-pyproject-toml/0` | 106 | 2 | **grade 2** |
| `docs/guides/projects.md#project-structure/pyproject-toml/0` | 247 | 4 | — |
| `docs/guides/migration/pip-to-project.md#…/the-pyproject-toml/0` | 153 | 3 | — |
| `docs/pip/dependencies.md#using-pyproject-toml/0` | 146 | 6 | — |

Most prose picks the guide's tour entry. Most mentions picks `docs/pip/dependencies.md`. The
section a judge graded relevant is the **smallest of the four and mentions the name least**.
Candidate (a) is not merely unhelpful, it is wrong in the measured direction.

**Plain path order is no better, and it was tried.** Run over the widened table without the
tie-break this ADR adopts, three records moved: `uv/pyproject.toml` onto the judged section,
and `uv/uv.lock` and `uv-ingested/pyproject.toml` onto pages that document nothing in
particular — a Renovate integration guide and a `uv pip` dependencies page. One right, two
wrong, none aimed.

**The deepest fact is that the documenting section often does not name the thing at all.**
`uv.lock` is documented by `## The lockfile`; package indexes by
`docs/concepts/indexes.md#defining-an-index`, the grade-3 anchor of `u-1001`. No heading rule,
at any width, reaches a heading that does not contain the name. Which page of a corpus is its
reference and which is its tour is an editorial fact about the whole corpus, and a stage that
sees one document at a time cannot read it.

**Separately, and decisively for the slice this was supposed to unblock:** sixteen of the
nineteen `symbol` case-instances ask for a multi-word command — `uv tool install`,
`uv lock --check`, `uv python pin` — which is not an identifier under spec 04 §2 and never will
be a `sym:doc:` term; the other three ask for classes (`SqliteStore`, `UlidFactory`) that our
own corpus discusses in prose and never fences. The pages that document those commands head
their sections *Installing tools*, *Checking the lockfile*, *Exporting the lockfile* — **not one
contains a command name**. No change to heading extraction can make that slice fire.

## Decision

**A heading defines the name it is *about*: the name itself, or the name and one framing
word.** `## uv.lock` and `## The pyproject.toml` both define `sym:doc:uv.lock` and
`sym:doc:pyproject.toml`; `## pylock.toml format`, `## Using requirements.in` and
`## manylinux_compatible enforcement` each define one term. A heading holding two names is a
list or a sentence and defines nothing — a section documents one subject — and per-word
sentence punctuation is stripped first, so *"Learn more about the core concepts in uv."* does
not define `uv.`.

**The one-extra-word bound is the largest at which no corpus yields a non-name**, which is why
it is two and not a number someone liked. At two words the three corpora gain twelve, ten and
zero headings with nothing among them that is not a name. At three, uv's ingested twin yields
`e.g`, out of a heading that is a git URL with a parenthetical. At five it yields `x86_64` from
*"Transparent x86_64 emulation on aarch64"*, where the subject is the emulation and the
architecture is a modifier.

**`defined_in` is the most *direct* naming site, and this change cannot move it.** A site is
direct when its syntax makes the symbol its own subject — a fence definition, a definition-list
term, or a heading that *is* the name — and resolution prefers a direct site to a framing one,
path order between equals. So widening which headings are read is **strictly additive**:
measured across all three corpora, nine symbols and thirteen sites are gained on uv, seven and
eleven on its twin, and **not one `defined_in` value moves**.

**No field claims to name the documenting site, because nothing here can compute it.**
`defined_in` says, in the record's own docstring, that it is a naming fact and not an editorial
one — and the three signals that were measured are named there, so the next reader meets the
refusal where the field is defined rather than only here. Candidates (a), (b) and (c) are refused
with the measurements above rather than left for someone to re-propose. What replaces them is `doc_refs`: it now holds **every** site at which
the corpus names the thing, which is where a reader can weigh them and where the symbol leg
already ranks them by BM25 — the second reason ordering them would be inert.

**No ranking code is touched**, as 5.19 required. `identifier_like` — the rule shared with the
planner (ADR-0080) — is unchanged, so what a *name* is has not moved and the leg can still
reach every symbol the extractor writes; only which *headings* are read has. `retrieval_identity()`
is byte-identical, so gate G2's recorded verdict stays current, and
`measure_symbol_leg.py --check` reports every case on every set identical to the baseline.

## Alternatives Considered

- **Rank sites by the prose they hold (candidate a).** Rejected on the table above: it picks
  the 247-token tour entry, and the judged section is the smallest of four. Ranking by mentions
  instead picks a third section. A rule fitted to make the right one win on one case would be a
  rule with no reason.
- **Order `doc_refs` so documentation precedes listings (candidate b).** Rejected twice over:
  before this change every `sym:doc:` symbol had exactly one `doc_ref`, so there was nothing to
  order; and the symbol leg re-ranks `doc_refs` by BM25 (ADR-0080), so their stored order
  cannot reach a result either way.
- **Add a second field for the documenting site (candidate c).** Rejected because nothing can
  fill it. It would have been the right shape if the site were computable; four signals say it
  is not, and a field that is sometimes right and never checkable is worse than no field.
- **Keep plain path order on the widened table.** Rejected on measurement: it moves three
  records, two of them onto pages that document nothing. The directness tie-break costs one
  boolean on a reference and makes the change additive.
- **Widen further — three words, or five.** Rejected on the corpora: three admits `e.g`, five
  admits `x86_64` as the subject of a sentence about emulation. The bound is where the evidence
  stops, not where the yield does.
- **Drop the product names the rule now admits** (`PyTorch`, `GitHub`, `macOS`, `PyPy`,
  `CodeArtifact`). Rejected: removing them needs a stoplist, which is a parameter fitted to one
  corpus, and they are honest — `## Installing PyTorch` is a section about PyTorch. ADR-0073
  already recorded product names as a known consequence of the camel-case signal; this makes
  the consequence larger, not different.
- **Make a command a symbol** — `sym:cli:uv tool install` — so the `symbol` slice can fire at
  all. Not rejected: it is the only change that could, and it is a **new source** of symbols
  rather than a `defined_in` fix, needing its own identity rule (spec 03 §2 has no `cli`
  language), its own extraction syntax, and its own measurement. Filed as roadmap 5.23 with the
  nineteen case-instances that justify it.
- **Judge the four firings differently instead.** Rejected: `u-1001` names PyPI incidentally
  (*"a package index other than PyPI"*) and its judged answer is correct; re-judging a case so
  that a mechanism looks better is the re-fit D-010 forbids, and the guard
  `check_frozen_release_sets.py` refuses the conjunction anyway.

## Consequences

- **The table gains what it was blind to, and loses nothing.** uv: 14 → **23** symbols, 16 →
  **29** sites, 16 → **29** `defines` edges. The ingested twin: 12 → **19**, 12 → **23**, 12 →
  **23**. This repository: **unchanged at 3** — its own headings are prose titles, which is the
  same honest answer 5.1 got.
- **One measurable improvement, stated as exactly what it is.** On `u-0021` the leg offered one
  site, judged irrelevant; it now offers four, one of which —
  `docs/concepts/projects/layout.md#the-pyproject-toml/0`, at lexical rank 9 — is the case's
  grade-2 anchor. The *result* is still unchanged, because add-only cannot promote a chunk the
  ranking already has inside the top ten (ADR-0075), and because the leg ships off (ADR-0080).
  The table is right; the retrieval consequence remains zero and is not dressed up.
- **`u-1001` is unchanged and unfixable here.** Its grade-3 anchor is a section whose heading
  names no symbol. That is the general limit, recorded so the next reader does not re-derive it.
- **The shipped ranking is byte-identical.** Every case on every set, both readings of the leg,
  `--check` green; `retrieval_identity()` unmoved, so no G2 re-record (ADR-0068). No baseline
  moves for a retrieval reason; `ours/*` moves only because this ADR is a document in our own
  corpus, which G3 reports and does not enforce (ADR-0053).
- **Gate G6 covers the new shape.** The fixture gains `## The RetryPolicy` in `retries.md`, so
  `sym:doc:RetryPolicy` has two sites in two documents: the golden pins that `defined_in` stays
  the direct site in `api.md` and that `doc_refs` holds both, and the coverage test asserts it
  by name. Golden diff: `chunks` 29 → 30, one new chunk, one symbol gaining a second site, one
  new `defines` edge; every other document, chunk and symbol byte-identical.
- **`EXTRACT_STAGE_VERSION` 5 → 6**, so the first build after upgrading re-extracts every
  document through the parse and chunk caches. A `doc_state` row written before this change
  decodes with `direct=True`, which is correct: the old rule only ever recorded direct sites.
- **`heading_term` becomes `heading_subject` and returns a pair.** Internal to
  `mycelium.symbols`, which is not in `MODULE_SURFACE`, so no module contract moves.
- **Known limits, on the record.** A section whose heading omits the name is invisible, and that
  is most reference prose. Product names multiply. A three-word heading about one name
  (`Relationship to pylock.toml`) is not read, and the bound that would read it also reads
  `e.g`.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (identity), §6 (the record);
  `.draft-specs/04-retrieval-and-evaluation.md` §2 (identifier-like tokens), §3 (the symbol
  leg), §7.1 (slices).
- Re-runnable: `python tools/measure_symbol_leg.py --coverage` for the sites and the ranks;
  `python tools/measure_symbol_leg.py --check` for the null result it leaves untouched.
- The documents the decision was read from: `eval/corpora/uv-docs/docs/concepts/projects/layout.md`,
  `.../docs/guides/projects.md`, `.../docs/pip/dependencies.md`,
  `.../docs/getting-started/installation.md`, `.../docs/guides/tools.md`,
  `.../docs/concepts/projects/sync.md`.
- Tests: `tests/test_symbols.py`, `tests/test_symbol_leg.py`, and the coverage assertion in
  `tests/test_determinism.py`.
