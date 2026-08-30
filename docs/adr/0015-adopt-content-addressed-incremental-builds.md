# ADR-0015: Compile incrementally through a content-addressed stage cache

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §4
- **Related:** [ADR-0009](0009-adopt-build-publication-semantics.md) (the publication
  semantics this inherits unchanged), [ADR-0012](0012-adopt-the-g6-determinism-gate.md)
  (the golden this re-blesses, and the gate that makes caching trustworthy),
  [ADR-0014](0014-adopt-partial-strict-configuration.md) (config slices in build keys),
  [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) (the store the cache
  index lives in); spec 02 §§3–4, spec 03 §2; D-005, D-008, D-016; roadmap 3.1

## Context

D-008 names the content-addressed incremental build DAG as the product's technical
differentiator, and spec 02 §4 fixes its two contracts: every stage has a **build key** —
SHA-256 over `(stage_id, implementation_version, input_digests, config_digest,
schema_version)` — and the incremental algorithm recompiles only documents *"whose source
digest, config slice, or stage versions changed"*, with a cache of *"CAS + SQLite"*. The
v0 orchestrator (2.7) deliberately shipped without any of it: full recompilation every
build, wipe-and-rewrite storage, and the promise that 3.1 would inherit its publication
semantics unchanged.

The exit gate is unforgiving in a useful way: an incremental single-document rebuild must
be **byte-equal to a clean rebuild** (and < 2 s p95 on the reference profile). Byte
equality is what separates a build cache from a bug farm — any shortcut that can disagree
with a from-scratch build is not an optimization, it is a correctness hole with good
latency numbers.

Three design questions had no obvious answer:

1. **What may dirty detection trust?** mtime alone is the classic answer (make, ninja) and
   the classic failure: renames preserve mtimes, pinned-mtime trees (our own determinism
   fixtures) defeat it entirely, and coarse filesystem timestamps miss rapid edit cycles.
2. **Where does the previous build's state live?** The manifest records corpus-level
   digests; nothing recorded per-document state to diff against.
3. **How does the manifest stay O(changed)?** v0 digested the *entire* record set into
   `artifact_digests` — loading and serializing every record on every build is exactly the
   O(corpus) work an incremental build exists to avoid.

## Decision

**A two-level cache: `build_cache` rows index CAS blobs.** Stage outputs are canonical
JSON blobs in `.mycelium/cas/<xx>/<sha256>`, named by `digest_bytes` of their content —
the same custody rule spec 03 §2 fixes for tier-1 originals, so ingestion (milestone 4)
reuses this module rather than growing a second CAS. The `build_cache` table (in the DDL
since 2.6) maps build keys to blob digests. The split is what makes the cache safe to
distrust: a row without its blob is a miss, a blob that no longer hashes to its own name
is deleted and re-run, and a blob whose records fail validation is journaled
(`cache.invalid`) and recomputed. The cache is an optimization, never an authority.

**Per-document state in a new `doc_state` table — schema v1, and the writer operates the
D-016 rebuild.** One row per indexed document: source digest, source mtime, environment
digest, per-document artifact digests, warnings. It cascades from `documents`, so the
index and the dirty detector's ground truth cannot disagree. Adding the table bumps
`SCHEMA_VERSION` to `mycelium/store/v1`, which exposed a latent gap in 2.6's refusal
message: it told the operator to run `mycelium build`, but the build path raised the same
refusal. Now the *reader* still refuses a foreign store, while the *writer* recreates it
in place — dropping every object rather than deleting the file, because Windows will not
unlink a database a concurrent reader holds open (D-015). Recreation is journaled
(`store.recreated`), and it is lawful only because every row is derived from source
(D-005).

**Dirty detection is digest-based and conservative: every file is read and hashed every
build.** The plan step computes per-document source digests — the spec's own algorithm —
so content truth never comes from metadata. A document is untouched only when source
digest, mtime, *and* environment digest (stage versions, record schema versions, config
slices, namespace) all match its `doc_state` row. mtime cannot make a document clean; it
can only make one dirty — a digest-equal file with a new mtime reruns exactly the
assemble stage, because mtime is that stage's input (ADR-0009: mtime → `created_at`).
What the unchanged-file fast path *does* skip is the frontmatter parse: an indexed
document was pinned, its pinned identity is frontmatter, and frontmatter is content — so
an unchanged digest proves the id is still in the file, and the row says which one.

**The per-document chain is parse → chunk → assemble; only the first two are cached.**
Parse (markdown-it → KIR, the expensive stage) keys on the source digest and the pinned
id; chunk keys on the parse artifact's digest, the path (anchors embed it), and its
config slice — `max_tokens` and the token counter's qualified name, deliberately
excluding advisory `target_tokens` (ADR-0014; 3.8 bumps the stage version when it becomes
real). Assemble is recomputed for every dirty document: it is arithmetic over cached
inputs, and its mtime input is the one that most often changes alone. The release version
participates in **no** key — bumping `__version__` must not cold-start every cache — so a
behavior change without its stage-version bump is the failure mode this design accepts,
and the net that catches it is G6 plus the incremental-equals-clean suite, which compare
cached against freshly computed output on every CI run.

**Manifest corpus digests fold per-document digests.** `artifact_digests["documents"]`
(and `"chunks"`) are `digest_json` over the path-ordered list of per-document artifact
digests from `doc_state`, not over the full record set. Manifest assembly is O(changed);
equality between incremental and clean builds holds by construction; and the digests
remain recomputable by an auditor from the store alone. Spec 03 §7 requires
per-artifact-class digests without fixing their construction — this ADR fixes it.

**Identity conflicts and quarantines resolve over the whole plan, exactly as a clean
build would.** First claim in path order wins a duplicated `mycelium_id`, even when the
loser was happily indexed and the thief is the newcomer; a document that stops parsing
loses its rows; both directions are covered by equality tests. Deletions run before
insertions inside the one publication transaction, so `UNIQUE(path)` cannot fire on
renames or path swaps.

**`mycelium build --clean` is the escape hatch**: recompile everything, consult no cache,
publish the same bytes. It exists so "is the cache lying to me?" is a one-flag experiment
rather than a support thread.

## Alternatives Considered

- **mtime(+size) fast path that skips reading unchanged files** — the make/ninja/tup
  answer, and the only way to beat a per-file read floor without FS events. Rejected *for
  3.1*: a false "clean" (rename preserving mtime, pinned-mtime tree, coarse timestamps,
  same-second edit) silently serves stale artifacts, which is the one failure a
  determinism product cannot afford. Watch mode (3.5) is where event-driven read-skipping
  can be argued safely, with the OS as the change detector instead of a guess.
- **Store-diff only, no CAS** (keep rows, diff against `documents`, no keyed artifacts) —
  simpler, no new tables. Rejected: it reuses only the *latest* state, so config A → B →
  A recompiles the corpus twice, and a reverted edit recompiles — precisely the wins
  content addressing exists for (and the A→B→A case is a test now).
- **Digest the full record set for the manifest, as v0 did** — no golden re-bless.
  Rejected: loading and serializing 10⁵ records per build is O(corpus) work in the O(1)
  path; measured at seconds against a < 2 s end-to-end budget.
- **Cache the assemble stage too** — uniform treatment of stages. Rejected: it trades a
  dict-build for a CAS round-trip, adds mtime as a third invalidation axis on cached
  artifacts, and saves nothing measurable.
- **Include `__version__` in build keys** — trivially safe staleness story. Rejected:
  every release would cold-start every cache; stage implementation versions invalidate
  precisely what changed, which is the entire point of stage-level keys.
- **A separate `cache.db`** — isolates cache lifetime from the serving store. Rejected:
  the cache index must commit atomically with the rows it describes, and one database,
  one transaction is the crash-safety argument ADR-0009 already made.
- **Recreate a foreign-version store by deleting the file** — the obvious D-016 reading.
  Rejected after it failed on Windows: an open reader blocks the unlink. In-place drops
  behave identically on every platform and keep readers isolated by WAL.

## Consequences

- **The G6 golden is re-blessed with a two-line diff** — the `documents` and `chunks`
  corpus digests changed construction. Every chunk, document record, warning, and count
  in the golden is byte-identical, which is the evidence the compiler's *output* did not
  change. `edges` is unchanged (an empty list digests identically under both
  constructions).
- **Measured on 200 documents (Windows dev machine):** cold build 12.9 s; no-op
  incremental 452 ms; single-edit incremental 546 ms wall — the marginal document costs
  ~46 ms of compile, and the floor is the plan scan at ~2 ms/document (bounded by
  per-file open/stat, not by hashing — the read itself is the cost). The < 2 s
  single-edit budget holds with wide margin at this size and structurally (floor + one
  document's chain); at the envelope top (10⁵ chunks ≈ thousands of documents) the
  every-build scan is the term to watch, and 3.5's event-driven planning plus the spec's
  own "parallel, bounded" allowance are the named paths if the reference profile busts
  the budget. `tests/bench/test_build_bench.py` tracks all three numbers.
- **Store schema v1**: existing stores (v0.1.0/v0.2.0) are recreated on the first build —
  a full recompile, journaled, no manual deletion. Read-only consumers of a v0 store get
  the same refusal message as before.
- **`.mycelium/cas/` grows without bound until 3.2**: nothing garbage-collects orphaned
  blobs or stale `build_cache` rows yet — `created_at` on cache rows exists so 3.2's
  retention window has something to cut on. Deleting the directory remains safe at the
  cost of one clean rebuild.
- **`BuildStats`** (reused/rebuilt/removed, per-stage runs vs hits) is returned, printed
  by the CLI, and journaled — so "why did that build take 12 seconds" is answerable from
  `journal.jsonl`. The stats are diagnostics, never part of the manifest: two correct
  builds may legitimately differ in how much they reused.
- The always-publish semantics stay: a no-op build publishes a fresh snapshot with
  `parent_id` lineage. Snapshot files accumulate faster now that builds are cheap —
  3.2 (`snapshots`/`rollback`/`gc`) is the counterpart.
- Patterns: **Pipeline** and **Content-Addressed Cache** move from Planned to Implemented
  in the catalogue, both under this ADR.

## References

- Spec: `.draft-specs/02-architecture.md` §§3–4 (layout, stage DAG, incremental
  algorithm); `.draft-specs/03-data-model.md` §2 (digest rules, CAS custody)
- Decision log: D-005 (derived world is disposable), D-008 (the differentiator),
  D-016 (schema versioning, rebuild migration)
- RFC-0001 — NFR table (incremental < 2 s p95, byte-equal), algorithm sketch
- Benchmarks: `tests/bench/test_build_bench.py`; equality suite:
  `tests/test_build_incremental.py`
