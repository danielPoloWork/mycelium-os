# Evaluation

The judged case set behind `mycelium eval`, and the honest account of what it does and
does not prove.

```bash
mycelium eval                      # score the default set against the published snapshot
mycelium eval --retriever grep     # the incumbent, for comparison (D-010)
mycelium eval --gate               # exit non-zero if a gate fails (CI mode)
mycelium eval --tasks              # the agent-task suite against the grep loop (D-010)
mycelium eval --bless              # freeze this run as gate G3's baseline
mycelium eval --json               # the run manifest, machine-readable
```

Runs are written to `.mycelium/eval/<run-id>.json`. A report without a manifest is
exploratory and cannot satisfy a gate (spec 04 §7.5).

## The case sets

Six of them: a **dev** and a **release** set per corpus (spec 04 §7.1, ADR-0027).

| set | cases | corpus |
|---|---:|---|
| [`dev.jsonl`](dev.jsonl) | 20 | this repository's documentation |
| [`release.jsonl`](release.jsonl) | 286 | this repository's documentation |
| [`corpora/uv-docs/eval/dev.jsonl`](corpora/uv-docs/eval/dev.jsonl) | 22 | [`uv`'s documentation](corpora/uv-docs/README.md) |
| [`corpora/uv-docs/eval/release.jsonl`](corpora/uv-docs/eval/release.jsonl) | 404 | the same |
| [`corpora/uv-docs-ingested/eval/dev.jsonl`](corpora/uv-docs-ingested/eval/dev.jsonl) | 22 | [the same documents, ingested](corpora/uv-docs-ingested/README.md) |
| [`corpora/uv-docs-ingested/eval/release.jsonl`](corpora/uv-docs-ingested/eval/release.jsonl) | 404 | the same |

**The release sets were authored to the count their own slices need at roadmap 6.8**
([ADR-0136](../docs/adr/0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md)): 19,
25 and 25 cases until then, which is why the row below about four-case slices reads the way it
does. `enforceable_at` derives, from a slice's blessed mean and its median non-zero per-case
score, the count at which no single case can trip its −2 % bar alone (ADR-0123) — 50 to
97 per slice across these sets — and until the authoring landed **G3 enforced nothing, on
any set**. The dev sets are unchanged and are roadmap 6.33's work: they are reported rather
than gated, so their job is the overfitting gap rather than enforcement.

`uv/dev` was twelve of those cases until roadmap 4.39, with one `exact` case, one `symbol`
case and no `relationship` case at all — thin enough that a field-weight change scored
*exactly* the baseline on it, whatever the setting (ADR-0058). Ten cases written from the
documents brought the thin slices to four each, which is the threshold ADR-0052 arms a slice
at, and the effect was immediate: the leaf-heading weight the dev set could not see before now
peaks visibly at 3.0 and is **refused** at 4.0 (ADR-0067). Read that ADR before adding cases —
it also records the design mistake in four of the ten, kept rather than corrected.

The third corpus is the second one **put through `mycelium ingest`** — the same 81 upstream
documents rendered into DOCX, HTML and PDF, and scored as the evidence documents the
projector wrote from them (roadmap 4.10). Its cases are not judged here: every query, grade
and slice is copied from the `uv-docs` sets and only the anchor is recomputed, so the
document is the only thing that varies. Of the 404 cases carried at roadmap 6.8, **every one survives**; 27 anchors fall through the
coverage or `whole` floor — mostly uv's feature list, which the HTML lane shatters into a
heading per item (ADR-0111). Every drop is printed by the generator and every surviving mapping
is recorded in `carry.json`. The same item re-rendered 25 of the corpus's binary sources,
because judging a document for the first time is what takes a format slot (ADR-0056): the
assignment is now 22 DOCX, 22 PDF and 37 HTML. `docs/index.md` is left unjudged on purpose —
it is the only document here with raw inline HTML, and the site roadmap 5.40 tests ADR-0110's
rule on end to end.

**The release set is what CI gates. The dev set is what tuning may look at.** A release run
scores the dev set beside it and prints the gap — reported, never gated, because nobody has
the evidence to set a threshold and a constant chosen to look rigorous is worse than a number
a reviewer reads. The gap is the overfitting signal G3 cannot give: G3 compares a run to a
baseline over the *same* cases, so a change that fits those cases better passes it by
construction.

The existing twenty cases became the **dev** set rather than the release set, because four
ADRs' worth of tuning already read them. Relabelling them would have frozen the set the
product was fitted to and called it independent.

Regenerate either corpus's sets with:

`tools/build_ingested_cases.py --check` regenerates the carried set and compares instead of
writing; it runs in CI, because a derived artifact whose generator no longer reproduces it is
a defect rather than a cue to regenerate ([BUG-0018](../docs/bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md)).
`eval/corpora/uv-docs-ingested/eval/carry.json` is that carry's receipt: every mapped anchor's
twin and its coverage, committed so drift reads as a diff of numbers, plus the `collapsed`
block naming each twin chunk that several distinct judged units landed on (roadmap 5.33).

```bash
python tools/build_eval_cases.py           # this repository's documentation
python tools/build_uv_docs_cases.py        # the second corpus
python tools/build_uv_docs_tasks.py        # the second corpus's agent tasks
python tools/build_ingested_corpus.py      # the third corpus's evidence documents
python tools/build_ingested_cases.py       # ...and the judgements carried onto them, tasks included
```

Those five ingest and carry; none of them renders. Re-rendering the third corpus's binary
sources is `--render`, a one-time provenance act, and it needs pandoc plus the pinned PDF
renderer — which is declared in its own dependency group and deliberately left out of the
default sync, because it is 62.5 MB and CI never renders
([ADR-0098](../docs/adr/0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md)):

```bash
uv sync --group render                              # the pinned typst, 62.5 MB
python tools/build_ingested_corpus.py --render      # a provenance act, not a refresh
```

`--render` refuses before writing anything if a PDF is due and the renderer is absent, and
prints the version it used. A routine `uv sync --all-extras --dev` removes it again, by
design.

The judgments live in those scripts as data, so every anchor is validated against a real
build before a set is written.

## Did the retriever get worse, or did the corpus get bigger?

```bash
python tools/measure_slice_decay.py <git-ref> [--set release]
```

Gate G3 refuses to enforce across a corpus change ([BUG-0014](../docs/bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md)),
which is right — this repository's documentation *is* its corpus, so every PR moves the
numbers — and the cost is that a slow decay can cross several milestones unremarked. That is
what happened to `relationship` on our own release set: 0.304 to 0.106, unnoticed
(roadmap 4.17). A *chunking* change is no longer one of the cases it abstains on: comparability
is judged on the documents, so moving every boundary in the corpus is gated (ADR-0045).

This tool asks the question the gate cannot. It holds the judgments and the compiler fixed and
varies only the corpus — the named ref goes into a throwaway worktree, today's judged sets are
copied in, both sides are compiled with today's compiler — then prints per-slice deltas and,
for the slices that moved, the per-case ranks behind them. A slice that moves here moved
because documents arrived; one that does not is telling you to look at the code.

**Read the per-case lines, not the slice mean.** A slice mean cannot distinguish a regression
from one case's luck, which is a finding about the sets rather than a caveat about the tool
([ADR-0044](../docs/adr/0044-name-what-a-two-case-slice-can-and-cannot-say.md)). Roadmap 4.20
acted on it — G3 now prints the cases behind any row it reports or fails, and enforces only
the rows that can carry it
([ADR-0052](../docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md)) — but at these set
sizes the per-case lines are still where the answer is.

### What a baseline records

`eval/baselines/<set>.json`, per retriever:

| field | what it holds | what G3 does with it |
|---|---|---|
| `per_slice`, `overall_ndcg_at_10` | the frozen scores | compares against them |
| `content_digest` | what the corpus *says*, from chunk text | **decides whether it enforces** |
| `corpus_digest` | how the corpus was *cut*, the fold of chunk digests | reports it, names a re-cut |
| `cases_digest` | which judgements the means were taken over | **decides whether it enforces** |
| `cases` | how many, for whoever reads a diff | nothing |
| `per_case` | each case's nDCG@10, per slice | names the case behind a move (ADR-0052) |
| `blessed_from_snapshot`, `toolchain` | provenance | nothing |

A baseline missing one of the digests keeps the comparison it was written for, and the
verdict says which one is unarmed — reading an absent field as a match would let a stale
baseline enforce, and reading it as a mismatch would disarm the gate everywhere at once.
`tools/stamp_baseline_fingerprints.py` arms an older baseline without re-blessing, and
refuses when it cannot verify that the corpus or the case set was frozen before the bless.

### What gate G2's verdict records

`eval/g2-verdict.json` is the same idea one gate along, and it exists because G2 has no
automated *measurement* — only an automated *check* (roadmap 4.40, ADR-0068). One file, all
six judged sets:

| field | what it holds | what `--check` does with it |
|---|---|---|
| `sets.<corpus>/<set>` | both arms' nDCG@10, the per-slice figures, the verdict, the case count | compares the **verdict** where a re-measurement is possible |
| `decision` | which profile the *release* rows support | **fails** when it disagrees with `shipped_profile` |
| `shipped_profile` | `[retrieval] profile`'s built-in default when the verdict was taken | **fails** when the default has since moved |
| `retrieval_identity` | a digest of the field weights, stem weight, stopword membership, fusion constants and FTS schema | **fails** when the lexical arm has moved |
| `corpora.<name>.content_digest` | what each corpus *said* | **fails** for a `dated` corpus; reports for `ours` |
| `corpora.<name>.chunks_digest` | how it was *cut* | reports a re-cut |
| `sets.….cases_digest` | which judgements the means were over | **fails** for a dated corpus; reports for `ours` |
| `recorded_at`, `model_id`, `toolchain` | provenance a reader can act on | prints it |

`dated_corpora` is the two vendored ones. `ours` is measured and recorded but never gated,
for the reason the next section gives about G3: this repository's corpus moves on every pull
request, and a control that fires on everything selects for being ignored.

Two fields deliberately do **not** match their namesakes in `baselines/<set>.json`, and a
reader comparing them should know why. `cases_digest` here is taken over the *answerable*
cases only, because G2 compares two retrievers' rankings and an `unanswerable` case has no
ranking to compare — abstention is G4's gate, not this one. The corpus digests, by contrast,
match the baselines exactly, and that is the evidence this record reproduces in CI: those are
the fingerprints G3 already enforces against on a Linux runner.

**The check never fails because hybrid lost.** "Ship lexical-only" is a legitimate G2
outcome, so the failures above are all the same kind of thing: a recorded claim that no
longer describes the product. The remedy is one command —
`python tools/measure_hybrid_gate.py --record`, which needs the model.

### What a −2 % slice bar means over four cases

Both G2 and G3 carry spec 04 §7.3's second condition — *no slice worse than −2 %* — and it is
worth stating what that demands at the sizes these sets have, because the words suggest
something about a *category* of question and the arithmetic says something about **one**
question.

A slice of `n` cases with a lexical mean of `m` trips when a single case loses more than
`0.02 · n · m`. Measured across the six judged sets at roadmap 4.41, that threshold runs from
**0.007 to 0.089** nDCG with a median of **0.053** — against a median losing case of
**0.126**. So a *typical* losing case trips its slice on its own: at four to seven cases the
condition is a **per-case veto** wearing a percentage's clothes.

For it to require more than one case to move, at the losses actually observed, a slice needs
**n ≥ 35** — five to nine times what it has. That is the direction spec 04 §7.6 already
points (≥ 1 000 cases at 1.0), and it is filed as roadmap 6.8.

Two things follow, and they are the reason neither bar is moved:

- **The trips are real.** Decomposed case by case, six of the seven slices hybrid trips are
  *one* case each, and every one is a large loss — `u-1016` 0.635 → 0.289, `u-1022`
  0.885 → 0.426, `u-1021` 0.316 → **0.000**. The condition is catching harm, not noise. G2
  in particular has no confounder: it compares two retrievers on the same cases, the same
  snapshot, the same instant.
- **And it is unmeetable.** Hybrid moves 55 % of the 119 answerable cases and worsens 15 %,
  so over five or six slices something trips on almost any set. G2 therefore cannot promote
  hybrid until the sets grow — which is a burden that cannot be discharged, not a weighing
  that came out against it.

The mitigation in the meantime is that every verdict now **names** the cases behind a tripped
slice, so a reader can make the distinction the arithmetic cannot (ADR-0069).

**Closed at roadmap 6.8** ([ADR-0136](../docs/adr/0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md)),
and the number above was the wrong one. `n ≥ 35` came from the median loss *observed*;
the bar has to survive the loss a single case *can* inflict, which is its whole score when it
leaves the top ten — so the requirement is a property of each slice's own mean and spread,
computed by `enforceable_at`, and it runs **50 to 97** cases (ADR-0123). The three release sets
were authored to it: 286, 404 and 404 cases, every gated slice at or above its own count. The
section above is kept because it is the arithmetic that says why the authoring had to happen,
and because the dev sets are still the size it describes (roadmap 6.33).

### Which sets a gate can live on

G3 needs the corpus held fixed, and **this repository's documentation is its own corpus** —
every PR here adds an ADR, a journal entry, a CHANGELOG line, so `content_digest` moves and
G3 abstains. That is not a defect to work around; it is the standing state of a self-hosting
set, and roadmap 4.22 settled what follows from it
([ADR-0053](../docs/adr/0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)):

| release set | corpus | G3 |
|---|---|---|
| [`release.jsonl`](release.jsonl) | this repository's documentation, authored here | **reported** |
| [`corpora/uv-docs/…/release.jsonl`](corpora/uv-docs/eval/release.jsonl) | vendored, frozen | **enforced** |
| [`corpora/uv-docs-ingested/…/release.jsonl`](corpora/uv-docs-ingested/eval/release.jsonl) | derived from the vendored corpus, frozen | **enforced** |

Our baseline is still committed and still re-blessed, for two reasons that survive not
being a gate: G3 *reports* the deltas against it, and a report against a corpus that no
longer exists is a number that looks like a measurement; and since ADR-0052 it carries the
per-case scores, which are the only continuous per-case record of our own corpus. So it must
be current, and **a re-bless is its own PR** — per-slice diff in the body, never riding along
with a retrieval or judgment change. `measure_slice_decay.py` above is what asks the
regression question on that set.

The two frozen sets were last blessed at roadmap 4.26, where they grew from 16 judged cases
to 25 and gate G3 went from `1 of 6 slice(s) enforced` to **5 of 6**; our own set was last
blessed at 4.22. A bless on a frozen set *does* ride with the judgement change that occasions
it — leaving it out would disarm the only enforcing gate and make re-arming it somebody's
errand — and never with a retrieval change, which is the conjunction
`check_frozen_release_sets.py` refuses (ADR-0056 narrows ADR-0053 on exactly this).

## The harness scores the product's seam, and did not always

Until roadmap 4.28 `MyceliumRetriever` called `store.search_chunks` directly — a
re-implementation of the query path rather than the path itself — and it tokenised the query
with `terms_of` on the way. **The product did not.** So the harness had been measuring a
function-word boundary the product never had, for four milestones and seven ADRs: every
number in this directory, in the baselines and in the root README described a query path no
user could reach. Measured through the product's own tokenisation, `uv/dev` read 0.510 where
the harness reported 0.673, and against its own committed baselines the product as it stood
would have failed gate G3
([ADR-0057](../docs/adr/0057-drop-the-function-words-and-score-the-seam-that-ships.md)).

Both halves are closed. The product drops function words itself
(`mycelium.retrieval.query_terms`, one list, imported here rather than restated), and this
retriever goes through `mycelium.retrieval.search` — the seam the CLI and the MCP server
use — so a query-path change cannot reach the product without reaching every measurement of
it. Routing it there moved no case on any set; `query: stopped` scoring exactly
`baseline (ships)` is the standing check.

## Candidate re-rankings, and why none of them shipped

```bash
python tools/measure_ranking.py                     # the dev sets - what tuning may read
python tools/measure_ranking.py --release           # the gate view, per slice
python tools/measure_ranking.py --oracle            # the ceiling no planner can beat
python tools/measure_ranking.py --stems             # why an IDF floor cannot find a function word
```

Ten candidate strategies live in that tool and **all ten are refused** — four rows by
[ADR-0031](../docs/adr/0031-refuse-three-rerankings.md) (a length prior at two floors,
coverage-first, section aggregation) and six by
[ADR-0041](../docs/adr/0041-bound-the-section-unit-and-refuse-six-more.md) (five more ways to
make a section the unit, plus the incumbent's own ranking function). They are kept rather
than deleted, because a refusal nobody can re-run is a claim, and the next attempt should
start from the numbers.

`--oracle` is the instrument worth knowing about: it scores, per case, the best any strategy
achieves. Nothing realisable can beat it, so when its ceiling sits 3 % above the incumbent
the family is closed — which is how roadmap 4.8 stopped being a search for one more re-rank
and became a chunking item (4.11).

**A judgment must be true under every configuration the set is scored under.** The rule
above assumes one chunker. When a chunking change is pending — `[chunking] pack_atomic` was
the first, measured at roadmap 4.11 and flipped on at 4.15 — a judgment naming a chunk that
the change deletes scores zero however good the retrieval was. So the unit a judgment names is the smallest one holding
the answer under *both* settings: still the chunk where the chunk survives, the section where
the change merges it away. Five cases were re-anchored on that basis at 4.12 and nothing else
was widened; the reasoning, and the one case where it overrides ADR-0029's caution with the
cost measured, is in
[ADR-0043](../docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md).

**A `relationship` case relates two things, and does not also test vocabulary.** Four cases
written at roadmap 4.39 took `u-1022`'s note — *"the query uses neither's noun"* — as a design
rule and applied it to all four, which made every one of them a vocabulary-gap case as well.
The slice reads 0.090 against grep's 0.093: neither retriever serves it, so it discriminates
nothing. Testing two failures at once measures neither. The four are kept, because they were
found wanting *after* they were committed and rewriting a case that scored badly is
indistinguishable from fitting the set — the reasoning is in
[ADR-0067](../docs/adr/0067-grow-the-dev-set-before-asking-it-a-question.md).

**A judgment names where the thing is documented, not where it is framed.** The unit rule
above says chunk-or-section; this one says *which* chunk or section. A `symbol` case — a
query that is a named thing — names the section that documents it at grade 3; a page that
frames it, defines a sibling, or mentions it in passing is a lesser grade or none, never the
primary anchor. `u-1007` (`uv tool install`) broke it and scored 0.0000 for four milestones:
its one anchor was a section whose subject is the *interface* rather than the command.
Re-judged at roadmap 4.34, with the reasoning and the honesty note — the incumbent gains
twice what we do — in
[ADR-0062](../docs/adr/0062-a-symbol-judgment-names-where-the-thing-is-documented.md).

That ADR added, in passing, that the same section is the correct grade-3 home of `u-0006`
(`uvx`, which it defines). **It is not, and roadmap 4.37 is where that was settled**: a
section's subject does not change with the query asked of it, so one section cannot be the
*documenting* home of two sibling commands under a rule that gives grade 3 to the section
that documents the thing. `uvx` is documented by `guides/tools.md#running-tools` — *"The
uvx command invokes a tool without installing it"* — the counterpart of the
`#installing-tools` section 4.34 promoted, and the framing section keeps a 2 in both cases.
Re-judging it turned a silent zero into a **visible concession**: `symbol` on uv/dev now
reports `conceded on 1 of 1 case(s): u-0006 0.373 vs 0.465`, because grep was already ahead
on the case while we scored nothing. The three grades, the alternative that was priced and
rejected, and what to revert to if you read the two sections the other way are in
[ADR-0065](../docs/adr/0065-one-section-cannot-document-two-commands.md).

**Freezing is a conjunction, not an immutability.** Sets have to grow, so
`tools/check_frozen_release_sets.py` refuses a change that edits a release set *and* touches
retrieval, chunking, the store or the metrics. One change may move the retriever, or move
the judgments, and not both — which is the failure that actually happens: a run comes back
worse, a judgment looks wrong in hindsight, and the set quietly becomes the thing that fits.

A **derived** set used to be forbidden from moving with its source as well, and that rule is
retired (roadmap 4.26,
[ADR-0056](../docs/adr/0056-make-the-format-assignment-append-only.md)). It was a proxy for
"this file was not hand-written", and the direct check exists: `build_ingested_cases.py
--check` regenerates the carry and byte-compares it in CI, whichever commit it arrived in.
What the proxy did do was deadlock growth — a source that gains cases must regenerate its
carry, and a regeneration alone has nothing to regenerate from — which is what stopped the
`uv` sets from growing at 4.20 and the chunker from moving at 4.15.

**A format, once assigned, is never reassigned.** The third corpus renders the documents a
judgement points at into DOCX, HTML and PDF in rotation, and that rotation runs over a
recorded order — `corpora/uv-docs-ingested/format-rotation.json` — rather than over the
judged paths re-sorted on every run. Sorting made the corpus unable to grow: a newly judged
document sorts *between* existing ones and re-rolls every format after it, and those
renderings are committed provenance that cannot be re-derived (ADR-0039). Appending
re-rendered two documents where sorting would have re-rendered eighty-one.

**Corpus:** this repository's own documentation, as `mycelium.toml` defines it —
`[project] exclude` drops `tests` (fixtures are test data, not knowledge), `docs/journal`
(it grows every session and would churn judgments for no gain), `eval/corpora` (the second
corpus is measured separately, not mixed in), and the legacy tree. That line is not
housekeeping: before it existed, a query about message brokers was answered by a *test
fixture* and gate G4 read 25 %
([BUG-0007](../docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md)).

**Three guards keep the sets honest**, because each trap is easy to walk back into:

- A judged anchor must exist in the corpus. Headings move.
- An `unanswerable` case must be unanswerable by *either* retriever — grep matches word
  prefixes, so a case that separates the two is measuring tokenisation, not abstention. It
  caught a replacement query this repository's documentation had grown into, and caught
  three more on the second corpus on their first run (`ratio` matches `rationale`).
- A grade-3 anchor that is a heading stub **warns**. It found four mis-judgments the moment
  it existed — and it stays a warning because short is only a proxy for empty: `## License`
  followed by one line naming the licence is 24 tokens and is a complete answer.

**Slices covered:** `exact`, `symbol`, `fact`, `conceptual`, `relationship`, `injection`,
`unanswerable`. Metrics are always reported per slice — an overall win never excuses a
protected-slice loss.

### Which slices gate G3, and which it only reports

A slice's score is a mean, and a mean over one case is that case wearing a slice's name: the
smallest move it can make is the case's whole range, against a 2 % threshold. So G3 enforces
a slice only when all three of these hold, and **names the row and the reason** when one does
not ([ADR-0052](../docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md)):

| | why |
|---|---|
| it is not `unanswerable` | that slice scores 0.0000 by construction and a *fall* in it means the system got better at staying silent; **G4** gates it |
| the baseline is above zero | a relative threshold cannot fail a zero, so a row blessed at 0.0000 is unfailable whatever it does |
| it holds ≥ 4 judged cases | below that the row is one case relabelled — and 4 is a line drawn on a continuum, not a statistic: at these set sizes no honest threshold exists |

The verdict says so out loud — `4 of 6 slice(s) enforced; reported only: symbol (blessed at
0.0000: a relative threshold cannot fail it); …` — because a gate that reports "6 slices
compared" while four of them cannot fail is describing its own coverage inaccurately.

What makes G3 a regression gate rather than a single-case alarm is set size, and until
roadmap 6.8 no set had it: four cases here, five judged at 4.20, `1 of 6 slice(s) enforced` on
the `uv` sets until 4.26 lifted them — and then, once ADR-0123 derived the count each slice
actually needs, **none of them enforced at all**. The release sets were authored to that count
at 6.8 (ADR-0136) and now hold 286, 404 and 404 cases; the `uv` sets remain the ones G3
enforces on, since ours is never comparable (ADR-0053).

## Chunk or section: the judging rule

A judgment may name a chunk (`docs/a.md#setup/2`) or a section (`docs/a.md#setup/`, with the
trailing slash). A section is satisfied by any chunk under it and **credited once** (ADR-0029).
Which to write is a judgment about the document:

> **Name the section when a reader needs more than one chunk to have the answer** — a
> procedure with the example that shows it, prose plus the table that lists it, a search order
> stated across paragraphs. **Name the chunk when the answer is confined to it** — a literal
> term, one stated fact, a paragraph that stands alone.
>
> When it is genuinely unclear, name the chunk. That is the reading that cannot flatter us.

The rule exists because judging a chunk of a twelve-chunk section measures where the *chunker*
splits, which has nothing to do with retrieval — and because a chunk anchor carries an ordinal,
so [ADR-0023](../docs/adr/0023-make-the-chunk-target-steer-size.md)'s chunking knob invalidates
one and leaves the other standing.

## What projection costs

The third corpus exists to answer one question the other two cannot: **is an evidence
document projected from a binary source as retrievable as the Markdown a human would have
written?** `python tools/measure_projection_cost.py` scores both corpora over the cases they
share and prints the difference per format, then per case. On the release set, the same 25
cases twice:

| | n | nDCG@10 | MRR | R@10 | R@50 | judged passage |
|---|---:|---|---|---|---|---|
| overall | 25 | 0.614 → 0.619 | 0.590 → 0.615 | 0.826 → 0.783 | 0.891 → 0.848 | |
| docx | 8 | 0.567 → 0.558 | 0.507 → 0.498 | 0.812 → 0.812 | 0.875 → 0.875 | 1.1× |
| html | 3 | 0.667 → 0.667 | 0.667 → 0.667 | 0.667 → 0.667 | 0.667 → 0.667 | 1.0× |
| pdf | 7 | 0.560 → 0.643 | 0.525 → 0.629 | 0.857 → 0.714 | 1.000 → 0.857 | **4.7×** |

**The one apparent gain is PDF's ranking, and it is not one.** The last column is the
mechanism: a PDF has no headings, so its chunks are packed to the token budget and the
carried anchor averages nearly five times the Markdown chunk it came from. A bigger target
is easier to rank highly — and recall falls in the same row, which is what actually
happened to those documents.

**Read the per-case block before the averages.** Three release cases score *above* their own
source — `u-1006` +0.569, `u-1001` +0.324, `u-1003` +0.075, all PDFs — and those three are
the whole of the `pdf` row. A twin cannot be easier than the Markdown it was projected from;
where it is, something upstream of the measurement is wrong, which is why the tool names
those cases rather than averaging them away
([ADR-0097](../docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md)).
The dev set says the same thing from the other side: the twin is **worse overall** there
(−0.032), `docx` −0.037 and `html` −0.108, and `pdf` is again the only row that rises
(+0.111) on the strength of its one above-source case.

**And read the `whole` column with the negatives.** The carry records, per anchor, the share
of the judged passage's word *occurrences* the twin chunk it chose actually holds (roadmap
5.31). Below 1.0, part of what a case is judged on is in a neighbouring chunk that nothing
credits — 43 of 54 anchors land whole, and the two largest negatives here are the two lowest
shares among scored cases. `u-1004` is the worked example: 0.000 against 0.387 on its source,
not because a page-sized chunk is too big for the query but because a page boundary fell
*inside* the section and left the sentence that answers it in the chunk before, which both
retrievers rank far higher and no judgement names
([ADR-0102](../docs/adr/0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md)).
The same boundary rule gains `u-1003` in the same document by merging two sections, so this
is a number to read a case with and not a predictor: the largest *gain* in the table is a
split passage too.

**And read the `shared` column with the positives — it closes the question above.** A
headingless PDF is one page-sized block where the Markdown had sections, so several judged
passages can land on the *same* twin chunk: `shared` counts how many, and all three
above-source cases have it while nothing else in the table does (roadmap 5.33). The starkest
is `python-versions-pdf-*.md#/0`, which four cases judge as their grade-3 answer where their
sources named three different passages — a retriever returning that one block has answered
all four. So the twin being easier there is not a retrieval finding but a distinction the
projection destroyed, which is the thing this corpus exists to detect, and the cases are kept
and marked rather than dropped. It is a reading aid like `whole`, not a predictor: seven cases
share a chunk and three gained, because the other four were already at the ceiling or the
floor on both sides. Within a *single* case the same collapse used to name one anchor twice —
`u-1001` and `u-1003` both did, and the harness keys judgements by anchor, so each scored
against the lower of its two grades until they were merged at the highest
([ADR-0104](../docs/adr/0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md)).

Reported, never gated: with three to eight cases per format there is no threshold anyone
could defend ([ADR-0039](../docs/adr/0039-measure-what-projection-costs.md)).

The same run also found what projection costs that nobody was measuring: the Markdown corpus
compiles **229 edges** and its ingested twin **10**. A relative link between two documents
does not survive rendering and re-projection. Filed as roadmap 5.7.

### The three lanes do not lose the same things

An inline code span is how this corpus *names* a command, and only one of the twin's three
lanes can carry one across (roadmap 5.29,
[ADR-0100](../docs/adr/0100-declare-what-a-lane-cannot-carry.md)):

| lane | documents | code spans carried | documents carrying one |
|---|---:|---:|---:|
| html | 62 | **1 215** | 46 |
| docx | 10 | **0** | 0 |
| pdf | 9 | **0** | 0 |

So roadmap 5.25's result — *the twin names commands again* — is a statement about the HTML
lane, and this table is what keeps it from reading as a statement about ingestion. The cause is
not ours and not fixable here: pandoc writes inline code into a DOCX as a `VerbatimChar`
character run (224 in the largest of them), and docling's DOCX backend exposes a run as bold,
italic, underline, strikethrough or script with **no monospace**, so the distinction is
destroyed before this project's adapter is called. A PDF text layer never had one.

What *is* ours is saying so. Each DOCX and PDF projection carries the declaration in its
fidelity report, so the corpus says which of its 81 documents are which rather than leaving it
to a reader's memory. Nothing is charged to the loss budget: no content disappears —
`__token__` arrives with every character — and only the naming is gone.

## What this set is not

- **The judgments are still not independent, and only half the problem moved.** Nobody here
  wrote `uv`'s documentation, so a query over that corpus has to be guessed the way any
  reader would guess it. But the same agent that builds the retriever still assigns the
  grades on both corpora. Removing that needs judgments from someone else, which is what
  1.0's published guidelines and redistributable subset are for (spec 04 §7.6).
- **Relevance is chunk-exact, and that is measuring something narrower than it looks.** A
  case naming one anchor for a section the chunker split into twelve scores 0 even when the
  retriever returns five chunks of that very section — which is what happened on the second
  corpus, where the judgments were not written by someone who knew where chunk boundaries
  fall. The cases are left as authored and the question is filed as roadmap 3.15: re-judging
  after seeing a ranking cannot be told apart from fitting the set to the result.
- **The ingested corpus's anchors were carried, not judged — and the rule is not neutral.**
  `build_ingested_cases.py` picks the twin chunk with the most word overlap with the judged
  passage, which is mildly favourable to the ingested side. Every conclusion drawn from that
  corpus is stated in the direction the bias does not help.
- **93 cases is the floor the spec asks for at this phase, not a benchmark.** 1.0 wants
  ≥ 1 000. Small sets move a lot on single-case changes, so read differences of a few points
  as noise — and that remains true of every gated slice, four cases or not (ADR-0052).
- **Absolute numbers are not targets.** Pre-GA the discipline is relative (spec 04 §7.3):
  compare against the previous run and against grep, not against an invented threshold.

## Known limitations

- **Abstention is measured only in the extreme.** A case counts as abstained when the
  system returns nothing at all, which happens only when no query term appears in the
  corpus as written — the foothold gate roadmap 4.23 kept when it removed the rest of
  ADR-0048's precondition. A natural-language question about something the corpus does not
  cover still returns low-ranked noise, because retrieval has no confidence signal to
  abstain on (roadmap 3.11). G4 proves the system does not invent matches, and no more.
  All ten judged `unanswerable` cases are of the extreme kind, which is also why 4.23's
  reach for footholdless *queries* had no headroom to find
  ([ADR-0054](../docs/adr/0054-gate-the-query-not-the-documents.md)).
- **The dev/release split is not real yet.** Spec 04 §7.1 wants the release set frozen
  before any tuning; we gate on the same twenty cases we develop against, so G3 detects
  regression but not overfitting. Filed as roadmap 3.13 with the ≥ 60-case, two-corpus
  target spec §7.6 sets for this phase.
- **The judgments are not independent.** They were assigned by the same agent that wrote
  most of the documents being judged — useful for regression detection and for the grep
  comparison, not an independent benchmark.
- **Twenty cases is a seed.** Small sets move a lot on single-case changes; read
  differences of a few points as noise.
- **The `injection` slice is one case**, and it only checks that the doctrine is findable.
  Resistance itself is tested as a property against the injection corpus — twenty-three
  attack documents under `tests/fixtures/injection/`, asserted by `tests/test_injection.py`
  (roadmap 6.3, ADR-0119) — rather than scored here, because no ranking metric can say
  *returned verbatim*.
- **`synthesized` has no cases** — the synthesis lane arrives at 4.4.

## Gates evaluated here

Every gate spec 04 §7.3 names is accounted for. A table with silent omissions reads as
though the missing gates passed.

| Gate | Status |
|---|---|
| G1 Citations | **Enforced** — every returned anchor must resolve; must be 1.00 |
| G2 Earn hybrid | **Reported per set; the decision is enforced across corpora** (roadmap 4.40/4.41, ADR-0068/0069). Both of spec 04 §7.3's conditions are computed whenever the hybrid retriever runs, and the cases behind any tripped slice are **named**. The gate line itself does not fail, for two reasons: "ship lexical-only" is a legitimate outcome, so a boolean would be red on the shipped configuration; and one set cannot decide a default that is decided over every frozen release set — today `ours/release` clears both conditions while both `uv` release sets fail. The verdict is **committed** in [`g2-verdict.json`](g2-verdict.json) with the fingerprints that date it, and `python tools/measure_hybrid_gate.py --check` — run by `tools/verify.py` at `retrieval` and by CI — fails when the retrieval configuration, a vendored corpus or a judged set has moved since, or when the decision the release rows support disagrees with the shipped profile. Never because hybrid lost. Where the model is present it re-measures too, comparing *verdicts* rather than floats (ONNX is not promised identical across machines). Re-record with `--record`; the bare form still prints the full table and `--cases` still shows where a judged anchor sits in the lexical, vector and fused lists. **At these set sizes G2 cannot promote hybrid** — *What a −2 % slice bar means over four cases*, above, is why that is the sets' fault and not the bar's |
| G3 No regression | **Enforced against `baselines/<set>.json`** when the corpus *and the judgements* are the ones the baseline was taken on, and only on the slices that can carry it — no enforced slice may fall more than 2 %, and a slice that is `unanswerable`, blessed at 0.0000, or thinner than four cases is reported by name with the reason (ADR-0052). "The same corpus" means the same *documents*, not the same chunk boundaries, so a chunking change is gated rather than excused (roadmap 4.13, ADR-0045) and the verdict names the re-cut. "The same judgements" means the same cases with the same grades: a slice's score is a mean over its cases, so a set that grew reads as a regression unless the gate can tell the two apart (roadmap 4.24, ADR-0051). When either has changed the numbers are not comparable, so the gate *reports* the movement instead of failing on it — and calls it movement, not regression. `--bless` writes a baseline and records all three fingerprints |
| G4 Abstention | **Enforced** — false-answer rate on `unanswerable` ≤ 5 % |
| G5 Performance | **Enforced, with its limit stated** — query p95 ≤ 150 ms, reported with the corpus size it was measured on. The budget is defined at the 10⁵-chunk reference profile, so passing here is a floor rather than the measurement spec 04 §1 asks for |
| G6 Determinism | **Delegated** — a compiler gate with its own golden and its own CI job (ADR-0012) |
| G7 Grounding | Not applicable — it gates a *synthesized document's* promotion, and the synthesis lane arrives at 4.4 |

CI runs G1, G3, G4, G5 and G6 on every push (`eval / gates G1-G6`), reports the grep
baseline without gating on it, and runs the agent-task suite. **G2 is the exception, and the
job's name is still slightly generous**: hybrid needs a model CI does not fetch, so what CI
enforces is that G2's *committed* verdict still describes this product — not the measurement
itself, which is taken where the model is (ADR-0068, roadmap 4.40). Whether a runner should
pay for the model is argued in that ADR rather than assumed: the cost is small (127.6 MB,
12-25 s) and the reason it does not is comparability.

## The agent-task suite

There are two of them, for the reason there are two judged corpora (ADR-0053): *report* on
the corpus we author, *gate* on the one we do not.

- [`tasks.jsonl`](tasks.jsonl) — 22 tasks over this repository's own documentation, built
  by [`tools/build_agent_tasks.py`](../tools/build_agent_tasks.py).
- [`corpora/uv-docs/eval/tasks.jsonl`](corpora/uv-docs/eval/tasks.jsonl) — 22 tasks over
  `uv`'s documentation, built by
  [`tools/build_uv_docs_tasks.py`](../tools/build_uv_docs_tasks.py) and added at roadmap 6.23
  ([ADR-0135](../docs/adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md)),
  because the verdict spec 04 §7.4 arms at 1.0 cannot be read on a corpus whose documents
  its own authors edit every merge. `--check` refuses a hand edit, as it does for the judged
  sets ([BUG-0026](../docs/bugs/2026/09/BUG-0026-the-uv-judged-sets-do-not-reproduce-from-their-generator.md)).
- [`corpora/uv-docs-ingested/eval/tasks.jsonl`](corpora/uv-docs-ingested/eval/tasks.jsonl) —
  the same 22 tasks **carried** onto the ingested twin by
  [`tools/build_ingested_cases.py`](../tools/build_ingested_cases.py), never re-judged: only
  the anchor is recomputed, through the same coverage and `whole` floors the cases cross, with
  `tasks-carry.json` as the receipt. A task that loses any required anchor is dropped whole,
  because a task is scored on *every* required anchor arriving and a shorter `requires` list
  would be an easier task rather than the same one.

All three are built with the same discipline as the cases: judgments as data, every required
anchor validated against a real build, and `mycelium eval <corpus> --tasks --gate` failing in
CI and in the ladder when a required passage the snapshot no longer holds is named.

D-010's standard is not another retriever, it is the agent's own `grep`/`read` loop, so
each task runs through both. Because a model in the loop needs a key, a budget, and a
network — none of which belongs in an offline gate — what is measured is the *substrate*
each strategy hands a model: did the required evidence arrive, and what did it cost?

Measured at `fa6757d` on all three corpora (ADR-0135, and the
[report](../docs/benchmarks/2026-09-19-the-suite-on-a-corpus-we-did-not-write.md) it cites),
at the shipped 4 000-token budget:

| Corpus | mycelium | grep | median tokens, ours / theirs |
|---|---|---|---|
| `uv-docs` — not ours | **18 / 22** | 13 / 22 | 2 274 / 15 251 |
| `uv-docs-ingested` — not ours, projected | **17 / 22** | 11 / 22 | 2 479 / 15 173 |
| this repository | 16 / 22 | 15 / 22 | 2 697 / 15 130 |

Three measurements, not one: different documents, different questions, one instrument. The
third row is also the argument for the first two — it read +2 on 2026-09-18 and +1 one day
and three merges later, with no retrieval change in between.

Re-run at roadmap 6.8, after `[retrieval] symbol_lookup` went back off
([ADR-0137](../docs/adr/0137-let-a-gated-default-follow-its-ablation-and-narrow-the-rule-that-would-refuse-it.md)),
**every evidence count above is unchanged** — 18, 17 and 16 of 22 for us, 13, 11 and 15 for
grep — and only the per-task cost moves, by a couple of hundred tokens on our side. The table
stays pinned to `fa6757d` because a dated measurement is a record of what was run, not a
running total; re-take it with `python tools/measure_agent_task_band.py`.

**The incumbent's model has two numbers in it, and both are measured rather than asserted.**
A grep hit is a line number, so the loop *reads* — and one read costs at most what one search
may, because `budget_tokens` is what a caller will spend on one step of context-gathering and
a grep loop has no packing to spend it once. A document that fits is read whole; one that does
not is read around the hit; a section larger than the window is read and carries no evidence,
because seeing part of a passage is not being handed it. The loop opens `MAX_GREP_FILES` files.
`python tools/measure_agent_task_band.py <corpus>` runs the comparison across the band both
constants trace: each extra file the incumbent opens costs ~3 000-3 800 tokens and returns
~3 tasks, so at *equal cost* its first read brings back a handful of tasks against our
sixteen-to-eighteen, and at *comparable evidence* it pays 5.6-6.7× the context. The band also
shows what our own side cannot do: our evidence rate is flat from 4 000 tokens upward, because
`_mycelium_context` asks for ten hits whatever the budget says (roadmap 6.28).

Numbers from before 2026-09-18 are not comparable with these. ADR-0022's original 64 %/27 %
was read off a denominator with four unanswerable tasks in it (fixed at 6.4, ADR-0120), and
then off an incumbent that read one file on every task whatever its size (fixed at 6.22).

**What this cannot tell you:** whether the model then answers correctly. Evidence reaching
the context is necessary and not sufficient, and no number here should be quoted as a
task-success rate without that sentence attached (ADR-0022). The quantified gate with a
real agent arrives at 1.0, where spec 04 §7.4 puts it.
