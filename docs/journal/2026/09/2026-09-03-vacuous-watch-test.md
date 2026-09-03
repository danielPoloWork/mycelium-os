# 2026-09-03 — the test that could not fail (roadmap 4.18)

- **Session scope:** roadmap 4.18 — a watch-mode test flaked once on macOS CI, and the item
  said establish the cause before changing anything.
- **PR:** #68 (`test/watch-observer-without-a-timeout`). Follows #67 (4.15), merged as
  `60cab80`.
- **Milestone 4:** 4.18 done; 4.8, 4.19, 4.20, 4.21, 4.22 open.

## Establishing the cause found a different fault

The item named two candidates for `DID NOT RAISE Empty` on `macos-14`: FSEvents coalescing
latency, or a resolved-versus-unresolved path comparison (macOS `tmp_path` lives under
`/var`, a symlink to `/private/var`). I could not reproduce the flake — no macOS here — so I
went at the test instead, and the test turned out to be broken in a way its green had been
hiding.

**It watched nothing.** The fixture builds a corpus with a `knowledge/` tree. With an
authored tree present, `_start_observer` schedules `root/knowledge` — and the derived store
is `root/.mycelium`, a *sibling* of that directory. Not one event about the store was ever
delivered to the handler:

```text
corpus with knowledge/   raw events delivered: 0    (of which under .mycelium/: 0)
bare root corpus         raw events delivered: 103  (of which under .mycelium/: 103)
                         passed the filter:    0
```

So the assertion — "nothing arrives within two seconds" — was true no matter what the filter
did. I checked that the obvious way: replace the handler with one that has no derived-store
filter at all, run the test's own scenario, and

```text
=> the OLD assertion PASSED with the guard deleted - it tested nothing
```

That is [BUG-0020](../../bugs/2026/09/BUG-0020-the-rebuild-loop-guard-was-covered-by-a-vacuous-test.md).
Not a product defect — the filter works, the scoping works — but a false assurance on the
guard that stops watch mode rebuilding forever, which is worth a record. BUG-0015 set the
precedent: a defect in a verification artifact goes in the ledger when it is verified and
reproducible, and this one is both.

## Two mechanisms, and the test was written against the wrong one

The loop is protected twice over, and I had not appreciated that the two are independent:

1. **Scope** — an authored tree narrows the watch, so the store is never observed.
2. **Filter** — when the repository root *is* the corpus, the store is inside the watch and
   `is_relevant` rejects every path in it.

Mechanism 2 is the one the test named and mechanism 1 is the one its fixture exercised. The
rewrite uses a bare-root corpus so the guard is actually reachable — 103 events to reject on
this machine — and mechanism 1 now has a test of its own, because it is what made the old
test vacuous and the next reader will otherwise write that test again.

## The negative, without a clock

The item's preferred remedy was right and I took it: bound the negative with a
synchronisation point the watcher owns rather than a longer wait. After the build the test
edits a known document, waits for **that** path, drains the queue, and asserts nothing in it
names the derived store.

Three properties fall out. The wait is *positive*, so a broken watcher fails loudly instead
of passing vacuously. The check is order-independent — anything spurious the build produced
was enqueued before the sentinel, so draining past it is complete. And there is no timeout
on the thing that must not happen, which is the only way an "it did not happen" assertion
can be trusted on a four-cell matrix.

The mutation check runs both ways in the bug record: broken filter plus bare root → 52 of 55
events under `.mycelium/`, assertion fails. Broken filter plus the old fixture → green.

## What I did not conclude

The macOS flake itself is still unreproduced, and I said so rather than picking a winner.
The symlink candidate I can rule out with evidence: `is_relevant` resolves *both* operands
before relating them and fails **closed** when it cannot, so a `/var` versus `/private/var`
mismatch would drop events, never invent one — asserted now by a symlink test that runs on
exactly the platforms that have symlinks. FSEvents coalescing remains the likely explanation
(the fixture writes its documents microseconds before the observer starts, and those are
`.md` files under the watch, so they *are* relevant and the old assertion would trip on
them), and it is no longer load-bearing: the rewritten test does not care which timing it
was, because it no longer asserts that no event arrived.
