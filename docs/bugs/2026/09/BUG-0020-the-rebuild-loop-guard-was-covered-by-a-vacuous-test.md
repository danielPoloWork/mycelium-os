---
id: BUG-0020
title: the watcher's infinite-rebuild guard was covered by a test that passes with the guard deleted
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-03
affected-versions: ">=0.3.0"
fixed-in: "0.4.0"
---

# BUG-0020: the rebuild-loop guard was covered by a vacuous test

## Summary

`test_the_observer_ignores_the_derived_store` claimed to cover watch mode's
infinite-rebuild guard over a real filesystem watcher: a build writes into `.mycelium/`,
and if those writes came back as changes the loop would rebuild forever.

It covered nothing. Its corpus had a `knowledge/` tree, so the observer watched
`knowledge/` — and `.mycelium/` is a *sibling* of that directory, not a child. No event
about the derived store was ever delivered to the handler, so the assertion ("nothing
arrives within two seconds") held whatever the filter did. **Deleting the filter entirely
leaves the test green.**

No product defect: the filter and the scoping both work. What was broken is the assurance —
a high-consequence guard was believed to be covered end to end and was not. It is recorded
here rather than left in the roadmap item because it is verified and reproducible, which
[BUG-0015](../08/BUG-0015-benchmark-times-a-pattern-no-code-has.md) established as the bar
for a defect in a verification artifact.

The item that produced this finding — roadmap 4.18 — was filed for something narrower: the
same test flaked once on macOS CI (`DID NOT RAISE Empty`, job 100275954484) and passed on
re-run. That flake is a symptom of the same fault. The assertion was not about the derived
store at all, so what tripped it was some event about `knowledge/`; the two candidates the
item named are addressed under *Notes*.

## Environment

- Windows 11, CPython 3.12.10, `watchdog` 6.x, `mycelium-os` 0.4.0.dev (`main` at `60cab80`).
- The flake itself was observed on `macos-14` / CPython 3.12 and has not been reproduced.

## Reproduction

Deterministic on Windows; the mechanism is platform-independent.

**1. The derived store is outside the watch.** With a `knowledge/` tree present,
`CorpusScope().scope_of(root)` is `root/knowledge`, which is what `_start_observer`
schedules:

```text
corpus with knowledge/   watched='knowledge' recursive;  .mycelium under the watch? False
bare root                watched='repo'      recursive;  .mycelium under the watch? True
```

**2. Nothing is delivered, so nothing is filtered.** Recording every event the handler
receives during a build of a pre-pinned corpus:

```text
=== corpus with knowledge/   (the test's own fixture)
  raw events delivered: 0    (of which under .mycelium/: 0)
  passed the filter:    0

=== bare root corpus
  raw events delivered: 103  (of which under .mycelium/: 103)
  passed the filter:    0
  event types seen:     ['created', 'deleted', 'modified', 'moved']
```

**3. The test passes with the guard removed.** Replace the handler with one that has no
derived-store filter — `events.put(path)` for every non-directory event — and run the test's
own scenario:

```text
=> the OLD assertion PASSED with the guard deleted - it tested nothing
```

Run the same broken handler against a **bare-root** corpus, where the store is inside the
watch, and the fault surfaces immediately:

```text
events seen: 55; under .mycelium/: 52
sentinel present: True
=> the rewritten assertion WOULD FAIL on a broken filter: True
```

## Root cause

Two independent mechanisms protect the loop, and the test was written against the wrong one:

1. **Scope.** When a repository has an authored tree, the watch is narrowed to it, so the
   derived store is never observed. This is why the test saw zero events.
2. **Filter.** When the repository root *is* the corpus, `.mycelium/` is inside the watch
   and `is_relevant` rejects every path in it. This is the guard the test named, and it is
   only reachable in the second shape.

The fixture used the first shape and asserted against the second. Compounding it, the
assertion was a negative bounded by a timeout — *nothing arrives within two seconds* —
which cannot pass for a good reason. It can only fail to fail, and it converts any unrelated
event anywhere in the watched tree into a red build on a matrix cell.

## Fix

The test now uses a **bare-root corpus**, so the guard is reachable — measured, 103 raw
events to reject on this machine — and the negative is bounded by a **sentinel** rather than
a clock. After the build it edits a known document, waits for *that* path (a positive wait,
which fails loudly and truthfully if the watcher is broken), drains the queue, and asserts
that nothing in it names the derived store. Anything spurious the build produced was
enqueued before the sentinel, so draining past it is a complete check with no timeout on
the thing that must not happen.

`test_an_authored_tree_puts_the_derived_store_out_of_the_watch` states mechanism 1
separately, because it is what made the old test vacuous and a reader who does not know it
will write that test again.

## Regression test

- `tests/test_watch.py::test_the_observer_ignores_the_derived_store` — rewritten; fails
  when the filter is removed (shown above).
- `tests/test_watch.py::test_an_authored_tree_puts_the_derived_store_out_of_the_watch` —
  pins the scoping so the coverage gap cannot silently reopen.
- `tests/test_watch.py::test_the_derived_store_is_never_watched` — the path list is now the
  set a build was *observed* to write (`store.db`, `CURRENT`, `journal.jsonl`, `lock`, a
  snapshot manifest, CAS blobs, an eval manifest).

## Notes

The roadmap item named two candidate causes for the macOS flake. Neither is the mechanism,
and both are now covered:

- **A resolved-versus-unresolved path comparison** (macOS `tmp_path` is under `/var`, a
  symlink to `/private/var`). Ruled out: `is_relevant` resolves *both* operands before
  relating them, and fails **closed** when it cannot. A mismatch there would drop events,
  never invent one. `test_a_symlinked_root_classifies_the_same_as_its_real_path` asserts it
  on platforms that have symlinks — including the one where it was suspected — and
  `test_classification_does_not_depend_on_how_a_path_is_spelled` asserts the portable half.
- **FSEvents coalescing latency.** Plausible and unreproduced: the fixture writes its
  documents microseconds before the observer starts, and a macOS stream can still deliver
  those creations. They are `.md` files under the watch, so they *are* relevant, and the old
  assertion would fail on them. Left as the likely explanation rather than a verified one —
  the rewritten test does not depend on which timing it was, because it no longer asserts
  the absence of events.
