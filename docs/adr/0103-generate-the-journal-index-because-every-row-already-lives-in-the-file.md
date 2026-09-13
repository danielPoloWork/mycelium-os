# ADR-0103: Generate the journal index, because every row it holds already lives in the file it links to

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per AGENTS.md §7
- **Related:** [ADR-0001](0001-record-architecture-decisions.md) (why a decision like this gets
  a record at all), [ADR-0059](0059-make-the-plan-one-implementation-too.md) ("one implementation,
  two callers" — the shape this reuses); AGENTS.md §7; roadmap 5.26 (where the drift was
  noticed), 5.32 (where it was fixed)

## Context

`docs/journal/README.md` listed 69 checkpoints on 2026-09-13; `docs/journal/2026/**` held
104. Twenty-four sessions across three days — beginning with roadmap 5.1's, on 2026-09-10 —
had closed without step 2 of AGENTS.md §7's three-step close: *create the file, add a row to
the index, update ROADMAP's pointer*. Nothing caught it. `tools/consistency_lint.py` already
holds one hand-written index to its files — `check_adr_index`, checking that every
`docs/adr/NNNN-*.md` is linked and every link resolves — and has no counterpart for this one,
which is exactly why every PR across those three days could skip the row without a single
red tick (found at roadmap 5.26 while adding one; filed as 5.32).

The item that found it named the real question before naming the fix: *does a hand-written
index earn its keep at all, when the filenames already sort by date and carry their slug?*
Checking the tree against itself answered it. Every checkpoint file's own first line is
`# <date> — <title>`, and every one of the 104 files matches that shape with the date it
also carries in its filename (verified across the whole tree before writing a line of this
ADR). The index row for a checkpoint is not a second fact about it — it is a formatting of
the first line the file already has, with a directory prefix. A person copying that row by
hand was never adding information; the file already had the row, one line above where the
copy usually went missing.

## Decision

**The index is generated, not hand-written.** `tools/update_journal_index.py` reads every
`docs/journal/<YYYY>/<MM>/*.md`, takes each file's own H1 as the row's date and title,
and renders the `## Index` section whole — grouped by year, then month, newest first. The
preamble above that heading is the only part of `docs/journal/README.md` a person still
writes; step 2 of the close is now *run the generator*, not *copy a row*.
`tools/consistency_lint.py` gains a tenth check, `journal-index`, that shells out to
`update_journal_index.py --check` and fails by name when the committed file does not match
what a fresh run would produce — the same "one implementation, two callers" shape ADR-0059
used for the verification ladder, so what a contributor's own run says and what CI decides
cannot drift from each other, because they are the same run.

**Newest-first is the only ordering the tree can support without inventing one.** Two
sessions opened on the same date have no signal on disk that says which came first — no
timestamp anywhere records it, and git history is not read here, deliberately (the index
must be reproducible from a clean checkout, not from a log). So a same-date tie breaks by
filename, descending: the same rule a directory listing gives for free. This is a visible,
disclosed change from the file's previous order, which followed session sequence rather than
any rule recoverable from the tree — the honest trade is a rule anyone can verify over one
nobody could reproduce.

**A checkpoint the generator cannot read is refused, not skipped.** A first line that is not
`# <date> — <title>`, or a date that disagrees with the one the filename carries, raises
rather than silently dropping the file from the index — the failure mode a generator must
never have is one where a bad file quietly stops being indexed, because a hole in a
generated file looks exactly like a hole in a hand-written one and the whole point was to
stop looking for holes by hand.

## Alternatives Considered

- **Drop the index for a directory listing.** The other answer the roadmap item itself named
  as making drift impossible. Rejected: the index's date-title link text reads better inline
  in a document than a bare filename does, and a generated file costs nothing extra to keep
  once it is generated rather than copied — dropping it trades a solved problem for a worse
  reading experience, for no remaining benefit.
- **Keep it hand-written, add a presence-only lint** (mirroring `check_adr_index`: every file
  linked, every link resolves). Rejected on the evidence this session gathered: presence
  would have caught the missing 24 rows, but not a row whose *text* had drifted from its
  file's own heading — and since the text is fully recoverable from the file, a check that
  tolerates drifted text is weaker than the file already allows for free.
- **A pre-commit hook that regenerates on every commit.** Rejected: it writes files a
  developer did not ask for mid-edit, and this project's enforcement point is the PR
  boundary (`tools/verify.py`, `tools/consistency_lint.py`), not a local hook nobody is
  required to install.
- **Sort by git commit date instead of filename.** Would recover same-day ordering. Rejected:
  it makes the generated file depend on history rather than on the tree, so two clean
  checkouts of the same commit could render differently depending on how they got there
  (a rebase, a shallow clone) — the opposite of what a generated, checked file is for.
- **Backfill the 24 missing rows by hand, now, and decide the generation question later.**
  The item's own text refused this ordering: backfilling before deciding whether a
  hand-written index earns its keep would have been work the decision might have thrown
  away. Deciding first made the backfill free — it is every row generation now produces.

## Consequences

- `docs/journal/README.md` is regenerated wholesale; its `## Index` section is now
  byte-for-byte what `tools/update_journal_index.py` produces, and the 24 missing rows (and
  every row's exact text) are restored as a side effect of generating rather than as a
  separate backfill.
- The visible ordering changed for entries sharing a date, from insertion order to filename
  order, disclosed above rather than left for a reader to notice as an unexplained reshuffle.
- `tools/consistency_lint.py`'s congruence checks go from nine to ten; `journal-index` runs
  in every mode `docs` upward, at the cost of one subprocess call.
- AGENTS.md §7's close is unchanged in shape — create, index, point ROADMAP — the middle step
  changes from a manual copy to `python tools/update_journal_index.py`, which cannot be typed
  wrong in a way that produces a wrong row, only in a way that produces no row (a missing
  run), which the lint catches.
- A checkpoint filename must keep carrying its own date, and its H1 must keep the
  `# <date> — <title>` shape, or the build of the index refuses rather than guesses — this
  was already every checkpoint's practice, so nothing already committed needed to change to
  satisfy it.

## References

- AGENTS.md §7 (documentation maintenance, the three-step close).
- `tools/update_journal_index.py` (the generator, `--check` mode); `tools/consistency_lint.py`
  `check_journal_index` (the tenth congruence check).
- Precedent: `tools/build_ingested_cases.py --check` (a generated artifact checked against
  its own generator); [ADR-0059](0059-make-the-plan-one-implementation-too.md) ("one
  implementation, two callers").
- Tests: `tests/test_journal_index.py`; `tests/test_consistency_lint.py`.
