# 2026-09-13 — the index was never carrying anything new (roadmap 5.32)

- **Session scope:** roadmap 5.32 — the journal index stopped being written on 2026-09-10 and
  nothing noticed; decide whether a hand-written index earns its keep before backfilling it.
- **PR:** #131 (`chore/generate-journal-index`). Follows #130, merged as `3e6fa43`.
- **Milestone 5:** 5.32 done.
- **ADR:** [ADR-0103](../../../adr/0103-generate-the-journal-index-because-every-row-already-lives-in-the-file.md).

## The drift, measured before it was fixed

`docs/journal/README.md` listed 69 checkpoints; `docs/journal/2026/**` held 104. Twenty-four
sessions across three days — 2026-09-10 through today, beginning with roadmap 5.1's — had
closed without step 2 of AGENTS.md §7's three-step close: create the file, add a row to the
index, update `ROADMAP.md`'s pointer. Nobody had reason to notice, because nothing compared
the two. `tools/consistency_lint.py` already holds one hand-written index to its files —
`check_adr_index`, every `docs/adr/NNNN-*.md` linked, every link resolved — and had no
counterpart for this one.

## The question the item asked before the fix

5.32's own text refused to let backfilling come first: *does a hand-written index earn its
keep at all, when the filenames already sort by date and carry their slug?* Checking the
tree against itself answered it in about a minute. Every one of the 104 checkpoint files
opens `# <date> — <title>`, and every filename's date prefix agrees with its own heading —
verified across the whole tree, not sampled. The index row for a checkpoint was never a
second fact about it; it was a reformatting of the file's own first line, with a directory
prefix in front. Copying that by hand was never adding information, and the three missed
days prove it: the information was on disk the entire time.

## What changed

`tools/update_journal_index.py` reads every `docs/journal/<YYYY>/<MM>/*.md`, takes each
file's own H1 as the row, and renders `## Index` whole — year, then month, newest first.
The preamble above that heading is the only part of `docs/journal/README.md` a person still
writes. `tools/consistency_lint.py` gains a tenth check, `journal-index`, that shells out to
`update_journal_index.py --check` — one implementation, two callers, the shape ADR-0059
already used for the verification ladder, so a contributor's own run and CI's cannot
disagree about what "current" means.

Two rules follow directly from what the tree can and cannot answer. Newest-first inside a
date breaks by filename, descending, because nothing on disk records which of two sessions
opened the same day happened first — not a timestamp, and deliberately not git history
either, since the generated file has to be reproducible from a clean checkout rather than
from a log. That is a visible change from the previous session-insertion order, and it is
stated as one rather than left for a reader to notice as an unexplained reshuffle. And a
checkpoint the generator cannot read — a malformed heading, a filename date that disagrees
with it — is refused outright rather than silently dropped, because a hole in a generated
file would look exactly like the hole this item exists to close.

## What was not done

No pre-commit hook: this project's enforcement point is the PR boundary, not a local hook.
No sort by git commit date: it would make the file depend on history instead of the tree.
No presence-only lint over a still-hand-written file: measured against the evidence this
session gathered, presence alone would have caught the 24 missing rows but not a row whose
*text* had drifted from its own file, and the text is fully recoverable, so a weaker check
would have been settling for less than the file already allows for free.

## Lesson

A hand-copied fact that already lives one line above where the copy is pasted is not a
second source of truth, it is a second place for the first one to go stale. The fix was not
a stronger check on the copy; it was noticing there was never a reason to copy it.
