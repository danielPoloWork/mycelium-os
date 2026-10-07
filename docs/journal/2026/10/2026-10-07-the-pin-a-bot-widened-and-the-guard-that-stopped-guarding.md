# 2026-10-07 — the pin a bot widened, and the guard that stopped guarding (roadmap 8.2)

- **Session scope:** roadmap 8.2 (issue #207, release-blocking) — first in the release order
  the maintainer accepted on 2026-10-07: the tree-sitter pin, then the `ours/release` re-bless,
  then the v0.7.0 cut.
- **PR:** `fix/restore-the-tree-sitter-pin`, from `981c365` (#236).
- **Milestone 8:** 8.2 closed by this PR.
- **Decision it records:**
  [ADR-0162](../../../adr/0162-hold-a-defect-pin-with-a-test-and-verify-the-ranges-a-wheel-resolves.md),
  amending ADR-0116's distribution check.

## Four dates, and nothing failed at any of them

BUG-0022 pinned `tree-sitter<0.26` on 2026-09-10 and named the ingested corpus as its guard. On
2026-09-12 #122 re-rendered that corpus (BUG-0025) and the faulting document left it. On
2026-09-13 Dependabot #128 widened the pin to `<0.27`; the lock kept 0.25.2, so every job still
ran the release that works. On 2026-09-23 v0.6.0 shipped the widened range, whose `[symbols]`
resolves 0.26.0. Each step was correct on its own terms, and each one removed a reason the next
would have been caught: the guard needed the corpus, the ladder needed the guard, and the lock
hid the range from every environment the project verifies.

## What the fix measured

- **The fault, recovered.** The fence came back out of `db84cc5` through the compiler's own
  parser — 20 644 bytes, the size BUG-0022 recorded. On Windows 11, 0.26.0 died on it in 4 fresh
  processes of 10 with one read each, and in 10 of 10 with five reads each; 0.25.2 read it every
  time, identically. The replay therefore reads five times per child.
- **The test can fail.** Widening the pin back to `<0.27` fails
  `test_no_declared_range_admits_a_release_known_to_fault` with the record's own message, and
  the replay tool pointed at a 0.26.0 environment reports the access violation and the fault
  handler's first line, three runs of three.
- **The fifth distribution check, on this machine:** 56 s, plus about a minute of Windows
  deleting the environment; the tool as a whole took 178 s, against the 64 s recorded at 6.11.
  Its first version built the environment under `build/`, on another drive than uv's cache, and
  the install alone took 234 s because uv copied every file; in the temporary directory uv
  links them and it takes about 40. Six direct requirements resolved past the lock
  (`anthropic`, `docling-slim`, `numpy`, `onnxruntime`, `pypdfium2`, `tokenizers`), tree-sitter
  stayed at its ceiling, the fence read five times on 0.25.2, and the determinism corpus built
  twice to an observation that matches the committed golden: at today's newest versions, a
  consumer compiles what gate G6 verifies.

## What the next session should know

- **Next is the `ours/release` re-bless** as its own pull request (`docs/workflow/release.md`
  step 0), from a clean worktree with the maintainer's untracked files set aside, blessed twice
  (the second with `--retriever grep`); then the v0.7.0 cut.
- **The distribution job now depends on the index on the day.** A new upstream release that
  stops a grammar loading, crashes on a known input or breaks determinism turns it red on
  whatever pull request runs next. That is the moment a consumer would be hit; the remedy is a
  range narrowed in a pull request of its own, never a skipped check.
- **The board's evidence for #207 misattributes the re-render** to BUG-0024 and ADR-0093; it was
  #122, BUG-0025 and ADR-0095. Recorded in ADR-0162 and BUG-0022.
- **Linux was not measured.** The fault is observed on Windows; whether 0.26.0 faults on the
  fence under Linux, where the newest-version replay runs in CI, is unknown. The range test
  refuses 0.26.0 on every platform regardless.
- **`mycelium-os[ingest]` no longer installs `anthropic`**; it moved to the dev group, where its
  comment always placed it.
