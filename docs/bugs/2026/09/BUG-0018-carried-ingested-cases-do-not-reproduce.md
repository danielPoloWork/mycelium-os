---
id: BUG-0018
title: the carried ingested judgements do not reproduce from their own generator
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-02
affected-versions: ">=0.4.0"
fixed-in: 0.4.0
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

**Established at roadmap 4.16, and it is not what this record first suspected.**

The original hypothesis — that 4.11's chunker change moved the coverage — is **disproved by
measurement**. Chunking both corpora with `chunking.py` at `d8a842b` (before 4.11) and at
`HEAD`, with `pack_atomic` at its shipped default, produces **identical output**: 2244 chunks
across `uv-docs` and 2073 across `uv-docs-ingested`, and *zero* documents differ in anchors,
text or kind. With packing off the change is a no-op, exactly as ADR-0042 claimed.

The real cause is the thing this record explicitly ruled out, and the reasoning that ruled it
out was wrong. `build_ingested_cases.py` does call `build()` on both corpora — but `build()`
is **incremental**. It recompiles what `doc_state` says is dirty, and a chunking *policy* that
did not arrive through `mycelium.toml` leaves nothing dirty to notice. Roadmap 4.11's
measurement session had built `uv-docs` with `pack_atomic` forced on from code; that store
(gitignored, disposable, and therefore invisible) survived on disk, and the carry then read
**packed** judged text — 568 chunks instead of 2244 — while scoring it against the twin's
**unpacked** chunks. Coverage collapsed, and four anchors sitting within 0.02 of the floor
went under.

Confirmed by removing both `.mycelium` directories and re-running: the generator then
reproduces the committed sets exactly, dropping only the anchors the committed sets already
record as dropped.

So the defect generalises past this tool: **a generator that derives a committed artifact
from an incremental build inherits whatever the local store happens to hold, and records the
machine rather than the corpus.**

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

Fixed at roadmap 4.16, in three parts:

1. **Both builds are `clean=True`.** The generator no longer inherits ambient derived state,
   so its output is a function of the committed corpora and nothing else.
   `tools/build_uv_docs_cases.py` gets the same treatment for the same reason — it also
   compiles its corpus in place.
2. **`--check` regenerates and compares**, and runs in CI beside
   `build_ingested_corpus.py --check`. The corpus check proves the *documents* still match
   their sources; this one proves the *judgements* still derive from them. Proved to fail by
   mutating one recorded coverage value and watching it name the file.
3. **The carry now leaves a receipt.** `eval/corpora/uv-docs-ingested/eval/carry.json` records
   every mapped anchor's twin and coverage, so drift shows up as a diff of numbers rather
   than as a case that quietly vanished — which matters because three anchors legitimately
   map between 0.42 and 0.49 against a 0.50 floor.

`MIN_COVERAGE` is deliberately **not** widened. It is a floor below which "the same passage"
stops being a defensible claim, not a dial; moving it so that marginal anchors survive would
be fitting the threshold to the data.

## References

- Fixing PR: #63
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [ADR-0039](../../../adr/0039-measure-what-projection-costs.md) (the carry and why
  nothing in it is judged), [ADR-0042](../../../adr/0042-let-an-atomic-block-share-its-chunk.md)
  (the chunker change that is the leading suspect), roadmap 4.10, 4.12, 4.16
