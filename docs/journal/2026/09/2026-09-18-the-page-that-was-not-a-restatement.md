# 2026-09-18 — the page that was not a restatement (roadmap 6.13)

- **Session scope:** roadmap 6.13 — decide whether `docs-site/` joins this repository's
  own corpus, a decision 6.2 filed rather than made.
- **PR:** `feat/docs-site-corpus-decision`, following the M6 work through #160.
- **Decision it records:** [ADR-0126](../../../adr/0126-measure-the-docs-site-before-deciding-whether-it-joins-the-corpus.md).

## Two questions that dissolved before a build ran

The item named three open things. Two turned out not to need measurement at all.

`docs-site/reference/sdk.md` — the page a duplicate-vocabulary worry would have been
about — is twenty lines of `mkdocstrings` `:::` directives. The prose those expand into
lives only in the built HTML site, which is gitignored; the tracked Markdown carries no
generated API-reference text at all. There was nothing to measure a duplication effect
against, because the thing that would duplicate does not exist in the corpus's own
input.

And `mkdocs.yml`'s nav and plugin configuration can never enter the corpus regardless of
what `[project] exclude` says, because `mycelium.corpus.discover` globs `*.md` only. A
`.yml` file is not a candidate for inclusion in the first place. Reading `corpus.py`
settled this one; no build needed.

## The one question that needed a build, twice

What indexing the eight new pages moves on `ours/dev` and `ours/release` could only be
measured, not inferred from the pages' shape. `mycelium build . --no-pin`, once with
`docs-site` excluded and once with it removed from `exclude`, both against `eval/dev.jsonl`
and `eval/release.jsonl` with `--against grep`.

Before either build, the maintainer's own untracked work had to come out of the tree:
`fable-review.md` at the repository root and `docs/analysis/` are both `.md` files
`discover()` would have picked up, and `docs/README.md` carried an uncommitted edit.
The first build (done before I noticed this) came back with 209 documents; setting the
three aside and rebuilding came back with 206 — the three files were quietly inside the
corpus I was about to measure and bless. This is the same trap `bless-the-tree-you-are-
about-to-commit` names for a release baseline, and it applies exactly as much to a
one-off corpus measurement: a scope decision is a claim about the tree that will ship,
not about whatever else happens to be open in an editor.

## What the real measurement found

The opposite of ADR-0072. That ADR found grep's own score fall by six percentage points
while ours held still — a term-counting retriever drowning in restated vocabulary. Here
grep's release score does not move at all, bit for bit; its dev score moves by 0.0029,
which is noise. Ours moves *up* on release (0.5008 → 0.5081) and is flat on dev net of
one case. Two judged cases actually moved: one dev case lost a judged anchor from the
top 50 with its top-10 score unaffected, and one release case — a *why*-question about
rollback — now competes with the how-to page that describes the same mechanism in
operational vocabulary, a real, single-case effect that is named in the ADR rather than
smoothed into the aggregate that reads as a net win.

## Decision and what it moved

`docs-site` leaves `[project] exclude`. `eval/baselines/release.json` is re-blessed,
both arms, to the 206-document corpus. Nothing else moves: `eval/g2-verdict.json` does
not gate `ours` on content drift by design (`DATED_CORPORA` excludes it, for the reason
its own docstring gives — "every pull request moves it"), and gate G6's fixture corpus
is a separate hand-built tree under `tests/fixtures/determinism/` with its own
`mycelium.toml`, untouched by a change to the root one.

## Lesson

A corpus-scope decision is not "does this content overlap in vocabulary with something
else" — nearly everything does, a little. It is "does including it reproduce the
specific pattern the exclusion precedent measured" — a term-counting incumbent losing
ground to restated prose. Here it did not, and the honest way to know that was to run
the same comparison ADR-0072 ran and read the same table, not to reason from the
pages' genre.
