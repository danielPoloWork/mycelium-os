# ADR-0098: Declare the renderer, pin it to what the artifacts already say, and keep it out of the default sync

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 06 §3
- **Related:** [ADR-0039](0039-measure-what-projection-costs.md) (the twin, why its renderings
  are committed, and the measurement that they are not reproducible),
  [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md) (the re-render that made
  this hurt twice in three days), [ADR-0071](0071-advertise-the-types-and-check-the-tools.md)
  (the mypy override, and the note this amends),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) (pin what runs, never "best
  available"), [ADR-0056](0056-make-the-format-assignment-append-only.md) (why a rendering,
  once made, is never remade); D-013; roadmap 5.24, 5.27

## Context

`tools/build_ingested_corpus.py --render` compiles nine of the twin corpus's documents to PDF
through the `typst` package. That package is declared **nowhere** — not a dependency, not an
extra, not a dev group, not in `uv.lock` — and is named only inside an error message that says
`pip install typst`. So a routine `uv sync --all-extras --dev` removes it, and three sessions
in four days have had to reinstall it by hand before they could re-render.

`pyproject.toml` already carried a comment calling the absence deliberate: *"it is declared
nowhere … because it is a generator-only tool a maintainer installs by hand"*. That is a
description of the situation, not a defence of it. A provenance act that cannot be re-run
without out-of-band knowledge is not reproducible in the sense ADR-0039 requires of this
corpus, and "declared nowhere" also means **unversioned** — which matters here more than
usual, because typst is the thing that decides what the PDFs look like and therefore what
their text layer says.

Roadmap 5.27 offered three shapes — a generator-only dev extra, a documented install in
`docs/workflow/`, or a check that fails before the generator starts — and one note: typst
embeds a build identifier, so its *version* is part of what a PDF rendering is, and pinning it
is the half that protects reproducibility.

Two measurements settle most of it.

**The renderer costs 62.5 MB installed** — one wheel, no dependencies, a whole typesetter.
`uv sync --all-extras --dev` runs in eight places in the CI workflow, on every cell of a
three-platform matrix. CI never renders: rendering is a one-time provenance act, and the job
that touches this corpus runs `--check`, which re-ingests the *committed bytes* and needs
pandoc, docling and PDFium but not a typesetter.

**The version was never actually unrecorded.** Every committed PDF carries
`Creator: Typst 0.15.0` in its own metadata, written by typst as it compiled. The provenance
of these renderings has been in the artifacts all along, in the most trustworthy place it
could be — inside the thing it describes, where nothing can restamp it without recompiling.
The corpus knew what made it; the repository did not.

## Decision

**The renderer is declared and pinned exactly, in a dependency group of its own:**

```toml
[dependency-groups]
render = ["typst==0.15.0"]
```

**It stays out of the default sync, deliberately.** `uv sync --all-extras --dev` does not
install a non-default group, so it still *removes* typst — and that is the intended
behaviour, not a residual defect. Carrying 62.5 MB onto every cell of the matrix to serve an
act performed a handful of times per milestone is the trade D-013 exists to refuse, applied to
the development environment rather than the runtime closure. What changes is that the
repository now describes the package, `uv.lock` records its version and hashes, and putting it
back is one documented command instead of a bare `pip install`:

```bash
uv sync --group render
python tools/build_ingested_corpus.py --render
```

**The pin is read out of the corpus, not chosen.** `0.15.0` is what every committed PDF says
made it, and `tests/test_eval_ingested_corpus.py` asserts that the pin and the artifacts agree
— so bumping the pin without re-rendering, or re-rendering with a different typesetter without
bumping the pin, fails by name. The test reads the committed bytes with PDFium, which the
`ingest` extra already provides, so it runs everywhere including on machines and CI cells that
have no renderer at all.

**And the generator refuses before it writes anything.** `require_typst` runs once, ahead of
the loop, counting the PDFs the plan owes that disk does not have; if there are any and the
package is absent it exits naming the command. The import used to fail at the first PDF, after
pandoc had already produced several DOCX and HTML files — a half-finished provenance act plus
the wrong advice. When the renderer *is* present, `--render` prints the version it is using,
which is the operator's copy of the fact the artifacts record.

**What this does not claim.** It does not make the renderings reproducible. typst stamps a
creation timestamp into every PDF — measured at ADR-0039, and `SOURCE_DATE_EPOCH` does not fix
it — so the same markup still compiles to different bytes every time, which is exactly why
`sources/` is vendored. Roadmap 5.27's note that pinning "protects reproducibility" is
therefore half right and worth stating precisely: the pin fixes the **typesetter**, which
governs layout and the text layer a parser reads back, and it is the bytes that remain
unreproducible.

## Alternatives Considered

- **Put it in the `dev` group.** The obvious fix, and it would end the reinstalling for good:
  `uv sync --all-extras --dev` would keep it. Rejected on the measurement — 62.5 MB, eight
  sync sites, three platforms, for a package CI never executes. The `embeddings` and `ingest`
  extras are in `dev` for a stated reason that does not apply here: *"CI type-checks and
  exercises them on every platform"*. Nothing in CI exercises the renderer, and nothing should:
  a CI job that rendered would be writing provenance.
- **Make it an optional extra** (`mycelium-os[render]`). Rejected twice over: `uv sync
  --all-extras` installs every extra, so it has the dev group's cost with none of its honesty;
  and an extra is a *consumer-facing* promise about the installed package, while this is a
  tool for maintaining a fixture in this repository. Nobody installing `mycelium-os` should be
  offered a typesetter.
- **A documented one-line install and nothing else** — the second shape 5.27 named. Rejected
  as the whole answer: prose in `docs/workflow/` does not put a version in `uv.lock`, and the
  version is the part that decides what the PDFs are. It is kept as the *other* half — the
  command is documented in `eval/README.md`, beside the generator it belongs to.
- **Record the typst version in `provenance.json`.** Considered seriously, and rejected
  because it would be a fabrication today: the manifest describes renderings made earlier, and
  writing the currently-installed version into it would assert a fact this session cannot
  know. The artifacts already carry it per file, which is strictly better — a manifest field
  can drift from the bytes it describes and `Creator` cannot.
- **Vendor a `typst` binary, or shell out to a system `typst`.** Rejected: the Python package
  was chosen at ADR-0039 precisely because it is one install with no distribution behind it,
  and a second installation mechanism for one generator is more surface, not less.
- **Drop PDF from the rotation** so no renderer is needed. Rejected outright: a PDF loses its
  headings entirely, which makes it the format with the most to say about what projection
  costs (ADR-0039, and roadmap 5.26 measured that the `pdf` row is where every interesting
  case sits).

## Consequences

- **`uv sync --all-extras --dev` still removes typst**, and that is now documented in three
  places rather than discovered: `pyproject.toml`, the generator's docstring, and
  `eval/README.md`. A maintainer about to re-render runs one command first.
- **`uv.lock` gains `typst 0.15.0`** with its hashes. Nothing else in the lock moves, and the
  default sync's resolution is unchanged — the group is not part of it.
- **The pin cannot drift from the corpus.** A new test compares the declared version with the
  `Creator` of every committed PDF. Verified by mutation: changing the pin to `0.14.0` fails
  the test with the nine filenames and what they actually say.
- **The mypy override for `typst.*` stays**, and its comment now gives the real reason. The
  package ships `py.typed`, so a machine that has synced the render group type-checks it for
  real; CI has no renderer, so the override is what keeps `mypy --strict tools` green there.
  That asymmetry is deliberate now rather than an omission, which is the sentence ADR-0071
  asked for and could not yet write.
- **`--render` fails in the right place** — before pandoc writes the first file, with the
  command as the message. The old failure left a partially rendered `sources/` tree, which for
  a corpus whose inputs are committed provenance is worse than an error.
- **Filed rather than absorbed:** roadmap 5.34 — pandoc is the other half of this generator's
  toolchain and is *also* unversioned. The DOCX and HTML renderings carry their producer the
  way the PDFs do, so the same question has the same kind of answer available, and it was left
  out here because it is an OS-level binary rather than a Python package and the shapes
  differ.

## References

- Spec: `.draft-specs/06-roadmap-and-governance.md` §3 (deferred with explicit triggers).
- Decision log: D-013 (small closure, zero network by default).
- Measured this session: `typst` 0.15.0 is 62.5 MB across 11 files with no dependencies; every
  committed PDF reports `Creator: Typst 0.15.0`; `uv sync --all-extras --dev` removes it.
- Re-runnable: `uv sync --group render`, then `python tools/build_ingested_corpus.py --render`.
- [ADR-0039](0039-measure-what-projection-costs.md) (why the renderings are committed),
  [ADR-0071](0071-advertise-the-types-and-check-the-tools.md) (the note this amends).
