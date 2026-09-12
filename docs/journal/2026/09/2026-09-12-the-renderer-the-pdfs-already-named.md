# 2026-09-12 — the renderer the PDFs already named (roadmap 5.27)

- **Session scope:** roadmap 5.27 — decide how the PDF renderer should be declared, after
  three sessions in four days had to install it by hand before they could re-render.
- **PR:** #125 (`build/declare-the-pdf-renderer`). Follows #124, merged as `5d2ad38`.
- **Milestone 5:** 5.27 done. 5.34 filed.
- **ADR:** [ADR-0098](../../../adr/0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md).

## The item's own note was half wrong, and checking it first changed the answer

5.27 said to note while deciding that *"typst embeds a build identifier, so its version is
part of what a PDF rendering is and pinning it is the half that actually protects
reproducibility."* Two things about that sentence are worth separating before choosing a shape.

Pinning protects nothing about reproducibility. typst stamps a creation timestamp into every
PDF; ADR-0039 measured that and measured that `SOURCE_DATE_EPOCH` does not fix it, which is
the whole reason `sources/` is vendored rather than rebuilt. The same markup compiles to
different bytes under the *same* pinned version. What a pin fixes is the typesetter — layout,
and therefore what a parser reads back out of the text layer — and that is worth having for
its own sake, stated as itself.

And the version was never unrecorded. One command settles it:

```
Creator: Typst 0.15.0
```

Every committed PDF says that, written by typst as it compiled, alongside a per-file creation
timestamp of 2026-09-12 14:14 — this morning's re-render. The provenance has been in the
artifacts the whole time, in the best place it could be: inside the thing it describes, where
nothing can restamp it without recompiling. The corpus knew what made it. The repository did
not.

That reframes the item. There is no missing record to invent, so the job is to make the
repository agree with a fact the corpus already holds.

## One measurement picks the shape

typst is **62.5 MB** installed — a whole typesetter in one wheel, no dependencies.
`uv sync --all-extras --dev` appears in eight places in the CI workflow, across three
platforms, and **nothing in CI renders**: the job that touches this corpus runs `--check`,
which re-ingests the committed bytes and needs pandoc, docling and PDFium but no typesetter.

So the `dev` group is out. The two extras that *are* in `dev` are there for a stated reason —
*"CI type-checks and exercises them on every platform"* — and it does not apply to a package
CI never executes. An extra is out twice over: `uv sync --all-extras` installs every extra, so
it carries the dev group's cost, and an extra is a promise to whoever installs `mycelium-os`.
Nobody installing a knowledge compiler should be offered a typesetter.

What is left is a dependency group of its own, which `uv sync --all-extras --dev` does not
install:

```toml
[dependency-groups]
render = ["typst==0.15.0"]
```

The routine sync therefore still *removes* it — I watched it do so, `- typst==0.15.0` — and
that is now the designed behaviour rather than the complaint. What changed is that the
repository describes the package, `uv.lock` records its version and hashes, and putting it
back is `uv sync --group render` instead of a bare `pip install` remembered from an error
message.

## Two things make it hold rather than merely be written down

The pin is read out of the corpus, and a test says so: it compares the declared version
against the `Creator` of every committed PDF. Bump the pin without re-rendering, or re-render
with a different typesetter and forget the pin, and it fails with the filenames and what they
actually say. Verified by mutation — `0.14.0` fails, `0.15.0` passes — and it reads the bytes
with PDFium, which the ingest extra already provides, so it runs on CI cells that have no
renderer at all.

And `--render` now refuses in the right place. The import used to sit inside the per-document
PDF branch, so it failed at the first PDF, after pandoc had already written several DOCX and
HTML files — a half-finished provenance act plus `pip install typst`, which was the wrong
advice even before this change. `require_typst` runs once before the loop, counts the PDFs the
plan owes that disk does not have, and exits naming the command. When the renderer is present
it prints the version it is using, which is the operator's copy of the fact the artifacts keep.

## What was refused

Recording the typst version in `provenance.json` looked obvious and is a fabrication. That
manifest describes renderings made earlier; writing today's installed version into it would
assert something this session cannot know. The artifacts carry the fact per file already, and
a manifest field can drift from the bytes it describes in a way `Creator` cannot.

## Found on the way

pandoc (5.34) is the other half of the same toolchain and is unversioned in exactly the way
typst was: an OS-level binary, installed by a CI action and by whatever a contributor's package
manager does, recorded nowhere. It is the reader whose *dialect* destroyed a fifth of this
corpus's structure for four milestones (ADR-0095), so which pandoc made these renderings is
the same class of fact. Left out of this item because the shapes differ for a binary, and
filed with the first thing to check: whether the committed DOCX and HTML carry a producer
string the way the PDFs do, in which case the answer is a test rather than a declaration.

## Lesson

The item asked how to declare a missing fact, and the fact was not missing — it was in the
artifacts, one `get_metadata_value` away, and forty minutes of choosing between dependency
shapes would have gone differently if I had read a PDF first. The generalisable half: when a
provenance question is about a tool, ask what the tool already wrote into its output before
designing a place to write it down. Producers stamp themselves; a manifest field that
duplicates that can only ever drift from it.
