# 2026-08-31 — the interchange bundle (roadmap 3.6)

- **Session scope:** roadmap item 3.6 — `mycelium export`, the JSONL interchange bundle
  (spec 03 §9, D-006).
- **PR:** #36 (`feat/export-bundle`). Follows #35 (3.5), merged as `69b6da5`.
- **Milestone 3:** 3.1–3.6 done; 3.7–3.12 open.

## What the item actually was

Spec 03 §9 draws a small tree and states a one-sentence contract: *"One JSONL line = one
record exactly as specified above."* Read literally, that is a serialisation chore — iterate
the store, dump JSON, stop.

What makes it more is the consumer. A bundle leaves the repository and is read by a tool
that cannot ask it anything. Everything this repository knows implicitly — which snapshot
those rows belong to, whether the working tree still matches them, whether two exports are
comparable — is either *in* the bundle or gone. So the work went into three refusals:

- **It names one snapshot and contains that snapshot.** Export reads `CURRENT`, requires its
  manifest to exist, and requires the store's own pointer to agree. In ADR-0009's
  commit-to-swap window it refuses, because a directory stamped snapshot A holding snapshot
  B's rows is the quiet inconsistency this project avoids everywhere else — except here it
  would escape into someone else's tool.
- **Its bytes are a function of that snapshot.** Declared record order (documents by path,
  chunks by anchor, edges by identity), `canonical_json`, LF endings. Two exports of one
  snapshot are byte-identical, so a bundle can be digested, cached and diffed. The order is
  not arbitrary: it is the order the manifest folds its corpus digests by (ADR-0015), so a
  consumer comparing bundle against manifest compares like with like.
- **`--with-markdown` copies the sources that were compiled, or none.** Every file's digest
  is recomputed against the `content_digest` its record carries; drift fails the export and
  names the files. Copying whatever is on disk would produce records from snapshot A beside
  a working tree from B, with nothing in the bundle to reveal it.

## The smaller calls

- **`manifest.json` is copied byte for byte.** The spec says "verbatim", and copying is a
  stronger promise than re-emitting faithfully.
- **`symbols.jsonl` is written empty; `entities.jsonl` is omitted.** Symbols are a declared
  artifact class whose stage arrives at 5.1 — an empty file says "none in this snapshot",
  while a missing one asks the consumer to distinguish unsupported from empty. Entities are
  the opposite case: the spec marks them "if present" and the stage is optional, so absence
  is the signal.
- **`init` gitignores `export/`.** D-006 says bundles are "not committed by default", and a
  directory the tool writes into a repository *is* committed by default unless something
  says otherwise. That turned up a smaller thing worth fixing: `init` treated `.gitignore`
  as all-or-nothing, so a repository scaffolded before an entry existed would never gain it.
  Entries are now appended individually, which is what idempotent was supposed to mean.

## A tooling note worth carrying forward

Two heredocs failed today with `unexpected EOF while looking for matching quote`, and one
patch script silently matched nothing: backslash escapes written into a shell heredoc arrive
collapsed, so a Python literal `"a\nb"` becomes a real newline before Python ever parses it.
Long heredocs also fail outright. Both are avoidable the same way — write files in a few
smaller blocks, and build backslashes explicitly (`chr(92)`) when patching source that
contains them. Recorded here because it cost three retries, not because it is interesting.

## Where the project stands

- **3.6 complete** pending merge. Milestone 3 has 3.7–3.12 left, of which 3.9–3.12 were
  filed by 3.3.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (616 passed, 18 skipped), `python tools/consistency_lint.py`.
- **Gate G6 did not move, and that is the point**: export adds no stage, changes no digest,
  and needed no re-bless. It is a pure reader of a published snapshot.
- Exercised as the real binary in a real terminal: `init` → `build` → `export
  --with-markdown` produced the spec's tree with CJK text intact, and editing a source
  afterwards made the next `--with-markdown` export refuse by name.

## How the next session resumes

- Wait for PR #36 to merge, then **3.7** (eval slices + CI gates G1–G6, agent-task suite v0)
  — the item that finally wires the gates into CI. Two things are waiting for it:
  [BUG-0007](../../../bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md) (G4 fails
  at 25 % because the eval corpus includes test fixtures) and roadmap 3.10, which is the
  decision that fixes it. Wiring a gate that is known-red without fixing the corpus first
  would just teach everyone to ignore it.
- The bundle is now a plausible input for the agent-task suite: a task can be scored against
  an exported corpus without a live store.
