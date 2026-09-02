---
id: BUG-0018
title: the carried ingested judgements do not reproduce from their own generator
status: open
severity: medium
reporter: internal
discovered: 2026-09-02
affected-versions: ">=0.4.0"
fixed-in:
---

# BUG-0018: the carried ingested judgements do not reproduce from their own generator

## Summary

`eval/corpora/uv-docs-ingested/eval/{dev,release}.jsonl` are **derived** artifacts: every
query, grade and slice is copied from the second corpus's frozen sets and only the anchor is
recomputed (roadmap 4.10, ADR-0039). Re-running the generator that produces them, on a clean
checkout of `main`, writes a **different set** from the one committed: 10 dev cases instead
of 12, with four cases dropped for losing every anchor. A derived artifact that its own
generator does not reproduce cannot be trusted to mean what its provenance says it means —
and this one is scored in CI.

## Environment

- **Affected versions:** ≥ 0.4.0 (observed at `97e599d`, the merge of PR #61)
- **Toolchain / platform:** CPython 3.12.10, Windows 11; the generator builds both corpora
  itself, so no stale local store is involved
- **Configuration:** stock; `[chunking] pack_atomic` at its shipped default (`false`)

## Reproduction

On a clean checkout, with no other change in the tree:

```text
$ git status --short          # clean
$ python tools/build_ingested_cases.py
  dropped anchor  u-0001: docs/concepts/cache.md#cache-directory/0 — best coverage 0.49
  dropped anchor  u-0002: docs/concepts/cache.md#cache-directory/0 — best coverage 0.49
  dropped anchor  u-1008: docs/concepts/projects/dependencies.md#adding-dependencies/ — best coverage 0.48
  dropped anchor  u-1013: docs/concepts/cache.md#cache-directory/ — best coverage 0.49
  dropped case    u-0001 — no anchor survived
  dropped case    u-0002 — no anchor survived
  dropped case    u-1008 — no anchor survived
  dropped case    u-1013 — no anchor survived
carried 10 dev and 14 release cases; 25 anchors mapped, 5 dropped

$ git diff --stat eval/corpora/uv-docs-ingested/eval/
 dev.jsonl     | 4 +---
 release.jsonl | 4 ++--
```

The committed `dev.jsonl` carries `u-0001 … u-0012`; the regenerated one carries
`u-0003 … u-0012`. One release case also moves: `u-1014`'s carried anchor changes from
`…#custom-certificates/0` to `…#custom-certificates/2`.

Reproduced twice on the same tree, and once more with an unrelated change to the *source*
judgements applied — the drops are identical in all three runs, so they are not caused by
whatever else is in the working tree.

## Expected vs. actual

- **Expected:** re-running the generator on an unchanged tree rewrites the committed sets
  byte-for-byte. The sets are derived; the generator is their definition.
- **Actual:** four cases are dropped and one anchor moves. The four dropped anchors sit just
  under the coverage floor (0.48–0.49 against `MIN_COVERAGE`), which is what makes this a
  *drift* rather than an obvious break.

## Root cause

**Not established. Hypothesis, marked as such:** the committed sets were last generated at
roadmap 4.10 (PR #58), and roadmap 4.11 (PR #61) changed `mycelium.chunking`. The carry works
by coverage — it reads the judged passage out of the Markdown corpus's store and finds the
best-covered chunk of the twin document — so both sides of that comparison are chunker
output. A chunker change that moves either side by a few tokens moves the coverage, and four
anchors were sitting within a hundredth of the floor.

What is ruled out: stale local state. `build_ingested_cases.py` builds both corpora itself
before reading them, so the result does not depend on what happened to be in `.mycelium`.

What would confirm it: regenerate the sets with `chunking.py` at `d8a842b` (the commit before
4.11) and compare. That is the first step of the fix and is deliberately not done here — this
record exists so the drift is on the books before someone regenerates the sets for an
unrelated reason and silently ships four fewer cases.

## Impact

Medium. Nothing is wrong *today*: the committed sets are the ones CI scores, and they are
internally valid. The exposure is that the next person to run the generator — for any reason,
including a legitimate re-carry after the source judgements change — will produce a smaller
set and have no way to tell that the shrink is unrelated to their change. Roadmap 4.12 met
exactly that and left the sets untouched rather than absorb it.

The deeper problem is that four anchors sit within 0.02 of the floor, so the derived corpus
is one small chunker change away from losing cases at any time. A floor that fragile needs
either a margin or a different matching rule.

## Fix / workaround

**Workaround (in force):** do not regenerate the ingested sets. They are correct as committed;
`tools/build_ingested_corpus.py --check` still verifies the *documents*, which is the half CI
gates.

**Fix:** filed as roadmap 4.16. Confirm the cause against the pre-4.11 chunker, then make the
carry stable rather than marginal — a recorded coverage score per anchor so drift is visible
in the diff, a documented floor with margin, or a carry that pins the source passage by text
digest instead of recomputing it.

## References

- Fixing PR: —
- `CHANGELOG` entry: —
- Related: [ADR-0039](../../../adr/0039-measure-what-projection-costs.md) (the carry and why
  nothing in it is judged), [ADR-0042](../../../adr/0042-let-an-atomic-block-share-its-chunk.md)
  (the chunker change that is the leading suspect), roadmap 4.10, 4.12, 4.16
