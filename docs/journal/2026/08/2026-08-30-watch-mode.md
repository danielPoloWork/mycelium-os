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

## Two bugs my own tests caught

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
