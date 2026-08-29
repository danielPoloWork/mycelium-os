## Summary

One or two sentences: what changes and why it matters.

## Motivation

Link to the spec section, ADR, roadmap item, or issue that prompted this work.

## Changes

- bulleted list of meaningful changes (not a file list)

## Design Patterns

- list every pattern adopted/refined/rejected in this PR, with a one-line rationale and a
  link to the ADR.
- if none, write "None — straightforward implementation."

## Verification

- [ ] Builds cleanly on the full CI matrix (Linux / Windows / macOS on CPython 3.12+)
- [ ] Unit tests pass; new/changed behavior covered (≥ 80% line)
- [ ] `ruff format (Black-compatible)` clean; `ruff check + mypy --strict` clean on the diff
- [ ] mypy --strict (type soundness), pytest -p no:cacheprovider under faulthandler, tracemalloc leak checks green (where applicable)
- [ ] Benchmark numbers attached (when perf-relevant)
- [ ] `python tools/consistency_lint.py` passes

## Documentation Impact

- [ ] README.md updated (if user-facing surface changed)
- [ ] ROADMAP.md checkbox flipped
- [ ] ADR added/updated (if a non-trivial design decision was made)
- [ ] docs/patterns/README.md updated (if a pattern was introduced, refined, or rejected)
- [ ] Spec updated (if behavior diverges from `docs/specs/`)
- [ ] CHANGELOG.md updated (for user-visible changes)
- [ ] PR metadata set — assignee (the owner), one type label, release milestone, project (where present)

## Lesson

<!-- Optional, one line. A generalizable rule the next contributor should inherit — captured
here at review time, while the knowledge is hot and the human gate is already open. Squash-merge
takes this PR body as the permanent commit on `main`, so a merged lesson is
owner-approved by construction. Write "none" if there is nothing durable to carry forward. -->

Lesson: none
