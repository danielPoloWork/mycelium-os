# 2026-09-12 — the tour was the only thing it could see (roadmap 5.19)

- **Session scope:** roadmap 5.19 — make a symbol's `defined_in` name where the thing is
  *documented* rather than where it is *named*, deciding from the documents and touching no
  ranking code (spec 03 §§2, 6; spec 04 §§2-3, §7.1).
- **PR:** #118 (`feat/documenting-site`). Follows #117 (5.18), merged as `b606044`.
- **Milestone 5:** 5.19 done; 5.23 filed. 5.21 and 5.22 remain open.
- **ADR:** [ADR-0091](../../../adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md).

## The item's premise was half right, and the wrong half was the fixable one

5.9 filed this with a diagnosis — `defined_in` names a page that merely spells the name,
while ADR-0062 says a `symbol` judgment names the page that documents it — and three candidate
fixes: rank the sites by prose, reorder `doc_refs`, or add a second field. Read from the
documents, none of the three survives, and the first one loses in the *measured direction*.

The four sites uv has for `pyproject.toml`, once the extractor can see them all:

| site | tokens | mentions | judged |
|---|---:|---:|---|
| `concepts/projects/layout.md#the-pyproject-toml/0` | 106 | 2 | **grade 2** |
| `guides/projects.md#project-structure/pyproject-toml/0` | 247 | 4 | — |
| `guides/migration/pip-to-project.md#…/the-pyproject-toml/0` | 153 | 3 | — |
| `pip/dependencies.md#using-pyproject-toml/0` | 146 | 6 | — |

Most prose picks the second. Most mentions picks the fourth. The one a judge graded relevant is
the shortest and mentions the name least. Reordering `doc_refs` was inert twice over — before
this change every `sym:doc:` symbol on every corpus had exactly one `doc_ref`, and the symbol leg
re-ranks them by BM25 anyway — and a second field had nothing to put in it.

What *was* wrong is narrower and fixable. ADR-0073's rule reads a heading only when the heading
**is** the name, and in a documentation corpus the headings shaped that way are the entries of a
tour: four of uv's seven sit under *Working on projects ▸ Project structure*, three under
*Installing uv ▸ Installation methods*. The reference sections that explain the same files —
`## The pyproject.toml`, `## pylock.toml format`, `## uv.lock output` — were invisible. The
judged anchor of `u-0021` was not a site the table ranked badly; it was a site the table did not
hold.

## A bound measured rather than chosen

A heading now defines the name it is *about*: the name, or the name and one framing word. The
width is where the evidence stops. At two words the three corpora yield twelve, ten and zero new
headings and **not one non-name**. At three, the ingested twin yields `e.g`, out of a heading
that is a git URL with a parenthetical. At five it yields `x86_64` out of *"Transparent x86_64
emulation on aarch64"*, where the subject is the emulation. Two names in one heading means a list
or a sentence, so it yields nothing; per-word sentence punctuation is stripped first, or *"Learn
more about the core concepts in uv."* would have defined `uv.` on the twin, where the HTML
projection turns whole paragraphs into headings.

## The finding that settled the ordering question

I built the widening first and left `defined_in` on plain path order, to see what it would do.
It moved three records: `uv/pyproject.toml` onto the section a judge grades relevant, and
`uv/uv.lock` and `uv-ingested/pyproject.toml` onto a Renovate integration guide and a `uv pip`
dependencies page. **One right, two wrong, none of them aimed.** The same lever that fixes one
symbol breaks another, which is as clear a statement as the corpus can make that the ordering is
not where the truth lives.

So `defined_in` prefers a *direct* site — a fence definition, a definition-list term, or a
heading that is the name — with path order between equals. The widening then becomes strictly
additive: uv 14 → 23 symbols and 16 → 29 sites, the twin 12 → 19 and 12 → 23, ours unchanged at
3, and **no `defined_in` moves at all**. The whole delta lands in `doc_refs`, which is where it
belongs.

## What it buys, and what it does not

On `u-0021` the leg offered one site, judged irrelevant; it now offers four, one of which is the
case's grade-2 anchor, at lexical rank 9. The *result* does not move, because add-only cannot
promote a chunk the ranking already holds inside the top ten, and because the leg ships off.
That is worth saying plainly rather than rounding up: the table is more truthful and retrieval is
byte-identical, which is exactly what an extraction change with no ranking code in it should look
like. `retrieval_identity()` is unchanged, so gate G2 needed no re-record.

`u-1001` is unchanged and cannot be fixed from here. Its grade-3 anchor is
`concepts/indexes.md#defining-an-index` — a heading with no name in it. That is the general limit:
the documenting section frequently does not name the thing at all. `uv.lock` is documented by
`## The lockfile`.

## The thing that would actually unblock the slice, filed rather than built

Sixteen of the nineteen `symbol` case-instances ask for a multi-word command — `uv tool install`,
`uv lock --check`, `uv python pin`. Spec 04 §2's identifier test rejects all of them on whitespace
alone, so the planner never routes them; and uv heads the sections that document them *Installing
tools*, *Checking the lockfile*, *Exporting the lockfile*, never with the command. No heading rule
at any width touches this. What is missing is a *source*, not an ordering: a command is a name a
documentation corpus defines and spec 03 §2 has no language for one. Filed as 5.23, sized L,
because the identity rule, the extraction syntax and the planner's multi-word lookup are three
open questions and none of them is a `defined_in` question.

## Lesson

When an item arrives with a diagnosis and a menu of fixes, the menu is the previous session's
hypothesis and the diagnosis is its evidence — and they can come apart. Here the evidence was
sound (the table pointed at the wrong chunks) and every proposed remedy was aimed at ranking,
while the defect was in what the extractor could *see*. Measuring the remedies was what showed
it: a signal that is wrong in the measured direction is a much better finding than a signal that
merely fails to help.
