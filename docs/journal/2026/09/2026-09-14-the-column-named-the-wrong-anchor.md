# 2026-09-14 — the column named the wrong anchor (roadmap 5.39)

- **Session scope:** roadmap 5.39 — `u-1019` is the other large negative on the twin, and its
  split passage sits on an anchor graded **1**. Does a split on a grade-1 anchor move a case at
  all, or is the 0.509 a coincidence the new column invites a reader to over-read?
- **PR:** #138 (`fix/read-u-1019-split`). Follows #137, merged as `5e0e02e`.
- **Milestone 5:** 5.39 done; 5.41 filed.
- **ADR:** [ADR-0109](../../../adr/0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-half-the-reading.md),
  narrowing a clause of [ADR-0102](../../../adr/0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md).

## Read before concluding, which is what the item asked for

| | anchor | source rank | twin rank | alone, source | alone, twin |
|---|---|---:|---:|---:|---:|
| grade 3 | `python-versions.md#requesting-a-version/python-version-files/0` | 2 | **10** | 0.6309 | **0.2891** |
| grade 1 | `features.md#python-versions/0` | 1 | **1** | 1.0000 | **1.0000** |

The grade-1 anchor — the one that split, the one carrying the lowest `whole` of any scored case
— is **first on both corpora** and scores a perfect 1.0000 alone on each. It cost nothing. Every
point of `u-1019`'s −0.314 belongs to the grade-3 anchor falling eight places, and that anchor's
share is 0.836, which appears nowhere in the table.

Why the split was harmless is legible once both chunks are read. The HTML lane made one heading
per feature line, so the twin chunk is headed `uv python pin: Pin the current project to use a
specific Python version` — the query, verbatim, in a weighted field. Half the passage's word
occurrences went next door; the half that stayed is the half the query names.

## The finding is about the column, not the number

The per-case mark is a `min` across a case's anchors with no grade attached. Where the grades
differ it therefore reports the *worst split*, which is not necessarily the one that moved the
score — and for `u-1019` those are two different anchors. ADR-0102's supporting sentence,
"the two largest negatives are the two lowest shares", is numerically true and, on one of its
two cases, a coincidence.

It is not noise, and the same table is what says so: `u-1004`'s 0.895 *is* on its grade-3 anchor,
and that case went to 0.000. The mark means opposite things depending on which anchor carries it,
and that was exactly the thing it did not print. It prints it now — `0.509@1`, `0.895@3` — and the
two largest negatives stop looking like a pattern.

## The other half of the item found something real

5.39 also said to note `features.md#the-pip-interface/0`, carrying at 0.338, "on a dev case
nobody has read either". Read: `u-0017`, query `uv venv`. Its grade-1 anchor is carried onto a
twin chunk headed `uv pip compile: Compile requirements into a lockfile`, whose text is the
pip-compile/pip-sync pair. It **does not contain the string `uv venv`**.

The correct chunk is in the same document, under the same heading slug (`#the-pip-interface/0`),
and holds `uv venv: Create a new virtual environment.` It scores coverage **0.4731** — below the
0.50 floor — against the wrong chunk's **0.5269**. The floor sits between them, and the right
answer is the one it drops.

The mechanism is that coverage counts *distinct* tokens. A feature list's vocabulary is `uv`,
`pip`, `install`, `packages`, `environment` repeated, so the single token that distinguishes the
passage — `venv` — is worth no more than the scaffolding, and the scaffolding decides. On the
twin the grade-1 anchor is never retrieved at all (rank >50) while the chunk that should have
been it sits at rank 5, unjudged. As carried the case reads 0.5788 against its source's 0.6201;
carried correctly it reads 0.6295. All of its apparent projection cost is the mis-carry.

ADR-0102's own last bullet had already pointed at this anchor — "the closest mapped anchor is
0.5269", named as *a cliff a reviewer should be able to see rather than discover*. This is the
first time anyone went and looked over it.

Filed as roadmap 5.41 rather than fixed here: it edits the twin's judged set, which re-blesses
both baselines and re-records gate G2 through `cases_digest`, and a judgement change never rides
with anything else.

## Lesson

An aggregate over things of different kinds has to say which kind it picked. `min(whole)` across
anchors graded 3 and 1 is a number about the *passage* being read as a number about the *score*,
and the two coincide often enough that the column looked right for two milestones. The item that
caught it did so by asking for ranks instead of accepting the correlation — and the same read,
applied to the one number nobody had followed up, turned up a judged anchor pointing at the wrong
command.
