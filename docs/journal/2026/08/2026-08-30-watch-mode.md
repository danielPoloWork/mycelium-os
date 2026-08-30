# 2026-08-30 — watch mode, and correcting a promise I made two items ago (roadmap 3.5)

- **Session scope:** roadmap item 3.5 — watch mode: debounced FS events → incremental
  builds (spec 02 §7, spec 05 §1).
- **PR:** #35 (`feat/watch-mode`). Follows #34 (3.4), merged as `933b7ef`.
- **The item's main output is a refusal**, and it contradicts something this journal said at
  3.1.

## The correction

3.1's checkpoint promised that 3.5 was "where the plan-scan floor (~2 ms/document,
I/O-bound) finally gets removed, because the OS becomes the change detector instead of a
full scan". I repeated it at 3.4. **It was wrong**, and the specification says so in the
same sentence that defines the feature: *"debounced FS events → incremental builds;
**identical guarantees**"*.

Not "faster guarantees on a best-effort basis". Identical. And once you look at what an
event stream actually is, that is the right call rather than a limitation:

- watchers drop events under load — every platform backend documents it;
- editors save through temp-file-and-rename, so the event names a file that is already gone;
- `git checkout`, `rsync`, and container mounts rewrite trees behind the watcher;
- a watcher started *after* an edit never hears about that edit at all.

Every one of those produces a **false clean** — and ADR-0015 already ruled on that class of
shortcut: *"a false 'clean' is the one failure a determinism product cannot afford."* So
events decide *when* to build; the build decides *what* to build, with the same conservative
digest scan as always. A test asserts the consequence directly: the artifact digests of a
watch-published snapshot equal those of a manual build of the same repository.

The floor stays, and the honest way to attack it is a faster scan — parallel reads, cheaper
hashing — not a less trustworthy one. ADR-0019 records the reversal explicitly rather than
quietly shipping something narrower than what the journal promised.

## What the loop actually has to get right

With the fast path off the table, all the difficulty moved to the loop's edges, and each one
is a test:

- **Debounce**, with a ceiling — a save burst becomes one build, but a continuously
  rewritten tree (`git checkout`) must not postpone the build for as long as it runs.
- **Never watch `.mycelium/`.** A build writes there; watching it is an infinite rebuild
  loop wearing a plausible disguise. The rule reuses discovery's dot-directory exclusion, so
  watch mode and the compiler agree on what the corpus is.
- **`mycelium.toml` counts** — it feeds the config digest (ADR-0014).
- **A failed build never ends the session** — a document mid-edit is routinely unparseable.
- **Build once before waiting**, because a watcher started after an edit hears nothing.

## Three bugs the tests caught — two before CI, one only on Linux

**The swallowed sentinel.** `collect_batch` returned the pending batch when a stop arrived
mid-drain — and consumed the sentinel doing it. The next call blocked forever on an empty
queue. The whole test file hung; the fix is to put the sentinel back, so the last save is
still built *and* the loop still stops. The test that was meant to pin this
(`test_changes_before_a_stop_are_still_built`) was already written and correct — the suite
simply never reached it, because the hang came first.

Second time this milestone that a hang had to be debugged rather than guessed at, and the
lesson from 3.4 paid off immediately: redirect to a file, use
`pytest -o faulthandler_timeout=N`, and stop theorising.

**Two flaky tests of my own making.** One compared digests across *two* repositories —
which differ on file mtimes alone, since mtime becomes `created_at` (ADR-0009); it now
builds the same repository both ways. The other timed batch boundaries with `sleep`, which
races the build; it now uses a `ScriptedSource` whose `QUIET` marker *declares* where one
batch ends, so multi-batch behaviour is asserted without depending on how long a build takes.

## The bug the matrix found — twice, on two platforms, for two different reasons

CI caught the third bug, and it took **two rounds on two operating systems** to see what it
actually was. Both rounds failed the same test:
`test_the_observer_ignores_the_derived_store` — the one written to catch an infinite rebuild
loop.

**Round one: Ubuntu red, Windows and macOS green.** inotify reports *reads* as well as
writes. The build's plan scan opens every document (ADR-0015 reads and digests everything,
every build), producing a burst of `opened` / `closed_no_write` events on the corpus it had
just read. The handler accepted any event type, so on Linux **every build would have
triggered the next one, forever**. Fix: an event-type filter.

**Round two: Ubuntu and Windows green, macOS red — same test.** FSEvents does not report
reads as reads: a read updates atime, atime is inode metadata, and watchdog surfaces that as
a *modification*. **Indistinguishable from a write.** No event-type filter can fix it, and
had I only run Linux I would have shipped believing the problem was solved.

The real fix is one level up, and it is better than what I had: **the loop proves a change
is real before building**, asking the question the build asks against the same `doc_state`
truth — does this file's content, or its mtime, differ from what is indexed? A read changes
neither, on any platform. It reads only the batch's own files, and it is conservative in
every direction: unreadable file, missing store, unknown path, anything unexpected means
*build*. It may only ever suppress a build it can prove would publish the same corpus.

mtime is in the comparison deliberately — it becomes `created_at` (ADR-0009), so a `touch`
does change what a manual build would publish, and the watcher must not decide otherwise.

Three things fell out of this that I did not plan:

1. The extra no-op build after identity pinning — which the first version documented as an
   accepted cost — is **gone**. `doc_state` holds the post-pin digest and mtime, so the loop
   recognises its own write.
2. Four older tests started failing, correctly: they named a file without actually changing
   it and had been relying on "any event means build". They are more honest now.
3. Watch mode is no longer "run `mycelium build` in a loop": a manual build in an unchanged
   repository publishes a snapshot, a watch session does not. That is the one deliberate
   difference, and ADR-0019 states it.

Lessons worth carrying: the three-OS matrix earned its entire cost here; *the test was
right* both times, failing for exactly the reason it was written; and the first fix passing
on two platforms is not evidence that the diagnosis was complete.

## What the real binary showed

Driving `mycelium build --watch` as a subprocess and editing files underneath it: an edit is
one build (~110 ms), and a *newly added* document costs one extra no-op build (~30 ms) —
because the first compilation pins its `mycelium_id` back into the file, which is a real
change and the watcher rightly reports it. The loop converges after that one pass, and there
is now a test for the convergence.

I chose **not** to suppress that extra build. Doing so means discarding events for paths the
previous build wrote, and a user edit landing in that window would be lost — the failure
this whole design refuses. Documented instead.

The other visible consequence: every build publishes a snapshot (ADR-0009), so a session
leaves a long history. Watch mode now says how many it published and names `mycelium gc` —
it does not delete anything on its own, because what to retain is the operator's call.

## Where the project stands

- **3.5 complete** pending merge. Milestone 3: 3.1–3.5 done; 3.6–3.12 open.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (583 passed, 18 skipped), `python tools/consistency_lint.py`.
- The G6 golden is untouched: watch mode adds no compiler behaviour, which is the whole
  point of the decision above.

## How the next session resumes

- Wait for PR #35 to merge, then **3.6** (`mycelium export` — the JSONL interchange bundle,
  D-006, spec 03 §9). It is the last "surface" item before 3.7 wires the eval gates into CI.
- Carry into 3.6: the export bundle is defined against the *records*, which every milestone
  has been extending (vectors at 3.3, edges at 3.4). Check spec 03 §9's file list against
  what the store now actually holds before deciding what a bundle contains.
