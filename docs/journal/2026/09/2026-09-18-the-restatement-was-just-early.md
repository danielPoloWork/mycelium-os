# 2026-09-18 — the restatement was just early (roadmap 6.10)

- **Session scope:** roadmap 6.10 — close the gap ADR-0072 left in this repository's own
  corpus scope.
- **PR:** #160 (`docs/exclude-root-changelog-from-corpus`), following #159, merged.
- **Milestone 6:** still open. 6.10 delivered; 6.8, 6.12–6.15, 6.17–6.23 remain.
- **Decision it records:** [ADR-0125](../../../adr/0125-exclude-the-root-changelog-because-unreleased-is-the-restatement-early.md),
  amending [ADR-0072](../../../adr/0072-keep-our-own-restatements-out-of-our-own-benchmark.md).

## What the item actually asked

6.10 named the gap plainly — `docs/changelog` and `docs/releases` left the corpus at 4.44, and
the root `CHANGELOG.md` did not, even though `[Unreleased]` holds exactly the same entries a
release moves into `docs/changelog` verbatim. What it did not do was let the "obvious answer"
stand unexamined: it asked whether `[Unreleased]` is genuinely the same restatement, or whether
the honest fix is narrower — sparing the "Released versions" index table at the foot of the
file, which is navigational rather than restated prose.

The answer, on inspection, is that ADR-0072 had already had this argument and refused it, at a
much larger size differential. It considered excluding only `docs/changelog` (1,091 lines) and
keeping `docs/releases` (~95 lines) and called that "a distinction without a principle." The
"Released versions" table here is perhaps fifteen lines. Building a section-level exclusion
mechanism to spare that much content — content that is nearly worthless to a term-counting
baseline in either direction — is disproportionate to what an `XS` item should cost, and the
file-level mechanism already exists and already applies.

## What was measured, and how

Built `.` with `--no-pin --clean` (195 documents), scored `dev.jsonl` and `release.jsonl`
against grep, added `CHANGELOG.md` to `[project] exclude`, rebuilt (194 documents), scored
again. The maintainer's untracked `docs/analysis/`, `fable-review.md` and `.claudeignore` were
moved out of the tree before either build and restored after — the same discipline the
2026-09-14 rebless session needed, for the same reason: a corpus measurement is a claim about
what is actually committed, and local WIP is not that.

Our own score did not move — identical to the fifteenth decimal on both sets, both before and
after. Grep's moved up on both: nDCG@10 0.2379 → 0.2433 on `dev`, 0.2221 → 0.2303 on `release`.
Same signature ADR-0072 read, same direction — a release stops widening our reported lead for a
reason that has nothing to do with retrieval — smaller in absolute terms because today's
`[Unreleased]` is shorter than the ~1,000-line block v0.4.0 moved out at release.

`python tools/measure_hybrid_gate.py --check` confirmed gate G2's recorded verdict is
unaffected — it fingerprints `retrieval.py`'s constants, which this change never touches.

## What this PR deliberately did not do

Re-bless `eval/baselines/release.json`. ADR-0072's own PR (4.44) reblessed within the same
change, because no other cadence existed at the time. ADR-0112 has since established that
`ours/release` is reblessed once per release, as its own PR, dated to the corpus a release is
actually cut from (`docs/workflow/release.md` step 0). Following the older habit here — reblessing
because a prior ADR did — would be reaching for what an earlier record did rather than what
governs now, which is close to the mistake ADR-0113's own addendum caught in a different shape
three days ago. Gate G3 reports the corpus as not comparable until the next scheduled rebless;
that is the gate behaving exactly as ADR-0053 designed it to on a corpus this repository writes
about itself.

## Lesson

An ADR that excludes two of three siblings and stops is a claim with an edge nobody drew on
purpose — `docs/changelog` and `docs/releases` are the *destination* of a restatement,
`[Unreleased]` is the same restatement in transit, and a rule keyed on the destination misses
the transit every time until someone reads the workflow doc closely enough to notice the entries
are the same text. The fix was small; noticing it required reading what the release procedure
actually does to the file, not what its name suggests.
