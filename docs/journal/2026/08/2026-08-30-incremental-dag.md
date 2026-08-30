# 2026-08-30 — the incremental compiler (roadmap 3.1)

- **Session scope:** roadmap item 3.1 — content-addressed incremental DAG + build cache +
  dirty detection (D-008, the product's technical differentiator; spec 02 §4).
- **PR:** #31 (`feat/incremental-dag`), one item, one PR. Follows the v0.2.0 cut (#28) and
  the release-artifact fix (#30), both merged; `v0.2.0` is tagged and drafted.
- **Milestone 3 opens.** New PRs carry milestone M3.

## What got done

- `src/mycelium/build/dag.py` — build keys exactly as spec 02 §4.1 fixes them
  (`stage_id, impl_version, input_digests, config_slice, schema_version` through canonical
  JSON), per-stage implementation versions with the bump discipline in the docstring, the
  build-environment fingerprint, and the CAS artifact envelopes (encode/decode with
  revalidation).
- `src/mycelium/build/cas.py` — `.mycelium/cas/<xx>/<sha256>`: canonical-JSON blobs named
  by `digest_bytes` of their content (the spec's tier-1 custody rule, so milestone 4's
  ingestion reuses this module). Every read re-hashes; a blob that does not match its own
  name is deleted and reported as a miss.
- Store schema **v1**: new `doc_state` table (per-document source digest, mtime, env
  digest, artifact digests, warnings; cascades from `documents`), plus
  `cache_get`/`cache_put`/`doc_states`/`put_doc_state` on the protocol. A **writer** that
  meets a foreign-version store now recreates it in place (D-016's rebuild policy,
  journaled as `store.recreated`); a reader refuses exactly as before.
- The orchestrator runs the spec 02 §4.2 algorithm: plan (read + pin + digest every file),
  duplicate resolution over the whole plan, digest-based dirty detection against
  `doc_state`, cache-aware parse/chunk with assemble always recomputed, delete-then-insert
  publication inside the one ADR-0009 transaction, and manifest corpus digests folded from
  per-document digests in path order. `BuildStats` (reused/rebuilt/removed, stage runs vs
  hits) is returned, printed, JSON-emitted, and journaled.
- `mycelium build --clean` — recompute everything, consult nothing, publish the same bytes.
- **ADR-0015**; patterns **Pipeline** and **Content-Addressed Cache** flip to Implemented.

## The judgment calls

**Dirty detection reads every file, every build.** The mtime fast path (make, ninja) was
rejected *for this item*: renames preserve mtimes, our own pinned-mtime fixtures defeat it
entirely, and a false "clean" silently serves stale artifacts — the one failure a
determinism product cannot afford. mtime therefore only ever *adds* dirtiness (it is the
assemble stage's input, ADR-0009); content truth comes from the digest. The floor this
buys is ~2 ms/document on the Windows dev machine (I/O-bound: per-file open/stat, not
hashing), which is what 3.5's event-driven watch mode exists to remove.

**Manifest digests changed construction — the golden re-bless is two lines.**
`artifact_digests.documents`/`.chunks` now fold path-ordered per-document digests instead
of digesting the whole record set (O(corpus) work in the O(changed) path). Every document
and chunk record in the golden is byte-identical; `edges` did not move (an empty list
digests the same both ways). Spec 03 §7 requires class digests without fixing their
construction; ADR-0015 now fixes it.

**Assemble is never cached.** It is arithmetic over cached inputs, and its distinguishing
input — mtime — is the one that most often changes alone. Caching it would trade a
dict-build for a CAS round-trip and a third invalidation axis.

**The 2.6 refusal message was a latent deadlock.** "Rebuild with `mycelium build`" was the
version-mismatch message, but the build path raised the same refusal. Bumping the schema
for `doc_state` forced the fix: the writer *is* the rebuild. First attempt deleted the
database file — **Windows refused** (`WinError 32`) because a concurrent reader held it
open, which is exactly the D-015 coexistence case. The recreate is now in-place `DROP` of
every object, identical on all platforms.

## What the equality suite caught while being written

- A test helper that rewrote files wholesale silently dropped the pinned `mycelium_id` —
  the "single edit" was really an identity swap (remove + add). Real editors keep
  frontmatter; the fixtures are now pre-pinned and edits preserve the pin. Identity churn
  is a scenario tests opt into, not an accident.
- `---\n[unclosed\n---` is **not** broken frontmatter — the first line is no mapping key,
  so the block is a thematic break and parses fine. Genuinely-declared-and-broken is
  `mycelium_id: not-a-valid-ulid`, which raises because identity is never guessed.
- `st_mtime + 100` carries sub-microsecond float bits that `datetime` truncates — an
  over-precise assertion, not a product bug. Integral timestamps in tests.

## Numbers (200-document corpus, Windows dev machine)

| Build | Wall time |
|---|---|
| Cold (first) | 12.9 s |
| No-op incremental | 452 ms |
| Single-edit incremental | 546 ms |
| Clean rebuild of 30 docs (bench) | ~626 ms vs ~325 ms single-edit |

The single-edit marginal cost is ~46 ms of compile plus the plan floor. Throttling the
per-file lock heartbeat (`os.utime` every file → every 64th) halved the floor by itself:
875 ms → 406 ms of plan at 200 documents.

## Where the project stands

- **3.1 complete** pending merge; spec coverage §4 (logical architecture) is ✅.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (443 passed + 20 new incremental tests + 12 determinism), benchmarks run,
  `python tools/consistency_lint.py` passes.

## How the next session resumes

- Wait for PR #31 to merge, then **3.2** (`mycelium snapshots` / `rollback` / `gc`) —
  the counterpart this item made urgent: builds are cheap now, so snapshot manifests and
  CAS blobs accumulate; `build_cache.created_at` exists for 3.2's retention window.
- 3.3 (local ONNX embedder + hybrid RRF) slots into the DAG as a declared
  non-deterministic stage keyed on `(chunk_digest, model_id)` — the vectors table and the
  embedding manifest field are already in place.
