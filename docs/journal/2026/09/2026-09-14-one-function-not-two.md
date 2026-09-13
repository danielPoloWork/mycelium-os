# 2026-09-14 — one function, not two (roadmap 5.38)

- **Session scope:** roadmap 5.38 — `encode_cases` has been written twice, in two case
  generators, each docstring saying it is "deliberately the same one-liner as the writer".
  Move it to `mycelium.eval.cases`, beside `write_cases`, so the two cannot disagree.
- **PR:** #137 (`refactor/dedupe-encode-cases`). Follows #136, merged as `8fdd8ce`.
- **Milestone 5:** 5.38 done.

## What moved, and what did not

`encode_cases` now lives once, in `mycelium.eval.cases`, and `write_cases` calls it instead of
rendering its own bytes — so the function a `--check` compares against and the function a
write actually uses are, by construction, the same function. Both private copies
(`tools/build_ingested_cases.py`, `tools/build_uv_docs_cases.py`) are deleted; both tools
import the shared one. Neither call site needed to change beyond the import.

Verified rather than assumed: `tools/build_uv_docs_cases.py --check` and
`tools/build_ingested_cases.py --check` both still report a byte-for-byte reproduction after
the move. No judged set, baseline, verdict or golden moves.

## Why this was blocked at 5.30 and isn't now

`mycelium.eval.cases` is a `TUNING_PATHS` entry, and at 5.30 the same PR that would have moved
this function also re-judged a frozen release set — a combination
`tools/check_frozen_release_sets.py` refuses outright. This PR touches only the shared module
and the two tools, carries no judgement change, and the guard has nothing to say about it.

## No ADR

No two reasonable options with a non-obvious rationale, no pattern adopted, nothing
superseded — the item's own text already said where the function belongs and why. Recording a
decision that was never in question would be noise the next reader has to filter out.

## Lesson

A docstring that argues for its own deletion — "this is deliberately the same as the other
copy" — is a roadmap item waiting to be filed, and 5.30 filed this one the moment the second
copy made the pattern visible.
