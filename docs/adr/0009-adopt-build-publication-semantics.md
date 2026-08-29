# ADR-0009: Fix the build's publication semantics — lock file, transaction-then-swap, identity pinned at first build

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §§4, 7
- **Related:** [ADR-0005](0005-adopt-in-repo-identity-library.md) (ULID factory),
  [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) (store, `BEGIN IMMEDIATE`);
  spec 02 §2 (tier ownership), §3 (layout), §7 (concurrency); spec 03 §3 (frontmatter
  ownership), §7 (manifest); D-005, D-015, D-016; roadmap 2.7 (sets-pattern)

## Context

Roadmap 2.7 is marked *sets-pattern*: the publication and crash-safety semantics chosen
here bind every later phase — the incremental DAG (3.1), rollback and GC (3.2), watch mode
(3.5), and the serving layer all inherit them unchanged. The spec fixes the mechanisms
(advisory lock file with pid + host + heartbeat mtime; `CURRENT.tmp` → rename → fsync;
immutable manifests) but leaves the *composition* open, and it contradicts itself once:
spec 02 §2 says the build "never writes tiers 1–2", while spec 03 §3's ownership table says
`mycelium_id` is "written once by `mycelium build`". Both cannot be literally true, and the
choice decides whether deterministic rebuilds are possible at all.

## Decision

**Publication order.** One writer, one transaction, one swap::

    acquire .mycelium/lock                 # O_CREAT|O_EXCL; heartbeat = mtime
    BEGIN IMMEDIATE                        # readers keep the old committed state (WAL)
      wipe + rewrite documents/chunks      # v0: clean rebuild; 3.1 makes this dirty-only
      write snapshots/<ulid>.json          # the manifest exists before anything names it
      meta[current_snapshot] = <ulid>
    COMMIT                                 # data + the store's own pointer, atomically
    swap CURRENT (tmp → os.replace → fsync)
    release lock

Crash windows, stated rather than hoped: before COMMIT, everything rolls back, `CURRENT`
is untouched, and at worst an orphaned manifest file exists (GC at 3.2). Between COMMIT and
the swap there is a microseconds-wide window where the store is complete and
self-consistent while the `CURRENT` *file* still names the previous snapshot — whose data
the wipe replaced. That is v0's honest gap: with one mutable store there is no torn-free
path for a `CURRENT`-file reader in that window. `mycelium doctor` detects the
disagreement, the next build heals it, and closing it entirely (versioned tables or
copy-on-write stores) is platform-phase machinery that v0 must not preempt.

**The lock** is the spec's advisory file, created with `O_CREAT | O_EXCL` — the one
creation primitive atomic on every supported platform — holding pid, host, and acquisition
time, with liveness proven by mtime heartbeats. Stale after 10 minutes by default; takeover
is unlink-then-recreate, so racing takeovers collapse into the same create race and exactly
one wins.

**Identity pinning is the build's only tier-2 write.** The contradiction resolves in favor
of the ownership table, because the alternative is worse than a broken rule: an unpinned
document would mint a fresh ULID every build, so no two builds could ever be byte-identical
(G6 dead on arrival), and citations would not survive a rename. The write is a one-time,
idempotent, purely textual insertion — the file's own newline convention preserved, BOM
kept in place, never a YAML re-serialization — after which the build is the pure function
§2 wants. `BuildResult.pinned` lists the touched files so a caller (the CLI at 2.8) can say
"commit these".

**Failure taxonomy** (RFC-0001): a document that cannot be compiled — unreadable
frontmatter, a duplicate pinned id — is *quarantined*: counted in the manifest, named in a
warning, and the build goes on. Whole-build failures roll back whole. There is no torn
publish.

**Timestamps**: `created_at`/`updated_at` are the source file's mtime (UTC). Honest for
`updated_at`, a stand-in for `created_at` (POSIX has no birth time); stable across
rebuilds in place, which is what the G6 golden test (2.10) measures. Real provenance times
arrive with ingestion.

**Discovery** (v0): `knowledge/**/*.md` when `knowledge/` exists (spec 02 §3), else the
whole root — so a plain docs repository gets value with zero layout ceremony (TTFV) —
never entering dot-prefixed directories, which excludes `.mycelium`, `.git`, and editor
litter with one rule. Sorted paths, so discovery order is deterministic.

## Alternatives Considered

- **OS file locks (`fcntl`/`msvcrt`)** — kernel-enforced, self-releasing. Rejected: they
  evaporate with their holder, leaving no diagnosable trace of who died; they are not
  inspectable by `mycelium doctor` or a human; and their semantics differ enough across
  platforms (mandatory vs advisory, byte-range vs whole-file) that the portable subset is
  weaker than a JSON file with an mtime. The spec also names the file.
- **Holding the lock inside SQLite** (a `BEGIN EXCLUSIVE` sentinel connection) — one
  mechanism fewer. Rejected: ties lock lifetime to a connection object, cannot carry
  holder identity, and cannot outlive the store file it is supposed to guard during
  re-creation.
- **Write `CURRENT` inside the transaction's scope, before COMMIT** — would shrink the
  crash window. Rejected: it *inverts* the failure — a rollback after the swap would leave
  `CURRENT` naming a snapshot whose data was never committed, which is strictly worse than
  naming a stale one.
- **No identity write-back** (derive ids from paths, or keep a path→id table in the store)
  — keeps the build byte-pure. Rejected: path-derived ids die on rename (the exact thing
  `doc_id` exists to survive), and a store-resident table dies with `.mycelium/`, which is
  disposable by design (D-005). Identity must live in Git, and frontmatter is where the
  spec puts it.
- **Deferring pinning to `mycelium init`/`ingest`** — honors "the build never writes
  tier 2" literally. Rejected: it turns first-build determinism into a user chore and
  contradicts the ownership table's explicit "`written once by mycelium build`".
- **Wall-clock `created_at`/`updated_at`** — matches the spec's field names most
  literally. Rejected: every rebuild would change every document record, so no rebuild
  could ever be byte-identical.

## Consequences

- 3.1 (incremental DAG) replaces the wipe with dirty-only rebuilds *inside the same
  transaction shape*; nothing about locking or publication changes. 3.2 (rollback) is
  `swap_current` to an older manifest id — publication was designed so rollback is a
  pointer move.
- The first build of a repository modifies it (pins ids). This is by design and
  documented; CI determinism tests must build twice and compare the second.
- The commit-to-swap window exists and is documented rather than denied. Its detector
  (`meta[current_snapshot]` vs `CURRENT`) is a `mycelium doctor` check (2.8).
- Manifest bytes are platform-independent: `os.open` without `O_BINARY` lets the Windows
  CRT rewrite LF as CRLF, which the test suite caught on this machine — the flag is now
  part of the publication contract, and the LF-only assertion pins it.
- The journal (`journal.jsonl`) is append-only diagnostics (F-4): best-effort, never able
  to fail a build, never replayed. Event names chosen now (`build.started`,
  `build.published`, `build.failed`) are the stable vocabulary OTel maps onto post-1.0.
- Sequential v0 throughput: ≈ 519 ms for a 30-document full rebuild (~17 ms/document,
  local Windows baseline) — the number the incremental compiler must beat on
  single-document edits (< 2 s p95 budget, measured at 3.1/3.7).

## References

- Spec: `.draft-specs/02-architecture.md` §§2–4, 7 · `.draft-specs/03-data-model.md` §3, §7
- RFC-0001 — algorithm sketch (the pseudocode this implements) and failure taxonomy
- Decision log: D-005 (derived store disposable), D-015 (single writer, atomic publish),
  D-016 (schema versions)
- Patterns: Snapshot (`docs/patterns/README.md`)
