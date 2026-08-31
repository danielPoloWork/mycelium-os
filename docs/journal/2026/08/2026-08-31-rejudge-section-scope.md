# 2026-08-31 — re-judging, and the control that stopped me reporting the wrong cause (roadmap 3.17)

- **Session scope:** roadmap 3.17 — apply ADR-0029's section notation to the four judged sets,
  the deliberate act that ADR itself deferred.
- **PR:** #47 (`feat/rejudge-section-scope`). Follows #46 (3.16), merged as `cfadf9b`.
- **Milestone 3:** 3.1–3.17 done; 3.18 open.

## How the judging was done

Not by looking at rankings. For every judgment I printed the section it names, how many chunks
the corpus split that section into, and the text of each — then decided from the document.

Most judged sections hold **one** chunk, where the two notations are equivalent; those were
left alone rather than converted wholesale, because "which to write is a judgment about the
document" and a blanket conversion is the opposite of one. Thirteen judgments named sections
the corpus had split, and those were decided case by case:

- `uv add httpx` and the entry it writes and the flags that vary it — **section**. Judging the
  flags paragraph, as the original case did, was judging where the chunker splits.
- "which versions still receive security fixes" — the prose *and* the table answer, and a
  reader needs whichever they land on — **section**.
- `UV_CACHE_DIR`, `BEGIN IMMEDIATE` — a literal in one chunk — **chunk**.
- "why does the build write mycelium_id into frontmatter" — I could not tell without reading
  more than I had — **chunk**, because that is the reading that cannot flatter us.

That last rule is the one worth keeping, and it is now in `eval/README.md`.

## The control that changed what I was about to write

Measured against the previous PR's numbers, our dev set appeared to **fall**: 0.567 → 0.546.
I nearly wrote that down as a cost of re-judging.

It was the corpus. The previous number came from a tree without #46's ADR, bug record and
journal entry. Re-measuring both sets of judgments against **one build**, with the judgments as
the only variable:

| set | before | after |
|---|---:|---:|
| ours / dev | 0.546 | 0.546 |
| ours / release | 0.453 | **0.457** |
| uv / dev | 0.403 | 0.403 |
| uv / release | 0.249 | **0.280** |

Nothing fell. This is the second time in three items that a number moved for a reason that had
nothing to do with the change under test — and it is exactly what G3's corpus fingerprint was
built for. The lesson is narrower than "be careful": **a before/after across two trees is not a
before/after.**

## What it did not fix

The re-judging raised us by 0.031 on the second corpus and raised **grep** by 0.062:

| uv / release | before | after |
|---|---:|---:|
| mycelium | 0.249 | 0.280 |
| grep | 0.409 | **0.471** |

The gap widened, from +0.160 to +0.191. So the judging flaw was never what 3.18 is about, and
the comfortable reading — "the numbers were unfair, the product is fine" — is not available.
Good: an item that could only have made us look better would not have been worth doing.

## A gap ADR-0029 left

It shipped the notation and not the validator: `validate_judged_set` asked the store for a
chunk, and a section anchor is not one, so the first rebuild reported eight judged anchors as
"not in the corpus". A section resolves against the set of heading paths instead — not
depending on the chunk count is the whole point of writing one.

Shipping a notation without teaching every tool that reads it is a small, ordinary omission.
It surfaced within one command because the builders validate before they write, which is why
that validation exists.
