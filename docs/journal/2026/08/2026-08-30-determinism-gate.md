# 2026-08-30 — determinism gate G6 (roadmap 2.10)

- **Session scope:** roadmap item 2.10 — determinism golden test wired into CI (gate G6,
  spec 04 §7).
- **PR:** #23 (`feat/determinism-gate`), one item, one PR. Follows #22 (2.9), merged.

## What got done

- `tests/fixtures/determinism/` — a six-document corpus with pinned identities, covering
  all three chunk kinds, all three verification statuses, both trust classes, nested and
  duplicate-slug headings, a section past the token ceiling, and CJK/accented content.
- `src/mycelium/determinism.py` — the observation the gate compares, shared by the test and
  the re-bless tool so a golden can never be produced by different code than the code that
  checks it.
- `tools/update_determinism_golden.py` — re-bless an intended compiler change; prints that
  the diff belongs in the PR.
- `.github/workflows/ci.yml` — a `determinism / gate G6` job, plus the same tests running
  inside the build matrix on all three operating systems.
- ADR-0012; 382 tests passing (+12).

## What promoting a test to a gate actually required

The assertion existed already (2.7 compares `artifact_digests` across two builds). Making
it a gate forced three decisions:

- **Saying what "identical" covers.** A manifest holds `snapshot_id` (a fresh ULID by
  design), `created_at` (the wall clock) and `timings_ms` (a measurement of the machine).
  No correct build reproduces those. The observation omits them — and a test asserts they
  *do* vary, so the exclusion stays honest rather than convenient.
- **Pinning mtime, because mtime is an input.** ADR-0009 made the file's mtime the
  document's `created_at`. A fresh checkout has fresh mtimes, so an unpinned golden would
  encode the moment the repo was cloned.
- **Making the golden readable.** Per-chunk anchors, digests, heading paths, line spans —
  so an intended change produces a diff a reviewer can judge. A single hash would reduce
  every review to "re-bless it", which is how gates become decoration.

## Two things the work itself caught

- **My own observation was inconsistent.** The readable `documents` section omitted
  timestamps while `artifact_digests["documents"]` covered them — so a timestamp
  regression would have surfaced as an unexplained digest mismatch with an identical
  documents section. Found by the mtime test failing for the "wrong" reason. The
  observation now records the pinned timestamps, and the golden shows them.
- **`.gitattributes` was required, not optional.** `core.autocrlf` is on by default on
  Windows *and* on GitHub's Windows runners, so a fresh clone would have rewritten the
  corpus and the golden — and the golden asserts its own bytes. Without pinning
  `text eol=lf`, the gate would have failed on a perfectly correct tree.

The gate is also proven to fail: two mutation tests change the corpus and assert the
observation moves away from the golden. A gate nobody has watched fail is a gate nobody
should trust.

## Where the project stands

- Milestone 2: 2.1–2.10 ✅ · 2.11–2.14 open. G6 is green and enforced; the compiler's
  central claim is now checked by CI on three operating systems rather than asserted.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (382 passed), `pytest -m determinism`, `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #23 to merge, then start **2.11** — the eval harness v0 plus the first 20
  judged cases over Mycelium OS's own docs (spec 04 §7), route standard/medium. It is the
  last functional item of the milestone, and D-010 sets the bar: the baseline to beat is
  the agent's built-in grep, not another retriever.
- The eval-case record already exists (`mycelium/eval-case/v0`, spec 03 §10) but has no
  pydantic model yet — 2.11 adds it. Run manifests live under `.mycelium/eval/`.
- The determinism corpus is a ready-made judged-case source if a second corpus is wanted,
  but the item says Mycelium OS's own docs, which are richer and more honest.
