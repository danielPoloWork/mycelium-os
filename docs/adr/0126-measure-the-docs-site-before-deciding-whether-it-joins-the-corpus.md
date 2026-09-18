# ADR-0126: Measure the docs site before deciding whether it joins the corpus

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent)
- **Related:** [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md)
  (the precedent this measurement follows, and the argument it does not transfer),
  [ADR-0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md)
  (the provisional exclusion this item was filed to resolve, and the design that
  makes `docs-site/` a link page rather than a restatement),
  [ADR-0125](0125-exclude-the-root-changelog-because-unreleased-is-the-restatement-early.md)
  (the other side of this same corpus-scope discipline); RFC-0001; spec 04 §7;
  spec 05 §2; roadmap 6.2, 6.13

## Context

Roadmap 6.2 built the docs site and excluded `docs-site/` from this repository's own
corpus provisionally, filing the decision as its own item rather than making it a side
effect of the PR that first wrote the content — the same discipline ADR-0072 used for
`docs/changelog` and `docs/releases`. What that item left open was named precisely:
`docs-site/`'s content is *not* a restatement in the sense ADR-0072 measured — the
tutorial, how-tos and plugin-author guide are genuine task-oriented content that exists
nowhere else in the repository — so the argument that excluded those two directories
does not apply here, and the honest default may be to include it. Three questions were
open: what indexing it moves on `ours/dev` and `ours/release`; whether the generated
API-reference prose creates the duplicate-vocabulary effect ADR-0072 measured; and
whether `mkdocs.yml`'s own nav/config content needs its own exclusion even if the pages
are included.

**The second question dissolved on inspection.** `docs-site/reference/sdk.md` is twenty
lines of `mkdocstrings` `:::` directives — `::: mycelium.sdk.types`, `::: mycelium.sdk.identity`,
and two more. The prose those directives expand into exists only in the built HTML
site (`site/`, gitignored, produced by `mkdocs build`), never in the Markdown source
this repository's compiler reads. There is no generated API-reference prose in the
corpus to create a duplicate-vocabulary effect with, because there is no generated
prose in the tree at all.

**The third dissolved the same way, for a different reason.** `mycelium.corpus.discover`
walks `settings.scope_of(root).rglob("*.md")` — only Markdown files are ever candidates
for inclusion. `mkdocs.yml` is YAML; no `[project] exclude` entry can keep out a file
type the discovery walk never looks at, and none is needed.

**The first question needed measurement, not inspection**, which is what this ADR
records.

## Measurement

The real repository, staged the way `tools/build_eval_cases.py`'s `stage_corpus` and
`tools/verify.py`'s `build` step both do — `mycelium build . --no-pin` against the
working tree, `[project] exclude` deciding the corpus exactly as it does in CI — run
twice: once with `docs-site` excluded (the provisional state), once with it removed
from `exclude`. Both builds were taken with the maintainer's own untracked working-tree
files (`fable-review.md`, `docs/analysis/`, an edit to `docs/README.md`) set aside first
and restored after, per the standing rule that a corpus measurement describes the tree
that will actually ship, not whatever happens to be open in an editor
(see the *bless the tree you are about to commit* discipline this repository already
follows for release baselines). `docs/dev.jsonl` (20 cases) and `eval/release.jsonl`
(19 cases) were scored against both builds, `mycelium` and `grep`, at `--against grep`:

| set | corpus | documents | ours nDCG@10 | ours recall@50 | grep nDCG@10 | grep recall@50 |
|---|---|---:|---:|---:|---:|---:|
| dev | excluded | 198 | 0.4739 | 0.8958 | 0.2275 | 0.8125 |
| dev | included | 206 | 0.4739 | 0.8750 | 0.2246 | 0.8125 |
| release | excluded | 198 | 0.5008 | 0.8235 | 0.2303 | 0.5588 |
| release | included | 206 | 0.5081 | 0.8235 | 0.2303 | 0.5588 |

**Nothing like ADR-0072's finding.** That measurement found the incumbent's score fall
by nearly a fifth (0.349 → 0.2998 on dev) while ours held still — the signature of a
term-counting retriever drowning in restated vocabulary. Here grep's release score is
*bit-identical* before and after, and its dev score moves by 0.0029, noise at this
sample size. Our own release score moves up, not down, and the one dev-side loss
(recall@50, one case) is fully accounted for below. This is the shape the item
predicted: genuine new content competes for rank the way any real document does,
rather than diluting a term-counting baseline the way a restatement does.

**What moved, case by case.** Only two judged cases changed at all:

- `q-0014` (dev, *relationship*: *"which ADR supersedes the cross-language source
  layout"*) lost one of its three judged anchors from the top 50 — `nDCG@10` for the
  case is unchanged, because that anchor was never in the top 10 either way. This is
  the one real, if modest, instance of the effect the item was watching for.
- `r-0006` (release, *conceptual/relationship*: *"why does a rollback rewrite data
  instead of just moving a pointer"*) dropped from `nDCG@10` 0.574 to 0.337: the how-to
  page `docs-site/how-to/roll-back-a-snapshot.md` describes the same mechanism in
  overlapping operational vocabulary (*"repoints `CURRENT`"*, *"a fact about the
  compiled output"*) and now out-competes part of the ADR's own rank for a query phrased
  as *why*, not *how*. This is real dilution, on one case, and it is named here rather
  than folded into an aggregate that reads only as a net gain.
- Four more release cases moved by ±0.03–0.37 nDCG in both directions
  (`r-0004`, `r-0008`, `r-0010`, `r-0017`); `r-0010` alone improved from 0.631 to 1.000.
  These track a corpus-wide term-statistics shift from 198 to 206 documents — BM25's
  IDF terms move for every query when the document count changes, whether or not the
  new documents mention the query's terms — and are not attributable to `docs-site`'s
  content specifically.

No CI gate's disposition changes: G1, G4, G5, G6 are untouched, and G2 (the hybrid
gate) does not gate `ours` on content drift by design — `tools/measure_hybrid_gate.py`'s
`DATED_CORPORA` excludes it for the reason its own docstring gives, *"every pull
request moves it… a check that failed on it would demand a re-measurement of gate G2
for a typo in a README."* G3 reports `ours/release` against a frozen baseline and does
not enforce on it (ADR-0053); the baseline is re-blessed as part of this change,
exactly as a corpus-moving PR always re-blesses it.

## Decision

**`docs-site/` joins the corpus.** The `docs-site` entry leaves `[project] exclude` in
`mycelium.toml`. The measurement confirms rather than merely asserts the item's own
prediction: this is genuine content, not a restatement, and including it does not
reproduce ADR-0072's incumbent-dilution pattern — grep's release score is unchanged
bit-for-bit and its dev score moves within noise, while ours moves up on release and is
flat on dev net of one case. The one real, named case of dilution (`r-0006`) is a
single judged case moving within its own slice, not a systemic effect, and is the kind
of rank perturbation any new, topically adjacent document can cause — the discipline
this repository applies is measuring it and naming it, not achieving zero perturbation.

**The baseline is re-blessed, both arms, as part of this PR** — `eval/baselines/release.json`
now reflects a 206-document `ours` corpus, matching the numbers in the table above. No
other artifact moves: `docs-site/`'s own fixture corpus for the determinism gate (G6) is
a separate, hand-built tree under `tests/fixtures/determinism/` with its own
`mycelium.toml`, untouched by this change.

## Alternatives Considered

- **Leave the exclusion in place, on the principle that a docs-site page and its
  source material inevitably overlap in vocabulary.** Rejected: the measurement shows
  the overlap is real but small and mostly favorable, which is a different finding
  from "this is a restatement" — conflating the two is exactly the mistake ADR-0072's
  own alternatives section warned against ("exclude only the offender… a distinction
  without a principle" — here the risk runs the other way, excluding on a principle the
  numbers do not support).
- **Include only the `how-to/` and `tutorial.md` pages, excluding `project.md` and
  `reference/`.** Considered and rejected as unnecessary complexity: `project.md` is
  almost entirely external links with one sentence each, contributing negligible
  vocabulary, and `reference/sdk.md` contributes twenty lines of directive syntax with
  no prose at all. A file-by-file split would trade a clean, principled boundary
  (the whole site is new content) for a fussier one that the measurement gives no
  reason to draw.
- **Exclude `docs-site/how-to/roll-back-a-snapshot.md` alone**, on the strength of the
  one case it measurably affects. Rejected: one case moving one slice by one grade of
  rank is not the corpus-contamination pattern this discipline exists to catch, and
  carving out a single page because it happens to compete with one ADR on one query
  is exactly the "fit the corpus to the case" move D-010 (*fix the product, not the
  benchmark*) refuses in the retrieval direction and this ADR refuses in the corpus
  direction.
- **Decide the mkdocs.yml question by adding it to `exclude` anyway, for clarity.**
  Rejected: `exclude` patterns are matched against Markdown-only candidates
  (`corpus.py`'s `discover` never globs anything else), so an entry for a `.yml` file
  would be dead code — a claim the config makes that nothing in the compiler can act
  on. The dissolution is recorded in `mycelium.toml`'s own comment instead.

## Consequences

- **The corpus grows from 198 to 206 documents** (the eight pages under `docs-site/`,
  net of the two set-aside maintainer files that are not part of this PR).
  `eval/baselines/release.json` moves with it, both arms; `eval/g2-verdict.json` does
  not, because `ours` is reported rather than gated there by design (ADR-0053's
  distinction, restated in `DATED_CORPORA`'s own docstring).
- **A precedent for the next new documentation directory**: the test is not "does this
  overlap in vocabulary with something else in the repository" — nearly everything
  does, a little — but "is this a restatement of a canonical source in the same
  vocabulary" (ADR-0072's question) measured against what actually moves on both sides
  of the comparison, ours and the incumbent's.
- **One dev-set case (`q-0014`) and one release-set case (`r-0006`) are on record as
  measurably affected**, named rather than smoothed into an aggregate, so a future
  session re-measuring this corpus is not surprised by either.
- **Nothing about retrieval changed.** No ranking code, config default, or gate
  threshold moved; only the corpus scope and the baseline it is measured against.

## References

- `mycelium.toml`'s own comment, next to `[project] exclude`, records the decision in
  the place a reader checking corpus scope will look first.
- Re-runnable: `mycelium build . --no-pin`, then
  `mycelium eval . --set eval/dev.jsonl --against grep --json` and the same for
  `eval/release.jsonl` — set aside any untracked working-tree Markdown first, the same
  discipline a release-baseline bless already follows.
- [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md) — the corpus
  exclusion this measurement follows the shape of, and diverges from in outcome.
- [ADR-0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md)
  — filed this item, and the design (link out, do not duplicate) that is most of why
  the outcome differs from ADR-0072's.
