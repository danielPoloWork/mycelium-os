# ADR-0012: State what determinism claims, and gate it with a reviewable golden

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7
- **Related:** [ADR-0009](0009-adopt-build-publication-semantics.md) (mtime becomes
  `created_at`), [ADR-0007](0007-adopt-structure-first-chunking.md) (chunk boundaries must
  be reproducible); spec 04 §7 (gate table); D-008; roadmap 2.10

## Context

D-008 makes deterministic, content-addressed compilation *the* technical differentiator:
build keys are meaningful only if identical inputs produce identical outputs, and a cached
artifact is trustworthy only for the same reason. Spec 04 §7 turns that into gate **G6**,
"byte-identical rebuild check (compiler gate, runs with eval in CI)".

The claim already had a unit test — 2.7's `test_second_build_pins_nothing_and_changes_no_bytes`
compares `artifact_digests` across two builds. Promoting it to a *gate* needs three things
that assertion does not provide, and each is a decision:

1. **A statement of what "identical" covers.** A snapshot manifest contains
   `snapshot_id` (a fresh ULID by design), `created_at` (the wall clock) and `timings_ms`
   (a measurement of the machine). No correct build reproduces those. A gate demanding
   they match would assert something false, be suppressed, and become decoration.
2. **A corpus worth compiling.** A gate over a trivial document proves almost nothing.
3. **An artifact a reviewer can read** when output legitimately changes — otherwise
   "re-bless the hash" is indistinguishable from "silence the gate".

## Decision

**Gate the observation, not the manifest.** `mycelium.determinism.observe_build` records
what compilation actually determines — `artifact_digests`, `counts`, `config_digest`,
`schema_versions`, `warnings`, and every document and chunk record — and deliberately omits
`snapshot_id`, `created_at`, `timings_ms`, and `parent_id`. The exclusions are not
convenience: a test asserts those fields *do* vary between two correct builds, so if they
ever stopped varying the exclusion would be dead weight worth removing.

**Pin mtime, because mtime is an input.** ADR-0009 made the source file's mtime the
document record's `created_at`/`updated_at`. A fresh checkout has fresh mtimes, so an
unpinned golden would encode the moment the repository was cloned rather than the content
it holds. The observation pins every fixture to 2026-01-01T00:00:00Z, and records the
resulting timestamps in the readable section — so a timestamp regression shows up as a
timestamp, not as an unexplained digest mismatch.

**The golden is a document, not a hash.** It carries per-document and per-chunk detail —
anchors, digests, heading paths, kinds, token counts, line spans — sorted, LF, non-ASCII
unescaped. A compiler change produces a diff a reviewer can actually read: *this anchor
moved, that chunk split differently*. Re-blessing is `python
tools/update_determinism_golden.py`, and the tool prints that the diff belongs in the PR.

**The corpus is part of the contract.** Six fixture documents cover the profile the gate
exists to protect: all three chunk kinds, all three verification statuses, both trust
classes, nested and duplicate-slug headings, a section past the token ceiling that must
split at a paragraph boundary, and CJK/accented content (D-028). A separate test asserts
that coverage, so the gate cannot be quietly weakened by simplifying the fixtures.

**The gate is proven to fail.** Two mutation tests change the corpus and assert the
observation moves away from the golden. A gate nobody has watched fail is a gate nobody
should trust.

**Line endings are pinned in `.gitattributes`.** Git's `autocrlf` — on by default on
Windows and on GitHub's Windows runners — would rewrite the corpus and the golden on
checkout, failing the gate on a correct tree. The fixtures and the golden are `text eol=lf`.

**CI runs it twice, on purpose.** The determinism tests run inside the build matrix on
Linux, macOS, and Windows, which is where cross-platform reproducibility is actually
proven; a dedicated `determinism / gate G6` job runs `pytest -m determinism` so the gate is
legible by name in the checks list instead of buried in a suite of 380.

## Alternatives Considered

- **Compare whole manifests byte for byte** — the most literal reading of "byte-identical
  rebuild". Rejected: it is false for `snapshot_id`, `created_at` and `timings_ms`, so it
  would have to be relaxed immediately, and a gate with a suppression list teaches that
  gate failures are negotiable.
- **A single digest of everything** — smallest possible golden. Rejected: a failure would
  say "expected `sha256:a…` got `sha256:b…`", which tells a reviewer nothing about whether
  the change is correct. The golden's job is to make an intended change reviewable.
- **Generate the corpus in the test** instead of committing fixtures. Rejected: generated
  corpora drift with the generator, and a committed corpus is diffable, editable, and
  usable as documentation of what the compiler handles.
- **Leave mtimes free and exclude timestamps from the digest** — no pinning needed.
  Rejected: it would weaken `artifact_digests["documents"]`, which should cover the whole
  record; the honest fix is to pin the input, not to shrink the claim.
- **Golden per platform** (one for Linux, one for Windows). Rejected as an admission of
  defeat: cross-platform reproducibility is a property worth having, and one golden
  checked on three operating systems is what enforces it. Per-platform goldens would hide
  exactly the divergence the gate exists to catch.
- **Run only in the dedicated job**, not in the matrix. Rejected: the dedicated job runs on
  Linux alone, and the interesting failures (line endings, path separators, locale) are
  the ones that appear elsewhere.

## Consequences

- Any change to the compiler that alters output fails CI until the golden is re-blessed in
  the same PR. That is the intent: compiler changes become visible and reviewed.
- The golden is ~1 400 lines of JSON. Large for a fixture, small for the evidence behind
  the product's central claim, and diffable line by line.
- The corpus is also, in practice, the project's most complete worked example of the
  Markdown profile — a second use that makes keeping it rich worthwhile.
- `mycelium.determinism` ships in the package rather than living in `tests/`, so the gate
  and the re-bless tool share one implementation and a golden can never be produced by
  different code than the code that checks it.
- G6 is now green and enforced; G1–G5 and G7 arrive with the evaluation harness (2.11,
  3.7) and the grounding work (4.5).
- When the incremental DAG lands (3.1), this gate is what proves the cache did not change
  the answer — it was written to be inherited, not rewritten.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7 (gate table, G6) ·
  `.draft-specs/02-architecture.md` §4 (the stage DAG and build keys)
- Decision log: D-008 (content-addressed incremental build), D-028 (multilingual corpus)
- [ADR-0009](0009-adopt-build-publication-semantics.md) — why mtime is an input
