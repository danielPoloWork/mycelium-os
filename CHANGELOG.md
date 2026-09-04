# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Changed

- **The lexical index gates the query, not the documents** (roadmap 4.23,
  [ADR-0054](docs/adr/0054-gate-the-query-not-the-documents.md)). ADR-0048's stem
  expansion required a surface hit inside one MATCH expression, which held two rules at
  once: *this query* must have a literal footing in the corpus, and *every candidate
  document* must carry one of its words as written. Only the first buys the abstention that
  keeps gate G4 green, and the second was excluding documents that share a word's
  inflection and nothing else. They are now separate — a `LIMIT 1` foothold probe, then an
  open search — with no threshold introduced anywhere. Measured: `uv/release` 0.5483 →
  0.5620 and `uv-ingested/release` 0.6469 → 0.6556 with **G3 enforcing and passing**, every
  point of it in the `fact` slice; ours/release flat at 0.4978; G4 unchanged at 0.00 % on
  all three corpora, which the same search without the gate is not.
- **`STEM_WEIGHT` is 0.05, not 0.1**, and it is the same balance rather than a new one: the
  old expression named the surface clause twice, so the nominal weight understated the
  surface side. With the duplication gone the nominal weight is the effective one. An
  evaluation run manifest's `retriever_config.stem_weight` is how a reader tells a run on
  this index from a run on the last one.
- **`mycelium.store.foothold_query` is a new public name**, and `expanded_query` changes
  meaning: it is now the open expression, and a caller wanting ADR-0048's semantics must run
  the gate itself. No store is rebuilt — the index columns are unchanged, so the schema
  stays `mycelium/store/v4`.

- **Gate G3 reports on the corpus we author, and enforces on the ones we do not** (roadmap
  4.22, [ADR-0053](docs/adr/0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)).
  G3 enforces only when the corpus and the judgements are the ones its baseline was taken
  on, and this repository's documentation *is* its corpus — so on our own release set that
  can never be true, and `eval/baselines/release.json` has carried per-slice numbers CI
  never once enforced. The contract is now stated rather than deduced: **our set is
  reported, the two vendored sets are gated**, our baseline stays committed (G3 reports
  against it, and since ADR-0052 it holds the per-case scores) and is re-blessed as its own
  deliberate act. The verdict itself now says the report branch is the *standing* state on
  a self-hosting corpus, so a threshold nobody can trip stops reading as a gate.
- **All three release baselines are re-blessed against the shipping retriever.** Ours/release
  overall `0.4499 → 0.4982`: `conceptual` and `fact` up on unchanged populations,
  `relationship` up on the two cases it already held (`0.1064 → 0.3013`), and `exact` down
  `0.9833 → 0.7593` only because the slice went from one case to four — the case the 0.9833
  was measured on reads **0.9942** today. The vendored two predated roadmap 4.19's stemming
  index, so the only *enforcing* gate was carrying nine points of headroom: `uv/release`
  `0.4920 → 0.5483` and `uv-ingested/release` `0.5911 → 0.6469`, no slice down on either.
  `uv-ingested/release` gains the `grep` entry it never had.

- **Gate G3 states which slices it can enforce, and says so in its verdict** (roadmap 4.20,
  [ADR-0052](docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md)). A slice's score is a
  mean, and a mean over one case is that case wearing a slice's name — five of seventeen
  gated rows across the three release sets could never fail at all (a relative threshold
  cannot fail a 0.0000 baseline) and eight of the rest held three cases or fewer, while the
  verdict said `6 slice(s) compared` regardless. G3 now enforces a slice only when it is not
  `unanswerable` (whose correct score *is* 0.0000, and which G4 gates), its baseline is
  above zero, and it holds at least **4** judged cases; every other row is reported **by
  name, with the reason**. On the sets G3 actually enforces this makes the gate honest and
  smaller — `uv/release` reads `1 of 6 slice(s) enforced` — which roadmap 4.26 is filed to
  widen again.

- **Five judged cases lift `exact` and `relationship` on our own release set** to four cases
  each, from one and two. The first thing that bought was a correction: `exact` was blessed
  at **0.9833 on a single case**, a term quoted back verbatim from a heading, and reads
  **0.7593** over four — the new `STRIDE` case at 0.3331 is an acronym whose literal home is
  one document among three that mention it. That figure was not a regression waiting to
  happen; it was a case being reported as a slice.

- **A failing or reported slice now names the cases behind it** — `exact 0.9833 -> 0.7593
  (-22.8%) [r-0003 0.9942, r-0015 1.0000, r-0016 0.7098, r-0017 0.3331]` — and
  `mycelium eval --bless` records per-case scores, so the next baseline can show where each
  case moved *from*. The complaint ADR-0044 recorded was attribution, not sensitivity: a
  slice mean cannot say whose move it was, and at these set sizes it never will.

- G3 reports rather than enforces on our own release set until roadmap 4.22 re-blesses it:
  growing a set changes its `cases_digest`, which is ADR-0051's designed behaviour.

### Fixed

- **Gate G3 can now see a case-set change** (roadmap 4.24,
  [ADR-0051](docs/adr/0051-hold-the-judgements-fixed-too.md)). A slice's score is a mean
  over the cases in that slice, so adding or re-grading cases changes the denominator — and
  G3 read a different denominator as a regression. Regenerating a derived set from 14 cases
  to 16 made it report `fact 0.632 -> 0.494 (-21.8%)` against a baseline blessed minutes
  earlier, when nothing had regressed. A baseline now records `cases_digest`, the identity of
  the judgements its numbers were taken over; when they differ the gate **reports and
  abstains**, and the movement is named as movement rather than in the vocabulary of
  regression. Both vendored baselines are armed by stamp — added lines only, no score moved.

- **The lexical index now matches inflections** (roadmap 4.19,
  [ADR-0048](docs/adr/0048-index-the-stem-beside-the-surface-form.md)). `signs` did not
  match `signed` and `contributed` did not match `contribution`, because FTS5's
  `unicode61` tokenizer does no stemming — one judged case was reaching its answer through
  a single unrelated word. Each indexed field now carries a **stem column beside** the
  surface one at a tenth of its weight, so a document spelling the query's word exactly
  matches two columns where an inflection matches one: reach without giving up the literal
  match, which is what a `porter` tokenizer would have cost (it fails gate G3 on both
  release sets). Measured: ours/release nDCG@10 0.463 → **0.508**, uv/release 0.492 →
  **0.548**, the ingested corpus **0.647**, `relationship` on our own set 0.169 → **0.346**,
  and **no slice regresses on any release set**.
  **A surface hit is the precondition for a stem hit**, so stems reorder what the surface
  index found and never introduce a document — without that, Porter's over-stemming
  (`organization` and `organ` collapse to one token) answered a judged `unanswerable` case
  out of a corpus that does not contain its subject, and gate G4 failed. The cost is that a
  query *none* of whose words the corpus spells literally still misses; that is roadmap
  4.23.

- **The watcher's infinite-rebuild guard was covered by a test that passed with the guard
  deleted** ([BUG-0020](docs/bugs/2026/09/BUG-0020-the-rebuild-loop-guard-was-covered-by-a-vacuous-test.md),
  roadmap 4.18). No behaviour changes — the filter and the watch scoping both work — but the
  end-to-end check for them asserted "no event arrives within two seconds" against a corpus
  whose derived store was outside the watched tree, so nothing was ever delivered to filter.
  The test now uses a corpus where the store *is* inside the watch (103 events to reject,
  measured) and bounds the negative with a sentinel edit rather than a clock, so a broken
  watcher fails loudly instead of passing vacuously.

- **[BUG-0019](docs/bugs/2026/09/BUG-0019-pack-atomic-does-not-invalidate-the-chunk-cache.md):
  turning `pack_atomic` on against an existing store changed nothing**, and the build
  reported success. The setting was missing from the chunk stage's config slice, so neither
  the environment digest nor the chunk cache key moved with it: every document looked
  unchanged and the previous boundaries were served under the new configuration. `--clean`
  was the accidental workaround. Found while flipping the default — the flip is exactly the
  operation the defect suppresses.

- **Gate G3 can now see a chunking change** (roadmap 4.13). G3 enforces its 2 % per-slice
  rule only when the run is comparable to its baseline, and comparability was the fold of
  chunk digests — so any change to chunk boundaries made the two runs "not comparable" and
  the gate abstained. The change class G3 is best placed to judge was the only one it could
  never see. A corpus now carries **two** fingerprints: `content_digest`, what the corpus
  says, and `corpus_digest`, how it was cut. Enforcement keys on the first, the second is
  reported, and a chunking change is gated with its cause named in the verdict. Measured
  with `[chunking] pack_atomic` off then on: chunk fold moved and content fold held
  identical on all three corpora with a baseline (932 → 731, 2244 → 568, 2073 → 624
  chunks). See
  [ADR-0045](docs/adr/0045-ask-the-documents-whether-two-runs-are-comparable.md).

### Added

- `mycelium.eval.case_set_digest`, and `cases_digest` on `EvalRunManifest` and on a
  committed baseline (with a `cases` count beside it, for whoever reads a diff between two
  baselines). `tools/stamp_baseline_fingerprints.py` arms it on existing baselines, and
  refuses unless Git shows the case set was frozen before the bless.

- **`mycelium search --explain` and `mycelium_explain` now report what each query term
  reached** (roadmap 4.21,
  [ADR-0050](docs/adr/0050-report-what-each-query-term-reached.md)). Ranking is silent about
  what it did not find — a term matching nothing contributes nothing, which is
  arithmetically identical to a term that matched and lost — and that silence once let a
  judged case score 0.395 for two milestones on the strength of a single stopword. Each
  distinct query word now comes back with document and chunk counts and **three
  distinguishable outcomes**: written that way, reached *only* by its stem, or absent from
  the corpus in every inflection. Surface and stem stay apart deliberately, so a term the
  stemmer rescued (roadmap 4.19) reads as a rescue rather than as a hit. Dead terms also
  become a note on the outcome, and a warning in the human output.
- `SqliteStore.term_hits`, `mycelium.store.TermHits`, and `SearchOutcome.terms` /
  `dead_terms`. The report is computed only when `search` is called with `explain=True` —
  two index queries per term, and the harness that measures p95 runs thousands of queries.
- **`mycelium eval --against <retriever>`** (roadmap 4.8,
  [ADR-0049](docs/adr/0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md)) —
  score a second retriever over the same cases, on the same snapshot, in the same anchor
  space, and record it in the run manifest (`incumbent`, `incumbent_overall`,
  `incumbent_per_slice`). `--against grep` is spec 04 §7.4's real incumbent. The report
  names the slices the incumbent still leads, which is the half an overall number hides:

  ```text
  vs grep: nDCG@10 0.548 against grep's 0.519 (+0.029) - ahead of the incumbent;
           still conceded: fact 0.403 vs 0.497
  ```

  Reported, never gated — §7.4 quantifies the gate at 1.0. CI runs it on all three corpora.
- **`mycelium build --no-pin`** (roadmap 4.14) — compile, publish and serve while leaving
  the authored tree byte-identical. Pinning a `mycelium_id` is the build's only write into
  your documents, and this switches it off; a document that has none takes an identity
  **derived from its path** instead of a minted one, so two builds of the same corpus
  produce the same snapshot. That second half matters more than the first: a pinning build
  of an unpinned corpus mints fresh ULIDs, so it never published the same corpus twice —
  which is what CI had been doing for two of the three corpora it scores. Works with
  `--watch`. See
  [ADR-0046](docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md).
- `mycelium.sdk.identity.derived_ulid` and `is_derived_ulid` — a reproducible identity for
  a document whose id cannot be recorded, and the exact test for one.
- `mycelium build --json` reports a `derived` list beside `pinned`, and a snapshot whose
  documents took derived identities carries a manifest warning naming the count.
- **`tools/stamp_baseline_fingerprints.py`** — arms that comparison on baselines blessed
  before it existed, by adding `content_digest` and **moving no score**, so roadmap 4.15's
  flip is measured against the line already drawn rather than one moved in the same change.
  It refuses to write if a corpus's chunk fold has drifted since its bless, because then the
  recorded numbers describe a different corpus and stamping would be a re-bless wearing a
  migration's clothes. It refused on this repository's own baseline — correctly, since our
  corpus has grown since that bless — so the two vendored corpora are armed and ours keeps
  the comparison it had, which roadmap 4.22 exists to settle.
- **`tests/test_frozen_release_sets.py`** — the frozen-release-set guard had no tests.
  Roadmap 4.15 recorded that a single change could flip `[chunking] pack_atomic`'s shipped
  default *and* re-judge the release set measuring it, because `src/mycelium/config.py` was
  missing from `TUNING_PATHS`; PR #61 added the path, and this is what keeps it — plus the
  assertion that every guarded path still exists, since a guard naming a file that moved
  guards nothing, silently.

### Changed

- **Mycelium OS now beats the `grep` incumbent on every corpus, including the one roadmap
  4.8 was filed about.** Measured on the release sets: `uv`'s documentation **0.548 against
  0.519**, this repository **0.504 against 0.271**. Neither of the two changes that closed
  it came from the thirteen re-rankings measured and refused along the way — it was the
  packed chunker (4.15) and the stemmed index (4.19), both changes to what gets *indexed*.
  `fact` on the second corpus is still the incumbent's and is filed as roadmap 4.25.
- **Store schema `mycelium/store/v4`.** The stem columns are a tokenization change, which
  is not migratable, so an existing store is recreated on the next build under the D-016
  rebuild policy and an older binary refuses a v4 store rather than reinterpreting it.
- `mycelium.store` exports `STEM_WEIGHT` and `expanded_query`; the new
  `mycelium.store.stemming` carries an in-repo Porter (1980) implementation, checked
  against SQLite's own C implementation over a real corpus vocabulary rather than against a
  transcription of the paper. No new runtime dependency.
- An evaluation run manifest records `stem_weight`, because a number measured on one index
  cannot be compared with one measured on another.

- **`[chunking] pack_atomic` is on by default** (roadmap 4.15). A table or code block may
  share a chunk with the prose around it instead of ending the run on both sides; it is
  still never *split*, and packing never crosses a heading. Measured on the frozen release
  sets: `uv-docs` **0.306 → 0.492** nDCG@10, `uv-docs-ingested` **0.385 → 0.647**, this
  repository 0.450 → 0.463, no slice regressed anywhere — and gate G3 **enforced** that
  verdict on both vendored corpora rather than abstaining, which is the first time it could
  see a chunking change (ADR-0045). Set `pack_atomic = false` for the v0.3 boundaries. See
  [ADR-0047](docs/adr/0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md).
- **Every corpus is re-chunked once** on the first build after upgrading. Anchors naming a
  section are unaffected; an anchor naming an ordinal inside a multi-chunk section may move,
  and a consumer holding one should expect `ANCHOR_GONE` and re-resolve.
- Spec 03 §5's chunking sentence is updated rather than deviated from: tables and code
  blocks are never split, and may now share.
- **The derived ingested judgement sets are regenerated** with the chunker (roadmap 4.23).
  They are carried mechanically from the second corpus's frozen sets, so a chunking change
  necessarily moves them; under packing the carry improves and the release set grows 14 → 16
  cases, because two judgements the coverage floor had been dropping now clear it. Queries,
  grades and slices are untouched.
- `tools/check_frozen_release_sets.py` no longer treats a *derived* set as a judged one —
  nothing in it is judged. Replaced by a stronger rule, not relaxed: a derived set may not
  move in the same change as the source it is carried from, and its contents are byte-checked
  against the generator on every CI run.
- The tools that build a committed corpus now build it with `--no-pin`, so running a
  generator no longer leaves 81 modified files behind.

- A build that *does* pin now re-pins a document whose recorded identity was derived
  (roadmap 4.14). The plan's fast path skips the frontmatter parse for an unchanged digest
  on the premise that a pinned id lives in the file; a derived id makes that false, so
  without this the first `--no-pin` build would have silently turned every later build into
  a no-pin build.
- CI's three evaluation builds use `--no-pin`, and `tools/measure_slice_decay.py` — which
  compiled the operator's own working tree — does too.
- **`mycelium eval --bless` records both fingerprints.** A baseline written before this
  change keeps the comparison it was written for and the G3 verdict says so, naming
  `--bless` as what arms the stronger one: treating the absent field as a match would let a
  stale baseline enforce against a corpus nobody checked, and treating it as a mismatch
  would stop enforcement everywhere at once.
- `mycelium.eval.corpus_digest_of` is replaced by `corpus_fingerprint_of`, returning a
  `CorpusFingerprint`. Pre-1.0, and `mycelium.eval` is not one of the five contracts that
  freeze at 1.0.

- **Six judged anchors were re-judged** (roadmap 4.12), and no code changed with them. Five
  name a chunk that `[chunking] pack_atomic` deletes, so they now name the section that chunk
  merges into — the smallest unit holding the answer under both settings; every judgment in
  all four sets now survives the flip (33/33, 17/17, 12/12, 18/18). The sixth, `r-0003`
  *Conventional Commits*, gained **AGENTS.md §6.3**: the rule is documented in three places
  and the judgment named two, omitting the one this repository calls its source of truth.
  Release baselines are re-blessed, so **every comparison across this change is invalid**.
  Measured cost, one build, shipped default: ours/dev +0.000, ours/release +0.002, uv/release
  +0.025 — the last from one case whose section anchor is satisfied by a chunk that does not
  answer it, accepted and explained in
  [ADR-0043](docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md).

### Added

- **`tools/measure_slice_decay.py`** — the instrument gate G3 cannot be. G3 refuses to enforce
  across a corpus change ([BUG-0014](docs/bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md))
  — correctly, because on a self-hosting corpus every PR moves the numbers — and the cost is
  that a slow decay can cross several milestones unremarked. This holds the judgments and the
  compiler fixed and varies only the corpus, checking any git ref out into a throwaway worktree
  and scoring both sides per slice and then per case. Roadmap 4.17's whole diagnosis is one
  command: `python tools/measure_slice_decay.py 9adad70 --set release`. See
  [ADR-0044](docs/adr/0044-name-what-a-two-case-slice-can-and-cannot-say.md).
- **Roadmap 4.19, 4.20 and 4.21**, filed out of that diagnosis: stem the lexical index without
  paying for it in `exact` (measured at +32 % on both release sets *and* failing gate G3 as a
  straight swap); give the thin judged slices enough cases to carry a gate, or state which ones
  G3 reports rather than enforces; and have `mycelium_explain` say when a query term matched no
  document at all.
- **`[chunking] pack_atomic`** — lets a table or code block share a chunk with the prose
  around it instead of standing alone (roadmap 4.11). Atomicity keeps its real meaning: a block
  is never *split*, packing never crosses a heading, and a section whose only content is code
  still yields a code chunk. **Off by default**, and measured on two corpora: on task
  documentation full of command blocks it is worth **+61 % nDCG@10** (0.280 → 0.451, no slice
  regressed, R@10 0.500 → 0.679) and collapses 2244 chunks to 568 with the under-25-token share
  falling from 47 % to 9 %; on long-form prose it is roughly neutral. It is off because moving a
  chunk boundary deletes an anchor, and five judged cases need re-anchoring before the default can
  flip — roadmap 4.12, with the flip itself as 4.15. See
  [ADR-0042](docs/adr/0042-let-an-atomic-block-share-its-chunk.md).
- **`tools/measure_chunking.py`** — shape, retrieval and **judged-anchor survival** in one
  command. The third axis is one no re-ranking ever needed: a chunking change can invalidate the
  benchmark it is measured by, so the cases that stopped measuring the change are counted and
  named rather than averaged in.
- **Roadmap 4.12** (re-anchor five cases), **4.15** (then flip the default) and **4.13** (gate G3 cannot
  see a chunking change — its corpus digest is folded from chunk digests, so any chunker change
  trips the "reported, not enforced" branch), and **4.14** (let a build compile without pinning
  `mycelium_id` into the tree, so measuring on a corpus is a read-only act).
- **`tools/measure_ranking.py` grew the section index, `--release` and `--oracle`** — the
  instrument behind roadmap 4.8's *second* refusal. It now carries **ten** candidate
  strategies and all ten are refused: the section-level indexing hypothesis
  [ADR-0031](docs/adr/0031-refuse-three-rerankings.md) named as the next thing to try, in six
  forms, plus the incumbent's own ranking function. `--release` prints the per-slice deltas
  gate G3 reads; `--oracle` prints the ceiling of the whole family — the per-case best of
  every strategy, which no planner can beat, and which sits **3 % above grep** on the corpus
  the item is about. One candidate *passed* G3 on both release sets and was refused anyway,
  because the dev set the gate does not read showed it returning a 14-token lead-in in place
  of the paragraph containing the queried phrase. Nothing in the query path changed. See
  [ADR-0041](docs/adr/0041-bound-the-section-unit-and-refuse-six-more.md).
- **Roadmap 4.11** — *make the chunk a comparable unit*. The hypothesis left standing after
  ten refused re-rankings: every failure traces to chunks of wildly unequal size, and no
  ranking rule repairs a unit that was already wrong when ranking saw it.
- **`tools/measure_pdf_structure.py`** — the harness behind roadmap 4.9's decision *not* to
  read PDF structure in v1. It measures what docling's ML pipeline would recover (82 % of
  headings, 43 % of code blocks, `src.bbox`, section-named anchors), what it costs (~2.4 GB
  and 3 s/page), whether it is reproducible (byte-identical on repeat, same machine), and what
  it buys in retrieval (a regression against the Markdown control). It needs ~2.4 GB that no
  CI runner should carry, states so, and refuses cleanly without it. See
  [ADR-0040](docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md).
- **Roadmap 6.7** — *score citation precision, not only rank*. Every metric the harness
  computes ranks chunks; none asks whether the anchor a reader is handed names the right
  thing. That gap is why 4.9 could not weigh the one benefit the ML pipeline does deliver.

- **A third judged corpus — the second one, ingested** (roadmap 4.10). The same 81 upstream
  documents as `eval/corpora/uv-docs`, rendered into DOCX, HTML and PDF and put back through
  `mycelium ingest`; what is scored is the evidence documents the projector wrote. It is
  built and gated in CI beside the other two. **Nothing in it is judged**: every query, grade
  and slice is copied from the frozen `uv-docs` sets and only the anchor is recomputed, so
  the document is the only thing that varies (ADR-0027's discipline, applied). See
  [ADR-0039](docs/adr/0039-measure-what-projection-costs.md) and the corpus's own
  [README](eval/corpora/uv-docs-ingested/README.md).
- **`tools/measure_projection_cost.py`** — the paired comparison this makes possible: the
  same cases over Markdown and over its ingested twin, per format, beside the size of the
  judged passage on each side. **Recall does not move** (R@10, R@50 ±0.000 in every format);
  where structure survives — DOCX, HTML — the numbers are *identical*; PDF's apparent
  ranking gain comes with a target 10.6× larger and is refused as an artefact. Reported in
  CI, never gated.
- **`tools/build_ingested_corpus.py`** and **`tools/build_ingested_cases.py`** — the corpus
  and the carried judgements. `build_ingested_corpus.py --check` re-ingests the committed
  sources and compares, and runs in the `ingest / lanes` CI job.
- **Roadmap 5.7** — *ingested documents are not in the graph*. Measured here: the Markdown
  corpus compiles 229 edges, its ingested twin 10. A relative link does not survive rendering
  and re-projection.

- **The ingestion fixture corpus and its element inventories** (roadmap 4.7) — the M4 exit
  gate, *zero silent element loss*, is now a test. `tests/fixtures/ingest/inventory.json`
  carries a hand-authored **declaration** of what each source document contains, in KIR node
  kinds, and the gate compares it with what every engine produced: a difference is either
  recorded with a reason a reviewer approved, or it fails. This is the half the fidelity
  report cannot supply — the report is computed from the KIR, so it cannot see an element
  that never became a node. See
  [ADR-0038](docs/adr/0038-declare-the-corpus-then-compare-it.md).
- **`tools/update_ingest_inventories.py`** — re-bless the corpus after an intended parser
  change. It regenerates only the machine half of the file and never the declarations or
  the approved deviations, so a regression cannot bless itself.
- **A new CI job, `inventory / zero silent element loss`**, and a matching `inventory`
  pytest marker.
- **New corpus fixtures**: an `elements` family covering the node kinds the original fixture
  never reached (deeper headings, an ordered list with a nested one, two code blocks, an
  image, a footnote, a thematic break), a `profile` family for the Markdown-only vocabulary
  (wikilinks, an embed, tags, a callout), and a two-page PDF whose second page has no text
  layer — one parse producing both a page locator and an opaque `lost` node.
- **Roadmap 4.10** — an ingestion-heavy corpus joining the eval set, the third clause of the
  M4 exit gate, filed with the judging trap ADR-0027 warns about written into it.
- **Ingestion quarantine** (roadmap 4.6) — a source the evidence lane refuses now leaves a
  `mycelium/quarantine/v0` record under `.mycelium/quarantine/` naming the stage that
  refused it (`acquire`, `dispatch`, `guard`, `parse`, `budget`), the reason, and the
  **custody digest of the bytes that caused it** — so a quarantined file can be opened
  again rather than only counted. Ingesting it successfully clears the record; `mycelium gc`
  never sweeps it. See
  [ADR-0037](docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md).
- **`mycelium ingest --forget <source>…`** — drop a quarantine record without ingesting, for
  a source that is never coming back.
- **Secret scanning at ingestion**, and `[ingest] redact_secrets` is honoured. Eleven
  structural rules — vendor key prefixes, PEM armour, credentials in a URL's authority —
  and deliberately **no entropy heuristic**, because a scanner that fires on base64 images,
  digests and UUIDs is one an operator switches off. A match is redacted **before the KIR
  is stored**, so the credential survives in exactly one artifact — the tier-1 original,
  which is what a citation is checked against — while the compiled document, its
  projection, its chunks and the index carry `[redacted: <rule-id>]`.
- **`Document.secret_flags` is populated**, through the ingested document's custody record
  (ADR-0034's mechanism), and **whether or not redaction acted**: flagging is the
  observation, redaction is the action, and switching redaction off should not silently
  also remove the record that a credential is there.
- **`mycelium doctor` reports two new conditions** — what is quarantined (as a warning: a
  recorded refusal is the system working), and, when `redact_secrets = false`, that
  credentials found in an ingested source are being written to the authored tree verbatim.
- **`GuardError` and `LossBudgetError`** join `mycelium.ingest.errors` as subclasses of
  `ParseError`, so a quarantine record can name its stage from the exception's type instead
  of parsing its message. Every existing handler is unaffected.
- **Verification: `mycelium verify`, `promote`, `demote`** (roadmap 4.5) — gate G7 as a
  per-document decision (D-021). `verify` recomputes citation coverage against the corpus
  *as it is*, which is what catches a candidate whose evidence has been edited,
  re-projected or deleted since it was written, and measures **sampled entailment** through
  an LLM judge when one is configured. `promote` moves a candidate into
  `knowledge/verified/`, refusing below the gate; `demote` moves it back and strips its
  verification block. See
  [ADR-0036](docs/adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md).
- **`entailment` is `None` when it was not measured**, never a number. There is deliberately
  no offline approximation: term overlap between a claim and its citation would look like a
  grounding score and would not be one. The recorded `grounding` is
  `min(coverage, entailment)`, so a perfect citation record cannot hide a failed entailment.
- **`verify --gate`** is the CI form and fails on a *measured* shortfall; an unmeasured
  entailment is reported and does not fail it. `promote` is stricter — there the unmeasured
  half is a blocker, and `--force` is the human override, recorded in the document as
  `verified_by: <name> (forced: <code>)` so it survives in Git.
- **`[verification]`** is honoured — `cites_coverage_min` (0.95), `entailment_min` (0.90),
  `auto_promote` (off: promotion is a human act), plus `sample_size` and `model_id`, which
  points the judge at a different model than the one that wrote. Unset, the writer grades its
  own work, and the report, the document and the CLI all say `self-judged`.
- **`[sources]`** is honoured — trust per origin, stamped at acquisition and carried by the
  document. `verify` reports the weakest trust among a candidate's cited evidence, and never
  gates on it.
- **`mycelium doctor` reports gate G7** — the floors, the judge, the sample size, and whether
  promotion is automatic — once a provider is configured.
- **`mycelium.markdown.frontmatter.upsert`** — one textual frontmatter writer, shared by
  identity pinning and by verification. It never re-serializes a human's block, and it never
  folds a value across lines.

- **The synthesis lane** (roadmap 4.4) — the LLM half of dual-lane ingestion (D-020).
  `mycelium ingest` now additionally authors a *candidate* document under
  `knowledge/candidate/` in which every claim-bearing block cites the evidence layer with a
  wikilink. The lane runs only when `[synthesis]` names a provider, so a default install
  still ingests entirely offline. See
  [ADR-0035](docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md).
- **`Synthesizer`** joins `Connector` and `Parser` in `mycelium.sdk.protocols`, with
  `SynthesisContext`, `EvidenceDocument` and `Synthesis` — the first plugin contract whose
  output is not a function of its input, so it declares itself non-deterministic and returns
  the identity of what produced the text.
- **The `wiki` plugin** (D-026): a closed citable vocabulary in the prompt, one repair
  round-trip when a draft breaks the contract, and a refusal when the second one does too.
  An ungrounded document is never written.
- **`[synthesis]`** is honoured — `enabled`, `plugin`, `provider`, `model_id`, `effort`,
  `max_output_tokens`, `instructions`, and `min_citation_coverage`, which defaults to **1.0**:
  every claim-bearing block cites, or nothing is written.
- **A new optional install, `mycelium-os[synthesis]`** — the official `anthropic` SDK, four
  packages. Nothing imports it unless a provider is configured.
- **`mycelium/synthesis/v0`** run records in tier-1 custody (`CustodyKind.SYNTHESIS`):
  provider, model, prompt digest, parameters, the evidence set, and the citations the
  document was accepted on. The compiler recovers them into `provenance.synthesizer`.
- **`mycelium ingest --no-synthesize`** skips the lane even when a provider is configured,
  and `mycelium doctor` reports the lane's state once one is.

### Changed

- The `pdf` parser's per-document warning now names
  [ADR-0040](docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md) beside ADR-0032,
  so an operator meeting "no headings, no tables" is one link from the measurements behind
  that limitation rather than from a decision they have to take on trust.

- **`[verification]` and `[sources]` are honoured**, leaving `eval` as the only section
  `mycelium.toml` accepts and nothing reads — and it may stay that way, since the harness
  takes its case set on the command line.
- **All three verification frontmatter fields are written by the verify machinery.** Spec 05
  §2's table assigns `verified_at` to `promote`; the compiler treats the three as a unit and
  warns about a partial block, so splitting their owners would warn on every candidate in the
  corpus. `promote` runs the measurement rather than writing the field itself (ADR-0036).
- **`verified_at` records when the grounding last *moved*.** The block is rewritten only when
  the score or the checker changed, so a nightly `verify` over an unchanged corpus produces no
  diff and no rebuild.
- Identity pinning now goes through the shared frontmatter writer rather than its own textual
  insert. Byte-compatible: the determinism golden did not move.
- The snapshot manifest's `config_digest` covers the two new sections. The golden is
  re-blessed with a one-line diff — every chunk byte-identical.

- **A wikilink into `knowledge/evidence/` is now a `cites` edge**, not `links_to` (spec 03
  §6). Folder-derived, so no store migration: `mycelium neighbors --type cites` answers what
  a document rests on.
- The snapshot manifest's `config_digest` now covers `[synthesis]`. The determinism golden is
  re-blessed with a one-line diff — every chunk is byte-identical.

- **Ingestion contracts and four parsers** (roadmap 4.1). `mycelium.sdk.protocols` declares
  the `Connector` and `Parser` Protocols, `Blob` and `PluginMeta` — the fourth of the five
  contracts that freeze at 1.0. Four adapters ship behind them: `markdown` (markdown-it,
  no optional runtime), `docling` (DOCX and HTML), `pandoc` (DOCX, HTML, ODT, EPUB,
  reStructuredText, LaTeX, through one `--sandbox`ed binary), and `pdf` (PDFium's text
  layer). One document rendered into DOCX, HTML and reStructuredText produces the same
  citable anchors as its Markdown original. See
  [ADR-0032](docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md).
- **`[ingest] parsers` and `[ingest] connectors`** — the pinned, ordered plugin lists.
  The first parser declaring a media type wins; a name that cannot be resolved is an error
  naming what to install, never a fall-back to whatever is installed (spec 05 §4.2). The
  default is `parsers = ["markdown"]`, which needs no optional runtime.
- **A new optional install, `mycelium-os[ingest]`** — `docling-slim` with its declarative
  format extras plus `pypdfium2`: no `torch`, no model weights, no network. The `pandoc`
  parser additionally needs pandoc 3.x on `PATH`.
- **`mycelium doctor` now reports the pinned parsers** and whether each one can run on this
  machine, with the remedy in the message — so an unavailable plugin is met before a build
  rather than during one.
- **Roadmap 4.16, 4.17 and 4.18** — three things roadmap 4.12 found and filed rather than
  absorbed: the ingested twin's carried judgements do not reproduce from their own
  generator ([BUG-0018](docs/bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md)),
  our release set's `relationship` slice has halved since the previous bless without this
  change causing it, and a watch-mode test that asserts *no* event arrives flaked once on
  macOS.
- **Roadmap 4.9** — read PDF *structure*, or record why v1 does not — filed with the three
  measured constraints (dependency closure, first-use model download vs NFR-6,
  cross-platform float reproducibility vs gate G6) as its acceptance criteria.

- **Tier-1 custody** (roadmap 4.2). An ingested source is stored verbatim under its own
  digest in `.mycelium/cas/originals/`, with the KIR compiled from it and a
  `mycelium/custody/v0` record of where it came from — written beside the blob, not into
  the store, because the store is disposable and evidence is not.
  `mycelium gc` never sweeps that subtree and now reports how much it kept;
  `mycelium doctor` re-hashes it and reports corruption instead of healing it.
  See [ADR-0033](docs/adr/0033-keep-the-original-and-bound-the-hostile.md).
- **`mycelium.ingest.ingest_source`** — the evidence lane end to end: acquire, store, guard,
  parse, store. The original reaches custody *before* the parse, so a file that is refused
  can still be examined afterwards.
- **Shape-based guards on untrusted input** (`mycelium.ingest.safety`). A ZIP container is
  refused from its own header when it declares a decompression bomb; markup nested or
  populated past a ceiling is refused from a single linear scan; and the shared KIR builder
  caps node count and text size, so a new adapter inherits the last line of defence. Every
  ceiling is set two orders of magnitude clear of anything measured on a real document.
- **A committed hostile fixture suite** under `tests/fixtures/ingest/hostile/`, each file
  generated by `make_fixtures.py` so what makes it hostile is reviewable, and each asserted
  to produce one typed failure inside a per-file time budget.

- **`mycelium ingest <path>...`** (roadmap 4.3) — the evidence lane end to end: acquire,
  keep, guard, compile, account, project. Each source is handled on its own, so one that
  cannot be read is reported and the rest continue; `--dry-run` takes custody and reports
  fidelity without writing a document. See
  [ADR-0034](docs/adr/0034-project-the-evidence-and-count-what-it-lost.md).
- **Evidence projection.** An ingested source becomes a Markdown document under
  `knowledge/evidence/` with provenance frontmatter, which `mycelium build` compiles like any
  authored file — so it arrives in the store with `ingested` trust, `evidence` status, chunks
  and citations, without anything but the compiler writing an index (D-020). Every KIR node's
  text survives the round-trip, proved per engine.
- **Fidelity reports** (`mycelium/fidelity/v0`), stored in tier-1 custody and linked from the
  document record. Three buckets — represented, degraded (structure simplified, content kept),
  lost — and the report is a pure function of the KIR, so anyone holding the KIR blob can
  recompute it and check the digest.
- **`[ingest] max_failed_elements` is honoured**: a projection whose *lost* fraction exceeds
  the budget is refused, with the counts and the setting's name in the message. A document
  with no elements at all is refused whatever the budget says. Both leave the original and the
  report in custody.
- **`source_digest` joins the frontmatter contract** as a fifth `mycelium ingest`-owned key.
  It is the link from a projected document to its tier-1 evidence, and the compiler reads the
  connector identity, the acquisition time and the fidelity report from the custody record
  rather than from four more frontmatter fields that could drift.
- **`mycelium.layout`** — a leaf module for the CAS layout and the durable-write primitives,
  which the build, snapshot publication and custody all need and none should have to import
  the compiler to get.
- **A hostile document can no longer take a build down.** Measured before the fix: HTML
  nested 5 000 deep took docling **45 s** (at 50 000, it never returned), and the same input
  made the pandoc adapter raise an uncaught `RecursionError` out of `json.loads`. Both are
  now refused in under 0.1 s as a typed `ParseError`.
- **An `opaque` node no longer names a CAS blob that was never written.** Where pandoc's
  payload is literal source text it is kept as the node's `text` — the treatment ADR-0006
  already gives raw HTML in authored Markdown — and `blob` is reserved for a payload that is
  actually in custody.
- **`[ingest]` is honoured by key rather than as a whole section.** `parsers` and
  `connectors` steer ingestion now; `redact_secrets` (roadmap 4.6) and
  `max_failed_elements` (4.3) are still accepted and digested but do nothing, and
  `mycelium doctor` names them individually. This extends
  [ADR-0014](docs/adr/0014-adopt-partial-strict-configuration.md) one level finer.
- **`[ingest] connectors` no longer names parsers.** Spec 05 §2's example
  (`connectors = ["markdown", "html", "pdf"]`) predates the Connector/Parser split in §4.1;
  the keys now match the Protocols, and the old shape is refused with the replacement in
  the message.
- The snapshot manifest's `config_digest` now covers the `[ingest]` section. The
  determinism golden is re-blessed with a one-line diff — every chunk is byte-identical.

### Fixed

- **[BUG-0018](docs/bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md) — the
  carried ingested judgements now reproduce from their own generator** (roadmap 4.16). The
  cause was not the chunker this record first suspected — measured, that change is a no-op
  with packing off — but an *incremental* build inheriting a store left behind by a
  measurement session, so the carry compared packed judged text against unpacked twin chunks.
  Both builds are now clean, `tools/build_ingested_cases.py --check` regenerates and compares
  in CI, and `eval/corpora/uv-docs-ingested/eval/carry.json` records every mapped anchor's
  coverage so drift shows as a number in a diff. `MIN_COVERAGE` is unchanged: it is a floor,
  not a dial.

### Deprecated

### Removed

### Fixed

- **A projected evidence document no longer records the absolute path of the machine that
  ingested it** ([BUG-0017](docs/bugs/2026/09/BUG-0017-evidence-frontmatter-carries-an-absolute-path.md)).
  The file connector stamped `file:///C:/Users/…` into every projection's provenance, so the
  same source ingested by two people produced two different documents and a local directory
  layout was published to whoever could read the repository. Sources inside the repository
  now get a relative-path URI (`file:sources/a.pdf`); anything outside keeps the absolute
  form. `mycelium ingest --forget` asks the connector for the same key rather than rebuilding
  it.

- **[BUG-0016](docs/bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md)** — a DOCX
  footnote's body vanished and the fidelity report called the document complete. Word keeps
  note bodies in `word/footnotes.xml`, a package part docling's DOCX backend does not read,
  so the text reached no KIR node and — the report being a pure function of the KIR — nothing
  downstream could tell that from a document with no footnotes. The adapter now counts the
  notes the container declares and records each one docling did not surface as an opaque
  `lost` element, so the loss is counted, charged to `[ingest] max_failed_elements`, and
  named in the projection. Found by the corpus above, on its first run.

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
