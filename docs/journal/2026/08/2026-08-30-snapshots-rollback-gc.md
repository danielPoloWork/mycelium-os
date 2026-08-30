# 2026-08-30 — restorable snapshots (roadmap 3.2)

- **Session scope:** roadmap item 3.2 — `mycelium snapshots` / `rollback` / `gc`
  (spec 02 §4.3, spec 05 §1).
- **PR:** #32 (`feat/snapshots-rollback-gc`), one item, one PR. Follows #31 (3.1), merged
  as `ce0e7aa`.
- **Size revised S → M**, for the reason below. Recorded in the roadmap entry rather than
  quietly absorbed.

## The decision this item turned on

Spec 02 §4.3 defines rollback in one sentence: *"repoints `CURRENT`; nothing rebuilds"*.
That is a one-line command — **if the store is versioned**. Ours is not, deliberately
(D-019 defers versioned storage to the platform phase), so the rows in `store.db` always
belong to the newest build. Repointing alone would leave `CURRENT` naming snapshot A while
the data is snapshot B: exactly the disagreement `mycelium doctor` has reported as
corruption since 2.8, and every citation resolved against the served snapshot would answer
from the wrong corpus. Silently.

So the honest implementation of *"nothing rebuilds"* is **restore, then repoint** — and
3.1 had already put everything needed in place. Chunk artifacts were in the CAS; the
`Document` record's digest was already the address it would have in the CAS
(`cas_put(canonical_json(record))` returns exactly `digest_json(record.model_dump())` —
one address, two uses), so storing it cost a write and no new concept. What was missing
was a record of *which* artifacts a snapshot consisted of.

That record is one content-addressed blob per publication holding the build's whole
`doc_state` table — a **Memento**. One blob and one row per snapshot, not one row per
document per snapshot: publication stays O(changed) in writes, and a rebuild that changed
nothing re-addresses the identical blob and writes nothing at all (tested).

The same record solves garbage collection's quieter problem. A content-addressed store can
only collect what nothing reaches, and until now nothing recorded what a snapshot reached —
so either the cache pinned every blob forever (collect nothing) or the sweep had to guess.
Now: a blob is garbage exactly when no retained snapshot's state names it and no retained
cache row points at it.

## What got done

- `src/mycelium/build/snapshots.py` — `list_snapshots`, `rollback`, `collect_garbage`, and
  the state Memento's encode/decode.
- Store schema **v2**: `snapshot_state` (snapshot → CAS pointer), plus `clear_documents`,
  `cache_entries`, `delete_cache_entries`, `snapshot_states`, `put/get/delete_snapshot_state`
  on the protocol. The v1 → v2 upgrade needs no operator action: 3.1's writer-side rebuild
  policy handles it.
- Rollback runs under ADR-0009's exact publication order — lock, load *and revalidate*
  everything first, replace in one transaction, commit, then swap `CURRENT` — so an
  interrupted rollback leaves `CURRENT` untouched. It also restores `doc_state`, which is
  what makes the *next* build correct: it diffs against what is actually in the store.
- **The integrity gate:** before committing, the recorded state is folded with ADR-0015's
  own construction and required to reproduce the manifest's published `artifact_digests`.
  A successful restore is therefore *proof* that the store now holds the snapshot the
  manifest describes — not merely something plausible found in the cache.
- Publication now tells the truth about restorability: two stats per live document, and a
  snapshot whose artifacts are not all present publishes and serves normally but is marked
  `degraded: ["snapshot_state"]` with a warning naming `mycelium build --clean`.
- CLI: `mycelium snapshots [--json]`, `mycelium rollback <id> [--json]`,
  `mycelium gc [--keep N] [--cache-max-age DAYS] [--dry-run] [--json]`.
- **ADR-0016**; **Memento** joins the patterns catalogue and the **Snapshot** row is
  refined (the pointer swap alone cannot roll back on a single mutable store).

## The honest limits, stated in the ADR rather than implied

- **Rollback is not O(1).** It rewrites the catalog and the lexical index and revalidates
  every artifact on the way in. 200 documents / 1 800 chunks: **4.0 s**, against a
  **15.2 s** clean rebuild — 3.8× faster and it needs no sources, but not a pointer swap.
  Making it O(1) needs the versioned store (D-019). The committed benchmark tracks the
  same comparison at 30 documents: 229 ms vs 500 ms.
- **Publication grew a small fixed cost** — no-op build ~452 ms → ~473 ms at 200
  documents; single-edit ~546 ms → ~573 ms. The < 2 s budget is untouched.
- **`--cache-max-age` is not a convenience dial.** Without it the build cache pins every
  blob it ever wrote and the sweep can never collect anything. `build_cache.created_at`,
  which 3.1 recorded for exactly this moment, is what it cuts on.

## What the tests caught while being written

- `CURRENT` must be retained by `gc` *whatever* the retention — including `--keep 0`, and
  including when it is not the newest snapshot, which is precisely the state a rollback
  leaves behind. Collecting the served snapshot would leave the repository pointing at a
  manifest that no longer exists.
- An assertion of mine, not a product bug: `search_chunks("Added after the first
  snapshot")` still matched surviving documents, because BUG-0005's fix makes FTS terms
  OR-joined. A phrase is not a filter here; the test now uses one distinctive term per
  side.
- The G6 golden did **not** need re-blessing, and that is the evidence that matters:
  restorability changes what is stored *beside* a snapshot, not what the compiler
  produces.

## Where the project stands

- **3.2 complete** pending merge. Milestone 3: 3.1 and 3.2 done; 3.3–3.8 open.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (476 passed + 27 new snapshot tests + 6 new CLI tests), benchmarks run,
  `python tools/consistency_lint.py` passes.

## How the next session resumes

- Wait for PR #32 to merge, then **3.3** — the local ONNX embedder, vectors keyed
  `(chunk_digest, model_id)`, and hybrid RRF. It is the first *declared non-deterministic*
  stage (spec 02 §4.1), so it lands in the DAG as one: a stage version, a config slice
  (`[embedding]`, already digested), and an `EmbeddingInfo` block in the manifest that has
  been `None` since 2.7. The `vectors` table has keyed on `(chunk_digest, model_id)` since
  2.6 precisely so unchanged text never re-embeds and switching models adds rows instead
  of destroying them (D-013).
- Note for 3.3: vectors are *not* part of the snapshot state blob yet. If they should be
  restorable alongside documents and chunks, that is a decision to take in 3.3's ADR —
  ADR-0016's live set would need to name them too.
