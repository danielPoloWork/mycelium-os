# ADR-0162: Hold a defect pin with a test, and verify the ranges a wheel resolves

- **Status:** Accepted
- **Date:** 2026-10-07
- **Deciders:** the maintainer (danielPoloWork), on the architecture review board's finding
- **Related:** [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md) (grammar versions in the build key), [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md), [ADR-0116](0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md) (the distribution check; amended here), [ADR-0059](0059-make-the-plan-one-implementation-too.md); [BUG-0022](../bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md), [BUG-0025](../bugs/2026/09/BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md); threat model B14; roadmap 5.2, 8.2; issue #207; [analysis 0002](../analysis/0002-architecture-review-board-v1-readiness.md) (clusters security-c4, security-c45)

## Context

BUG-0022 (2026-09-10) pinned the grammar binding to `tree-sitter>=0.25,<0.26`: 0.26.0 faults
with an access violation on a 20 644-byte fence of the ingested corpus, and a fault in native
code is not an exception — the build process dies, with no warning, no quarantine record and
its lock left behind. The record named that corpus as the regression guard, because
`tools/verify.py` builds it from `retrieval` mode upward, and declined to commit the fence
itself: a bisection stopped at 14 268 bytes, and "the vendored corpus is a better guard than a
checked-in copy of part of it."

Three things happened next, and nothing failed at any of them:

- **2026-09-12 — the guard stopped carrying the trigger.** #122 re-rendered the ingested twin
  in the dialect its sources are written in (BUG-0025, ADR-0095). The faulting document became
  `config-pdf-2839f69e.md`, with no fence in it. The record that relied on the document was not
  part of that change, and nothing asserted that the corpus still reproduced anything.
- **2026-09-13 — a bot widened the pin.** Dependabot's grouped PR #128 changed both
  specifiers to `<0.27` and merged without a review or a comment. `uv.lock` kept 0.25.2 by
  resolver inertia, so every job still ran the release that works. Nothing could see the
  change: every workflow installs from the lock; `tools/verify.py` classifies `pyproject.toml`
  and `uv.lock` as `code`, a mode that stops before any corpus is built; and
  `tools/check_distribution.py` installed the wheel with no extras.
- **2026-09-23 — v0.6.0 shipped the widened range.** `uv pip compile --extra symbols` resolves
  `tree-sitter==0.26.0`, the latest release on the index, so what a consumer of
  `mycelium-os[symbols]` installs is the binding BUG-0022 says kills the build, while the
  comment beside the pin, BUG-0022 and threat-model B14 all still said `<0.26`.

The architecture review board confirmed it at P1, release-blocking (analysis 0002, issue
#207). Its challenger's two findings are the decision's shape: *nothing records lifting the
pin*, and *no gate can see the change class that lifts it*. In the same file the board found
the `ingest` extra shipping `anthropic>=1.2` under a comment calling it a dev dependency — a
line misplaced at roadmap 4.4, so every `[ingest]` install received an SDK only the synthesis
lane uses.

Measured for this record, on the fence recovered from commit `db84cc5` through the compiler's
own parser: on Windows 11, 0.26.0 faulted 4 times in 10 with one read per fresh process and 10
times in 10 with five; 0.25.2 read it every time, identically. No Linux or macOS machine was
available to measure; CI's distribution job runs on Linux.

## Decision

**A defect pin is held by a test, its input is committed and replayed out of process, and the
distribution check verifies the published ranges at their newest versions as well as the
lock.**

1. **The pin is restored** to `>=0.25,<0.26` in the `symbols` extra and the dev group, and
   the lock re-resolved — metadata only; it holds 0.25.2 as before.
2. **One table names every input known to have faulted a native dependency**:
   `tools/check_known_faults.py`'s `KNOWN_FAULTS`, a row per bug record carrying the
   distribution, the releases observed to fault, the input, its size and its SHA-256.
3. **A test holds the ceiling.** `tests/test_symbols.py` reads every requirement
   `pyproject.toml` declares — core, every extra, every dependency group — the way an installer
   does (`packaging`, PEP 440), and fails when a range admits a release a row names. A comment
   cannot fail; a test can, and a bot's PR is a PR like any other.
4. **The input is committed, byte for byte**, as `tests/fixtures/symbols/bug-0022-fence.txt`:
   binary in `.gitattributes`, its digest asserted, its MIT notice beside it. This reverses
   BUG-0022's choice for the reason the re-render proved: a corpus is a guard only while it
   contains the input, and a regenerated corpus owes nothing to a record that relies on it.
5. **The input is replayed in a child interpreter**, five reads in one process, and judged by
   how the child exits — the only way a fault that kills a process can be observed. Two
   callers: the suite replays it in the locked environment, in every cell of the matrix; the
   distribution check replays it in a clean environment at the newest releases the ranges
   allow.
6. **The distribution check gains a fifth check.** The built wheel is installed with every
   extra at `--resolution highest` into a clean environment, which must load every grammar,
   replay every known fault and build the determinism corpus twice to one observation. It
   prints which direct requirements resolved past the lock, and whether the corpus still
   compiles to the golden at those versions — **reported, not gated**.
7. **Dependabot ignores the binding from 0.26.** The bot stops proposing what the test would
   refuse. Lifting the pin is a person's act: widen the range, run
   `python tools/check_distribution.py`, and if the newest allowed release reads every known
   input, narrow or retire the row, the ignore and the pin together and amend BUG-0022.
8. **`anthropic` leaves the `ingest` extra** for the dev group, where its comment always said it
   belonged. The synthesis lane is installed with `mycelium-os[synthesis]`, as the docs and the
   provider's own error message already say.

## Alternatives Considered

- **The Dependabot ignore alone.** Rejected: it binds the bot and nobody else, and it is
  configuration a person widens as easily as the bot widened the pin. The test is the control;
  the ignore removes the noise.
- **An exact pin, `==0.25.2`.** Rejected: the defect is a release, not the 0.25 line, and an
  exact pin refuses the line's own fixes and makes the extra harder to co-install. A consumer's
  resolver deserves the widest range that is known to work.
- **Exclude the release, `!=0.26.0`, instead of a ceiling.** Not yet: only 0.26.0 was tested,
  and nothing says a later 0.26.x without an upstream fix does not fault. The test is written in
  terms of releases admitted, so a future `!=0.26.0,<0.27` passes it the day someone proves
  0.26.1 against the replay.
- **Restore the corpus guard by planting the old document back.** Rejected: the twin is
  regenerated from its sources (ADR-0095), and a document kept only to preserve a trigger would
  be the corpus misreporting what it was compiled from.
- **Gate the golden at the newest versions.** Rejected: it is blessed against the lock, and a
  newer allowed release may compile the corpus differently with nothing wrong — the build key
  names the grammar versions for exactly that reason (ADR-0073). Gating it would fail a commit
  for a release somebody else made. The difference is printed, so it is seen.
- **Replay at the newest versions on every platform.** Rejected for cost: the distribution job
  asks a packaging question on one platform (ADR-0116). The residual is recorded below.

## Consequences

- **The change class that lifted the pin is now seen by the ladder.** A change to
  `pyproject.toml` or `uv.lock` derives `code`, which runs the suite — the ceiling test and the
  locked replay — and `tools/check_distribution.py`, which now resolves the published ranges.
  The CI `distribution` job and the publish workflow run the same tool, so a release cannot be
  uploaded while its extras, as resolved on the day, kill the build on a known input.
- **A new upstream release can turn the distribution job red on an unrelated pull request.**
  That is the moment a consumer would be hit, and the remedy is a range narrowed in a pull
  request of its own. The check costs a second clean environment — about eighty-five packages
  at the time of writing — and needs the network, as check 4 already does. Measured on the
  maintainer's Windows machine: 56 s for the check and about a minute more deleting the
  environment; the whole tool took 178 s, against the 64 s ADR-0116 recorded at roadmap 6.11.
  The environment is created in the system's temporary directory, beside uv's cache, because
  with the checkout on another drive uv copied every file instead of linking it and the
  install alone took 234 s.
- **At today's newest versions the corpus compiles to the golden.** The first run resolved six
  direct requirements past the lock — `anthropic`, `docling-slim`, `numpy`, `onnxruntime`,
  `pypdfium2`, `tokenizers` — and the determinism corpus still built to the committed
  observation; tree-sitter stayed at 0.25.2, its ceiling.
- **Residual, by platform.** The fault is observed on Windows. The ceiling test is
  platform-independent, so 0.26.0 is refused everywhere; a *new* faulting release is caught by
  the newest-version replay only where that replay runs and the fault reproduces — Linux in CI —
  and otherwise only once a lock resolves it and a Windows cell of the matrix replays it.
  Threat-model B14 is amended to say so.
- **`mycelium-os[ingest]` no longer installs the Anthropic SDK** — a change to a published extra,
  recorded in the CHANGELOG. Nobody's documented install changes: the synthesis lane has always
  been documented as `[synthesis]`.
- **BUG-0022 stays `confirmed`**: the defect is upstream and unfixed. Its record is amended to
  say what guards it now. The board's evidence for #207 attributes the re-render to BUG-0024
  and ADR-0093; it was #122, BUG-0025 and ADR-0095.

## References

- BUG-0022 (reproduction and diagnosis); BUG-0025 and ADR-0095 (the re-render).
- Dependabot PR #128 (`f690e18`); issue #207; analysis 0002 §3 (security-c4, security-c45).
- `tools/check_known_faults.py`, `tools/check_distribution.py` (check 5),
  `tests/test_symbols.py`, `tests/fixtures/symbols/README.md`, `.github/dependabot.yml`.
