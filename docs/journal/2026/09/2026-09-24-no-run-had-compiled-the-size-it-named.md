# 2026-09-24 — no run had compiled the size it named (roadmap 7.6)

- **Session scope:** roadmap 7.6 — the reference profile generates a corpus other than the
  one it names (BUG-0034, BUG-0035). Fix both, and publish the before and after at one
  commit so the benchmark series says where its corpus changed.
- **PR:** #198 (`fix/generate-the-corpus-the-profile-names`). Follows #197, merged as
  `df43af8`.
- **Milestone 7:** 7.6 closed. 7.1 held at its trigger, 7.2 held at its three, 7.7 open.
- **Decision it records:** none new — two bug records and a benchmark report. The
  refusal-not-skip shape is ADR-0118's and ADR-0154's, applied to a generator.

## The fix was small; the reading of the old manifests was the finding

Two constants and one helper: the source path that never existed, a title written as a JSON
string so YAML reads it whole, and `compiled_all`, which refuses a run whose build compiled
fewer documents than were generated. Before deciding whether the last of those was worth
its lines I read every published manifest's `scales[].documents`. Not one had compiled the
size it named: 998 of 1 000 in the 2026-09-17 profile, whose prose says *at exactly the
stated size*; 249 of 250 in today's before run at the profile's own default seed. The budget
spec 01 §8 states at 1 000 documents had never been measured at 1 000. Two tenths of a
percent moves no conclusion, and the sentence still had to be written where the numbers
are.

## Publish the discontinuity, not a comparison

The temptation with a before/after table is to read it: 20.4 → 18.0 s at 250, 67.2 →
70.9 s at 1 000. Both are single cold samples over two corpora of different composition on a
machine with an 8 % noise floor, and the compiler did not change between them. The report
says that first and puts the table second. What is real in it is the break: `corpus.sources`
in every manifest before today lists a path that did not exist, and from today lists the
one that does.

## The before run needed the old code, not just the old tree

`--harvest-root` arrived with the fix, so the before run could not be pointed at the export;
it had to run from a worktree of `df43af8` with its own environment, harvesting its own
clean `docs/`. Same commit, same seed, same hour, machine idle — and the two manifests'
`commit` fields are identical on purpose, because the generator is not the commit's.

## What the next session should know

- **Every earlier reference-profile number is a measurement of `docs/`-only prose.** Do not
  compare a new run's corpus figures with a manifest that lists
  `eval/corpora/uv-docs/knowledge`; take the pair from the same side of the break.
- **The 10⁵-chunk query profile is also a different corpus now** — `--query-scale` writes
  from the same harvested blocks. Its next number will not match the last, and this report
  is why.
- **`compiled_all` will stop a run that quarantines a document.** That is the intent; a
  new hostile heading shape is a bug to record, not a check to loosen.
