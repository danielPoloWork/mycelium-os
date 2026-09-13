# ADR-0105: pandoc gets a floor, not a pin, because nothing it writes can be checked

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0098](0098-declare-the-renderer-pin-it-to-what-the-artifacts-say.md) (the
  typst precedent this diverges from, and why), [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md)
  (why *which* pandoc dialect reads this corpus is load-bearing), [ADR-0039](0039-measure-what-projection-costs.md)
  (why the renderings are vendored rather than reproduced); D-013; roadmap 5.24, 5.27, 5.34

## Context

`tools/build_ingested_corpus.py` renders the second corpus's 81 Markdown documents into DOCX,
HTML and PDF. PDF goes through typst, declared, pinned and version-checked against every
committed file since roadmap 5.27 (ADR-0098). DOCX and HTML go through pandoc, an OS-level
binary the repository has never recorded a version for anywhere — filed at 5.27 and
deliberately left out of it, because the two renderers were expected to need different
answers, "the same class of fact as which typst did."

They do not get the same answer, and checking why settles the question. A typst PDF stamps
`Creator: Typst <version>` into itself, which is what lets `tests/test_eval_ingested_corpus.py`
compare the declared pin against every committed file and fail if a re-render used something
else. Read directly against every committed `sources/*.docx` and `*.html` in this corpus:
neither carries anything of the kind. Every DOCX's `docProps/app.xml` says
`Application: Microsoft Word 12.0.0` — a string pandoc's writer hard-codes, unrelated to which
pandoc wrote it — and its `core.xml` has empty creator and title fields. The HTML is a bare
fragment: `_pandoc()` never passes `--standalone`, so there is no `<head>`, no `<meta>`, nothing
a producer tag could live in. `grep -ri pandoc` over every committed source returns nothing.

The "good news" the item hoped for — that the same test-the-artifact trick might already work
— does not apply. There is nothing in the committed bytes this project could check a later
pandoc's output against, the way it checks a later typst's.

One thing was already done, and predates this item without anyone noticing the overlap:
`.github/actions/setup-pandoc` has pinned pandoc to a verified release archive since PR #78
(2026-09-07), five days before roadmap 5.27 was even filed. That pin governs what CI's
ingest-parser tests run against — the `PandocParser` in `mycelium.ingest.parsers.pandoc`, which
reads arbitrary pandoc-parseable formats through its own `--sandbox`ed subprocess call and
already floors its acceptable major version at 3 (`--sandbox` arrived in pandoc 3). It says
nothing about which pandoc rendered the DOCX and HTML sitting in `sources/` today, because
`build_ingested_corpus.py --check` never re-renders them — it ingests the committed bytes with
docling, the same as it always has, and pandoc plays no part in reading this corpus back.

## Decision

**pandoc gets a floor in the generator's own preflight, not a pin, and the difference is
stated rather than papered over.** `require_pandoc()` mirrors `require_typst()`'s placement —
called once before the render loop writes anything, refusing with a clear message rather than
letting the first old-pandoc failure land mid-loop as a raw subprocess error — but it can only
check what pandoc reports about itself (`pandoc --version`), never what it produced. The floor
is the one fact about pandoc this project has already measured and needed anyway:
`--sandbox`, which `_pandoc()` always passes, requires pandoc 3. That constant
(`mycelium.ingest.parsers.pandoc.MIN_MAJOR`) is made public and imported rather than
duplicated, so the ingest-time floor and the generator-time floor are one number.

**Recording a version in `provenance.json` is refused, for the opposite reason ADR-0098 refused
it for typst.** There, the artifact already carries the fact, so a second copy could only
drift from a truth that exists; here, no artifact carries it, so a copy in `provenance.json`
would be the *only* copy, unverifiable and unrefreshable the moment the file it describes is
touched by anything else. A field nothing can check against is worse than no field: it reads
as a guarantee and is a guess.

**CI's existing pin is left where it is and not extended to mean something it does not.** It
is a true fact about what CI's parser tests exercise, stated plainly in the generator's
docstring so a reader does not conflate "pandoc is pinned in this repository" with "pandoc
rendered these files" — they are different claims about different pandocs, possibly on
different machines, months apart.

## Alternatives Considered

- **Coerce pandoc into writing a producer string** — pass `--standalone` for HTML (which would
  add a `<head>` a `--metadata generator:` could populate) and a reference-docx with custom
  properties set for DOCX. Rejected: it is real engineering for a fact this project would then
  have invented a place to put, when the honest problem is that nothing recoverable exists
  today for the files already committed — retrofitting a mechanism does not retrofit the
  provenance of the corpus that already shipped.
- **Pin an exact version and refuse anything else**, matching typst's shape literally.
  Rejected: without an artifact fact to verify against, an exact pin is unfalsifiable — nothing
  can ever tell a maintainer whether the pin still describes what rendered `sources/`, so it
  would assert precision the project cannot back up.
- **Record the version in `docs/workflow/`** as a documented recommendation with no
  enforcement. Considered seriously, and folded into the docstring instead of a new file: this
  repository has no `docs/workflow/` page for the ingestion toolchain today, and a floor
  enforced in code is a stronger statement than a paragraph a re-render could ignore.
- **Do nothing, since D-013 already says an OS binary is outside the runtime closure.**
  Rejected: D-013 is about what this project depends on to *run*, not about whether a
  provenance-sensitive generator should fail clearly or obscurely when its external tool is
  too old. The floor costs one function and protects the same failure mode `require_typst`
  already protects against.

## Consequences

- `require_pandoc()` refuses before any byte is written when pandoc is absent or reports a
  major version below 3, naming the install command, the same shape `require_typst` uses.
- `mycelium.ingest.parsers.pandoc.MIN_MAJOR` is now public; the ingest parser and the generator
  share one floor rather than two numbers that could drift apart.
- The generator's docstring states, checked and cited, that no committed DOCX or HTML carries
  a pandoc identifier — a claim a future reader can re-verify with one `grep`, not folklore.
- No new field on `provenance.json`, no new file under `docs/workflow/`. The floor is the whole
  fix; a full re-render remains what ADR-0039 already made it — a deliberate, rare provenance
  act with its own per-format cost table, not something this ADR tries to make routine or
  perfectly reproducible.
- The three shapes roadmap 5.34 offered to weigh are all, in the end, answered: the setup
  action was already pinning CI's pandoc (found, not built), a new docs/workflow/ record was
  weighed and declined as weaker than code, and the floor is what shipped.

## References

- Spec 02 §5 (ingestion, the evidence lane); D-013 (zero network / small closure, and what it
  does and does not cover).
- `tools/build_ingested_corpus.py` (`require_pandoc`, `require_typst`); `.github/actions/setup-pandoc/action.yml`.
- `src/mycelium/ingest/parsers/pandoc.py` (`MIN_MAJOR`, `_probe`) — the floor's origin.
- Tests: `tests/test_eval_ingested_corpus.py` (the no-identifier claim, the refusal messages,
  the zero-pending no-op).
