# 2026-09-02 — the unit was the bug (roadmap 4.11)

- **Session scope:** roadmap 4.11 — make the chunk a comparable unit; the hypothesis left
  standing after ADR-0031 and ADR-0041 refused ten re-rankings.
- **PR:** #61 (`feat/pack-atomic-blocks`). Follows #60 (4.8's second refusal), merged as
  `7fa75c1`.
- **Milestone 4:** 4.1–4.7, 4.9–4.11 done; **4.8 still open**, and 4.12–4.15 filed out of
  this item.

## The diagnosis was half right

Two ADRs blamed code fences: "a three-token code fence containing the query term has maximal
term density, so it wins". Counting the chunk population before writing anything said which
half of that was true.

On the second corpus 47 % of chunks are under 25 tokens. Only 450 of those 1055 are code —
**605 are prose.** And they are not short paragraphs, they are *offcuts*: **93 % of them sit
directly beside a code or table chunk**, because an atomic block interrupts a prose run and
closes the chunk on both sides. A section reading "paragraph, command, paragraph" becomes
three chunks, two of them fragments the author never wrote as separate thoughts.

They did not need splitting at all. **97 % of that corpus's multi-chunk sections would fit
whole inside a single 800-token chunk.** The chunker was not splitting oversize sections; it
was splitting ordinary ones, because a code fence ended the run.

That reframes the fix. It is not "merge short fragments", which is how the roadmap phrased it
and which needs a threshold — the thing ADR-0031 refused the length prior for. It is one
sentence: **atomicity means indivisible, not solitary.** Deleting the special case needs no
number at all.

## What it bought

| corpus | packing | chunks | median | < 25 tokens |
|---|---|---:|---:|---:|
| ours | atomic | 888 | 90 | 11.6 % |
| ours | packed | 702 | 117 | 7.4 % |
| uv | atomic | 2244 | 27 | 47.0 % |
| uv | packed | **568** | 136 | **8.8 %** |

(The `ours` rows moved while this file was being written — the repository is its own corpus.
The `uv` rows are frozen, which is why the argument rests on them.)

| set | atomic | packed |
|---|---:|---:|
| ours/dev | 0.536 | 0.491 |
| ours/release | 0.472 | 0.473 |
| uv/dev | 0.403 | **0.561** |
| uv/release | 0.280 | **0.451** |

uv/release **+61 %**, against the incumbent's 0.471, with **no slice regressed** —
`conceptual` +49 %, `exact` 0.000 → 0.500, `fact` +11 %, `relationship` +49 % — and R@10
0.500 → 0.679. After ten refusals in two ADRs, the first change that moves the corpus 4.8 is
about was a change to the unit, not to the ranking.

## Why it ships off

Because moving a boundary **deletes an anchor**, and the flip and the re-anchoring may not be
the same change.

| set | judged anchors kept | needs re-anchoring |
|---|---|---|
| ours/release | **16 / 16** | none |
| uv/dev | **12 / 12** | none |
| uv/release | 17 / 18 | u-1016 |
| ours/dev | 29 / 33 | q-0002, q-0008, q-0013, q-0016 |

**This is ADR-0029 paying for itself.** It argued that a judged set "survives a chunking
change to the extent it uses section anchors", and 3.17 scoped to sections wherever a section
was what the judgment meant. ADR-0029 shipped two days ago and nothing had tested that claim; this is the first chunking
change since, and the release sets come through nearly untouched — 16/16 on ours. An argument
that read as a nicety turned out to be the thing that makes 4.12 affordable.

Five cases still need re-anchoring, and the frozen-set guard refuses a PR that edits a
release set while touching the chunker. That is the point rather than the obstacle: ADR-0031
rejected "re-judge so the change passes" outright, and 4.11's own text says re-judge nothing
in the same change. So the mechanism lands measured and inert, **4.12** re-anchors from
the documents, and **4.15** flips the default. Two items, because 4.12 edits a frozen release
set and 4.15 edits the chunker — the same conjunction the guard refuses. Same shape as
ADR-0029 → 3.17, which worked for the same reason: the second change can be argued from
documents instead of from a ranking.

The one regression is the case ADR-0041 already refused `section-open` over. For
`Conventional Commits` the top result becomes AGENTS.md's own section on the rule — the
contract this repository calls its source of truth — while the judged copy in
`docs/workflow/git-workflow.md` drops to rank two. Both anchors survive; the judgment names
two of the three places the rule is documented and omits the authoritative one. That is a
judgment to revisit on the documents, in 4.12, not beside a ranking.

## A gate that cannot see this change

Both release runs reported instead of enforcing, and the reason is structural: **gate G3
compares per-slice scores only when the corpus digest matches, and that digest is folded from
chunk digests.** Any change to chunk boundaries trips the "corpus has changed" branch
[BUG-0014] added for a good reason.

So the gate meant to catch a bad chunking change is blind to chunking changes by
construction, and 4.15's flip has no gate to clear. Filed as **4.13** with three options and
no free one.

A smaller hole turned up while splitting the follow-up, and it is closed here rather than
filed: the shipped default now lives in `ChunkingConfig`, so `config.py` can move the
retriever, and it was not one of the frozen-set guard's `TUNING_PATHS`. A single change could
have flipped the default *and* re-judged a release set unrefused. One line, and the
4.12 / 4.15 split is now enforced by the machine instead of by an ADR paragraph.

## Where this leaves 4.8

Closer than ten re-rankings got it, and still open. 0.451 against grep's 0.471 on the corpus
that has been losing since M3 — and the 3 % the section unit could not deliver (ADR-0041's
bound) is roughly the gap that remains. 4.8 closes when 4.15 flips the default and the
numbers hold, or it does not, and either way the next move is 4.12 rather than an eleventh
re-ranking.

One papercut worth recording because it cost time twice: `mycelium build` pins a fresh
`mycelium_id` into every unpinned document, so measuring on this repository's own corpus
leaves ~100 modified files that must not be committed. It is documented behaviour, not a
defect, but there is no way to compile without writing to the tree — filed as **4.14**.
