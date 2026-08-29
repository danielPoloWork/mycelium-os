# 2026-08-30 — build orchestrator v0 (roadmap 2.7)

- **Session scope:** roadmap item 2.7 — build orchestrator v0 (sequential) + snapshot
  manifest + atomic `CURRENT` swap + single-writer lock. The milestone's sets-pattern
  item: what is fixed here binds 3.1, 3.2, 3.5, and the serving layer.
- **PR:** #20 (`feat/build-orchestrator-v0`), one item, one PR. Follows #19 (2.6), merged.

## What got done

- `src/mycelium/build/` — `lock.py` (O_EXCL creation, pid+host+heartbeat, 10-minute stale
  takeover that collapses racing takeovers into one create race), `publish.py` (atomic
  writes, immutable manifests that refuse overwrite, `CURRENT` swap, diagnostic journal),
  `orchestrator.py` (discover → pin → parse → chunk → store → manifest → publish).
- Publication order fixed forever: one transaction wraps the store rewrite, the manifest
  file is written *before* anything names it, `meta[current_snapshot]` commits atomically
  with the data, and the `CURRENT` swap is the cross-process publish instant.
- **Identity pinning**: the spec contradicts itself — spec 02 §2 "the build never writes
  tiers 1–2" vs spec 03 §3 "`mycelium_id` written once by `mycelium build`". Resolved in
  the ownership table's favor (ADR-0009), because the alternative kills determinism: an
  unpinned doc mints a fresh ULID every build. The write is textual insertion preserving
  every other byte (CRLF kept, BOM kept), and `BuildResult.pinned` lists touched files.
- Patterns: **Snapshot** → Implemented (seeded as Planned at intake).
- Tests: 295 passing (+24). Benchmark: 30-document full rebuild ≈ 519 ms — the number the
  incremental DAG (3.1) has to beat on single-document edits.

## What the tests caught

- **`os.open` without `O_BINARY` lets the Windows CRT rewrite LF as CRLF** — the manifest
  files were platform-dependent bytes until the LF-only assertion failed on this machine.
  The flag is now part of the publication contract. This is exactly the class of bug the
  Windows CI cell exists for; it was caught locally first only because this session runs
  on Windows.
- `Path.read_text` applies universal-newline translation, which would have made pinning
  silently convert CRLF files; reads and writes go through `open(newline="")`.

## The honest crash window

Between COMMIT and the `CURRENT` swap there are microseconds where the store is complete
and self-consistent while the `CURRENT` file still names the previous snapshot — whose
data the v0 wipe replaced. With one mutable store this cannot be closed, only stated:
ADR-0009 documents it, `mycelium doctor` (2.8) gets the detector
(`meta[current_snapshot]` vs `CURRENT`), and the machinery that closes it is
platform-phase. Writing `CURRENT` before COMMIT was rejected because it inverts the
failure into a strictly worse one — a pointer to data that never committed.

## Where the project stands

- Milestone 2: 2.1–2.7 ✅ · 2.8–2.13 open. `build(root)` compiles a repository into a
  published, queryable snapshot end to end.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (295 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #20 to merge, then start **2.8** — the CLI skeleton (typer):
  `init/build/search/show/doctor` with `--json`, exit codes 0/1/2, no prompts in non-TTY,
  `NO_COLOR` honored (spec 05 §2). It is a thin shell over what now exists: `build()`,
  `SqliteStore.search_chunks`, `read_current`/`read_manifest`. New runtime dependency:
  typer. `mycelium doctor` should check lock liveness, schema version, and the
  `meta`-vs-`CURRENT` disagreement above.
- First builds modify the repository (pin ids) — the CLI must surface `BuildResult.pinned`
  as "commit these files".
