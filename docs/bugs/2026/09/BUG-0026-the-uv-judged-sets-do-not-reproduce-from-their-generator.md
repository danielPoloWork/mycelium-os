---
id: BUG-0026
title: the second corpus's judged sets do not reproduce from their generator, and running it deletes ten cases
status: fixed
severity: high
reporter: internal
discovered: 2026-09-13
affected-versions: ">=0.5.0"
fixed-in: 0.5.0
---

# BUG-0026: the second corpus's judged sets do not reproduce from their generator, and running it deletes ten cases

## Summary

`tools/build_uv_docs_cases.py` is the only home of the second corpus's judgements: it holds
them as `DEV`/`RELEASE` tuples, validates every anchor against a real build, and writes
`eval/corpora/uv-docs/eval/{dev,release}.jsonl`. Two pull requests edited the committed
`dev.jsonl` **without** updating the generator, so from 2026-09-08 the generator held twelve
dev cases while the committed set held twenty-two. Running it — for any reason, including the
legitimate re-judgement this was found by — silently deleted ten judged cases and reverted one
re-judgement, and nothing in the test suite or CI would have said so.

This is [BUG-0018] on the other side of the same pair. That one was the *derived* carry not
reproducing; it was fixed with a `--check` in CI. The *source* set had no such check, so the
carry kept reproducing faithfully while the thing it was carried from drifted.

## Environment

- **Affected versions:** ≥ 0.5.0 — the drift is present at `f690e18` (the tip of `main` when
  this was found) and dates from PR #90, merged 2026-09-08
- **Toolchain / platform:** CPython 3.12.10, Windows 11; the generator builds the corpus
  itself with `clean=True`, so no stale local store is involved
- **Configuration:** stock

## Reproduction

On a clean checkout of `main`, with nothing else in the tree:

```text
$ python tools/build_uv_docs_cases.py
wrote 12 dev and 25 release cases to .../eval/corpora/uv-docs/eval

$ git diff --stat eval/corpora/uv-docs/eval/
 dev.jsonl | 12 +-----------
 1 file changed, 1 insertion(+), 11 deletions(-)
```

Ten cases are gone — `u-0013` … `u-0022` — and `u-0006`'s note and grades revert to the
version ADR-0065 superseded. Counted directly rather than inferred:

| | cases |
|---|---:|
| `DEV` in `tools/build_uv_docs_cases.py` at `f690e18` | 12 |
| committed `eval/corpora/uv-docs/eval/dev.jsonl` | 22 |

`release.jsonl` is unaffected: every release judgement did go through the generator.

## Expected vs. actual

- **Expected:** the generator is the judgements' definition, so re-running it on an unchanged
  tree rewrites the committed sets byte-for-byte — the property `build_ingested_cases.py` and
  `build_eval_cases.py` both have and are both checked on.
- **Actual:** it silently discards every judgement that reached the set by any other route.

## Root cause

Two hand edits to a generated file, and no check that would notice.

`u-0006` was re-judged in PR #88 (roadmap 4.37, ADR-0065) and ten dev cases were added in
PR #90 (roadmap 4.39). Both edited `eval/corpora/uv-docs/eval/dev.jsonl` directly. The
generator's last change was PR #85. Nothing compared them, and the sets are not *derived* in
the sense the carry is, so the absence of a check was never obvious:

| generator | reproduction checked by | drifted |
|---|---|---|
| `tools/build_eval_cases.py` (our own corpus) | a test — `tests/test_eval.py` asserts it writes exactly what is committed | no |
| `tools/build_ingested_cases.py` (the carried twin) | `--check`, in CI and in `tools/verify.py` ([BUG-0018]) | no |
| `tools/build_uv_docs_cases.py` (the second corpus) | **nothing** | **yes** |

The one generator nobody checked is the one that drifted, which is about as clean a natural
experiment as this repository is likely to get.

## Impact

High, and the severity is about what *would* have happened rather than what did. Nothing was
wrong in the committed artifacts: `dev.jsonl` holds twenty-two correctly judged cases and CI
scored those. The exposure is that the next person to touch a judgement — exactly what roadmap
5.30 set out to do — regenerates, loses ten cases, and has no signal that the loss is
unrelated to their change. It was found by that person doing that, and the loss was noticed
only because `git diff --stat` printed a file nobody had meant to touch.

`uv/dev` is the set roadmap 4.39 grew specifically so that a field-weight question could have
an interior optimum (ADR-0070). Losing ten of its twenty-two cases would have reverted that
capability silently, and the next tuning decision taken against the smaller set would have
been taken against evidence that no longer existed.

## Fix / workaround

Fixed at roadmap 5.30, in two parts:

1. **The generator is re-synchronised with the committed set, mechanically.** The ten cases
   and the re-judged `u-0006` were transcribed back into `DEV` *from `dev.jsonl` itself* by a
   script, never by hand, and the result is proved by regenerating and byte-comparing against
   the committed file. No judgement changed: `dev.jsonl` is untouched in the fixing commit.
2. **`--check` regenerates and compares instead of writing**, the same shape
   `build_ingested_cases.py` has, wired into `tools/verify.py` at `code` and into CI's
   `ingest / lanes` job beside the carry check it is the upstream half of. It is 10 s.

The failure message says what to do rather than what happened, because the trap is that
regenerating *looks* like the fix: it names the file, states that a hand-edited case is
invisible to the generator and that the next run deletes it, and asks for the judgement to be
moved into `DEV`/`RELEASE` first.

**Not done, deliberately:** nothing prevents a hand edit. A judged set is a text file and
making it unwritable would be theatre; what matters is that a hand edit cannot survive
unnoticed, and now it cannot.

## References

- Fixing PR: #129
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [BUG-0018](BUG-0018-carried-ingested-cases-do-not-reproduce.md) (the same defect on
  the derived side, and the `--check` this copies),
  [ADR-0101](../../../adr/0101-let-the-exact-slice-name-the-section-that-documents-the-literal.md)
  (the re-judgement that triggered it), [ADR-0065](../../../adr/0065-one-section-cannot-document-two-commands.md)
  and roadmap 4.37/4.39 (the two hand edits), roadmap 5.30
