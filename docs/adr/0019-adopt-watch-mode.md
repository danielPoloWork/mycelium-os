# ADR-0019: Let filesystem events decide *when* to build, never *what* to build

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §7
- **Related:** [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the dirty
  detection this refuses to bypass), [ADR-0009](0009-adopt-build-publication-semantics.md)
  (the always-publish semantics a watch session multiplies),
  [ADR-0016](0016-make-snapshots-restorable.md) (the `gc` that answers it),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (the optional-extra
  precedent); spec 02 §§3, 7, spec 05 §1; D-008, D-017; roadmap 3.5

## Context

Spec 02 §7 gives watch mode a single line: *"debounced FS events → incremental builds;
**identical guarantees**"*. Spec 05 §1 gives it a flag: `mycelium build [--watch]`.

The tempting reading is that watch mode is where the compiler finally gets fast, because the
operating system hands it a perfect dirty set. Roadmap 3.1's own journal note said as much:
that 3.5 would remove the plan-scan floor (~2 ms/document, I/O-bound) because "the OS
becomes the change detector instead of a full scan". **That note was wrong**, and this ADR
corrects it in the same repository that made the claim.

It was wrong for two independent reasons. The specification's own sentence says *identical
guarantees* — not "faster guarantees on a best-effort basis". And an event stream is simply
not a dirty set:

- Watchers drop events under load; every platform backend documents this.
- Editors save through temp-file-and-rename, so the event a naive watcher sees names a file
  that no longer exists.
- Tools rewrite trees behind the watcher's back — `git checkout`, `rsync`, a container
  mount — and a watcher started *after* an edit never hears about it at all.
- A watcher watching the wrong directory (the corpus moved, a symlink changed) reports
  nothing while the corpus changes underneath it.

ADR-0015 already made the governing judgment for exactly this class of shortcut: *"a false
'clean' is the one failure a determinism product cannot afford"*. Every failure above is a
false clean.

## Decision

**Events decide when to build. The build decides what to build.** Each rebuild is the
ordinary incremental build — same conservative digest-based dirty detection, same publication
semantics — so a watched repository and a hand-built one publish the same snapshot from the
same sources. There is no second correctness story, and no "watch mode was stale" failure
mode to explain to anyone. A test asserts it directly, comparing the artifact digests of a
watch-published snapshot against a manual build of the same repository.

The plan scan therefore stays. At the measured ~2 ms/document it costs about 450 ms on a
200-document corpus, which is affordable for a loop that fires on a quiet period; at the
10⁵-chunk envelope it would be the term to attack, and the honest way to attack it is
faster scanning (parallel reads, cheaper hashing), not trusting the event stream.

**What the loop must get right is everything around the build**, and each of these is a
test:

- **Debounce.** One save is a burst of events; the loop waits for quiet, so a burst becomes
  one build. A ceiling (`MAX_BATCH_WAIT_S`) stops a continuously-rewritten tree — a
  `git checkout`, an rsync — from postponing the build for as long as it runs.
- **Never watch the derived store.** A build *writes* into `.mycelium/`, so watching it is
  an infinite rebuild loop wearing a plausible disguise. Relevance uses the same
  dot-directory rule discovery uses (spec 02 §3), so watch mode and the compiler agree on
  what the corpus is.
- **Only accept events that mean the content changed** — and Linux is why that sentence
  exists. inotify reports *reads* as well as writes, so a build's own plan scan, which opens
  every document, produces a burst of `opened` / `closed_no_write` events on the corpus it
  just read. Accepting those means every build triggers the next one, forever. Windows and
  macOS never emit them, so the platform that needs the filter is not the one this was
  developed on: CI's Ubuntu cells failed while Windows and macOS passed, on the very test
  written to catch an infinite rebuild loop. `closed` (inotify's `IN_CLOSE_WRITE`) *is*
  accepted — a completed write is the most reliable "this file is fully saved" signal there
  is.
- **`mycelium.toml` counts as a change.** It feeds the config digest (ADR-0014), so editing
  it changes what a build produces exactly as editing a document does.
- **A failed build never ends the session.** A document mid-edit is routinely unparseable, a
  config mid-edit is routinely invalid, and another process may hold the writer lock. All
  three are reported and the loop keeps watching — which is precisely when the operator
  needs the next successful build most.
- **Nothing is lost on shutdown.** A stop that arrives while a batch is draining is put
  back: the last save is still built, and the loop still stops. (Swallowing it left the loop
  blocked on an empty queue — found by the tests, and the reason the sentinel is re-queued.)
- **Build once before waiting.** A watcher started after an edit hears nothing about it, so
  a session that began by waiting would serve a stale snapshot and look like it was working.

**The watcher is an optional extra** (`pip install mycelium-os[watch]`), like the embedder.
An agent querying a published snapshot never needs it, and D-017's minimal runtime closure
is worth more than saving one install flag for a development convenience. The loop takes its
events from a queue, so the debouncing, relevance, and failure behaviour above are tested on
every platform whether or not `watchdog` is installed; the watcher itself is one small
adapter with its own tests.

**`--watch` refuses `--json`, `--clean`, and `--require-vectors`.** `--json` promises exactly
one document on stdout (spec 05 §1) and a session emits one per build; `--clean` and
`--require-vectors` are single-shot intents whose meaning does not survive an unattended
loop. Refusing beats redefining a convention or silently ignoring a flag.

## Alternatives Considered

- **Trust the event set and skip the scan** — the optimisation this item was expected to
  deliver. Rejected on the four failure modes above, all of which produce a *silently stale
  snapshot*. If the scan ever becomes the bottleneck, the fix is a faster scan, not a
  less trustworthy one.
- **Trust events, then reconcile with a periodic full scan.** Rejected: it keeps the fast
  path's staleness window and adds a second code path to reason about, in exchange for a
  saving that is not yet needed at v1 scale.
- **Poll instead of using a watcher** (stat the tree on a timer, no dependency). Rejected:
  polling *is* the plan scan, so it buys nothing over the loop already described, and it
  burns a core continuously to do it.
- **Make `watchdog` a core dependency.** Rejected: the runtime closure is deliberately four
  packages (D-017), and nothing in the serving path needs a filesystem watcher.
- **Prune snapshots automatically during a session.** Rejected: `gc` takes the writer lock
  and deletes history a user might want to roll back to. Watch mode reports how many
  snapshots it published and names `mycelium gc`; what to retain stays the operator's call.
- **Suppress the rebuild caused by the build's own identity pinning.** Rejected: it needs
  the loop to discard events for paths the previous build wrote, and a user edit landing in
  that window would be *lost* — the failure this design refuses everywhere else. The extra
  build is a no-op costing tens of milliseconds, and it is documented rather than papered
  over.

## Consequences

- **A watch session's snapshot history grows one entry per build**, because ADR-0009's
  publication semantics are unchanged: even a no-op build publishes. Measured on a demo
  session: an edit is one build (~110 ms), and a *newly added* document costs one extra
  no-op build (~30 ms) because the first compilation pins its `mycelium_id` back into the
  file — a real change, which the watcher rightly reports. The loop converges after that
  one extra pass, and a test pins the convergence.
- **`mycelium gc` is the counterpart**, and the session's closing line says so.
- **Roadmap 3.1's journal note is corrected**: the plan scan is not removed by watch mode
  and was never going to be, because the specification asks for identical guarantees. The
  scan's cost stays a 3.12-adjacent performance question, not a correctness trade.
- **The CLI's build reporting is now one function**, shared by a single build and every
  build in a session, so the two cannot drift into describing the same outcome differently.
- Testing shape worth reusing: the loop's event source is a queue, and a `ScriptedSource`
  declares batch boundaries instead of timing them — so multi-batch behaviour is asserted
  without sleeps and without depending on how long a build takes.
- **The event-type filter is a module-level predicate, not a detail inside the adapter**,
  precisely because the bug it prevents only reproduces on one platform. `is_change_event`
  is asserted directly on every OS, and a second test pins our strings against watchdog's
  own `EVENT_TYPE_*` constants so an upstream rename fails loudly rather than silently
  reopening the loop.

## References

- Spec: `.draft-specs/02-architecture.md` §3 (what the corpus is), §7 (the concurrency
  table's watch-mode row); `.draft-specs/05-interfaces-and-plugins.md` §1 (`--watch`)
- Decision log: D-008 (the incremental compiler whose guarantees this preserves), D-017
  (minimal runtime closure)
- [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) — "a false clean is the one
  failure a determinism product cannot afford", the sentence this decision follows
- Tests: `tests/test_watch.py`
