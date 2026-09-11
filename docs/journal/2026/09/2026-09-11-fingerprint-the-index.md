# 2026-09-11 — the fingerprint that watched the wrong thing (roadmap 5.12)

- **Session scope:** roadmap 5.12 — stop a build-side table from staling gate G2's verdict
  (spec 04 §7.3; ADR-0064, ADR-0068).
- **PR:** #111 (`fix/fingerprint-the-index-not-the-store`). Follows #110, merged as `dfed09b`.
- **Milestone 5:** 5.12 done. 5.13–5.19 and 5.21 open.
- **ADR:** [ADR-0084](../../../adr/0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md).

## One field, wrong since it was written

`retrieval_identity()` dates gate G2's recorded verdict: the verdict compares hybrid against
the lexical leg, and it is only about the shipped product while that leg is the one that
ships. Its field named `fts_schema` held `SCHEMA_VERSION` — the version of the *whole store*.
The name said index; the value said database.

Roadmap 5.4 put a price on the difference. It added `entities`, a table no query reads. The
DDL policy bumps the store version on any schema change at all, so the version moved, the
fingerprint moved, `eval/g2-verdict.json` went stale, and `--check` failed until the verdict
was re-recorded. Re-recording needs the embedding model, which CI does not have by design
(D-013), so a table addition had quietly become a task only a machine with a 133 MB download
could finish — for a ranking that had not changed by one digit.

## Why narrowing is safe here, which is not usually true

Narrowing a guard is the move to be suspicious of, and the item was right to say so: doing it
inside the PR whose CI it inconveniences is how a guard becomes a formality. So the argument
had to be that the narrowing loses nothing, not that it is convenient.

It does lose nothing, and the reason is an ordering rather than a judgement. The store's
version bumps on *every* schema change, including every change to `chunks_fts`. So the version
is strictly coarser than the statement: nothing that moves the statement can fail to move the
version, and plenty that leaves the statement alone moves the version anyway. Dropping to the
statement removes false positives and cannot create a false negative.

The check is in the tests rather than in that paragraph. Mutate `chunks_fts` four ways — add
an indexed column, change the tokenizer, change the prefix index, un-`UNINDEXED` a column —
and the fingerprint moves each time. Append a whole new table to the DDL and it does not.

## Two smaller decisions

**Normalised rather than verbatim.** Comments are stripped and whitespace collapsed before the
statement is digested, because the paragraph above `chunks_fts` explains *why* its columns
exist and rewording it is not a ranking change. That is ADR-0014's rule — digest the resolved
settings, not the file bytes — applied one layer down.

**The bound is written down.** The query path also reads `chunks`, `documents`, `vectors`,
`symbols` and `edges`, and none of them is fingerprinted. They supply filter predicates and
result fields, not term statistics, so their column lists decide what a result *carries* and
not what order results come in. Fingerprinting them was the first design and it was dropped
for re-creating the problem in a smaller form: adding a column to `documents` that nothing
selects would stale a retrieval verdict again.

## The one thing the fix costs

One more re-record, here, because the field's *value* changes even though nothing it describes
did. The item asked that the four vendored rows reproduce byte-identically as the check; what
came back is stronger. **Every score on all six sets reproduced byte-identically**, this
repository's own included, and the whole diff of `eval/g2-verdict.json` is three lines: the new
fingerprint, and the self-hosting corpus's two digests, which moved because this change adds two
documents to it. Not one measured number moved — which is exactly what a fingerprint change that
describes nothing new should look like.

## Lesson

A fingerprint is only as honest as its narrowest field, and the field to distrust is the one
whose *name* is narrower than its *value*. `fts_schema` holding a store version read as
correct for four milestones because nobody compared the two words. The general form: when a
guard fires on something it should not, check whether it was ever watching the thing its name
claims — and if the fix is to narrow it, prove the narrowing is a strict subset before
shipping it, not after.
