# 2026-09-09 — ten cases, and a mistake kept (roadmap 4.39)

- **Session scope:** roadmap 4.39 — `uv/dev` cannot answer a field-weight question, and one
  is waiting on it (spec 04 §§7.1, 7.6; ADR-0027/0052/0058/0063).
- **PR:** #90 (`test/grow-the-uv-dev-set`). Follows #89 (4.38), merged as `40b6171`.
- **Milestone 4:** 4.39 done; 4.40, 4.41 open, plus 4.42 filed here.

## The order of the two commits is the whole method

The branch has two commits. The first adds ten judged cases and **scores nothing**. The
second measures. Nothing about any candidate informed which cases were written, and the split
is what a reviewer can check instead of taking my word for it.

Cases were selected by a mechanical criterion — which slices were thin — and written from the
documents: `exact` 1 → 4 (rare literal tokens with one dominant home), `symbol` 1 → 4 (bare
command names), `relationship` 0 → 4. Graded on the conventions already in force, section-scoped
where the chunk is big enough that another chunking setting would split it, every anchor verified
to resolve. Eight of the ten name documents that had never been judged, which takes coverage
from 20 of the corpus's 81 documents to 26.

## It worked, and the useful half is the refusal

At twelve cases every safe setting of the heading family read **exactly 0.673** — the number
that made ADR-0058 refuse `heading 3.0/0.5` for having no dev signal. At twenty-two:

| setting | uv/dev nDCG@10 | MRR | R@10 |
|---|---:|---:|---:|
| `2.0/0.5` *(ships)* | 0.609 | 0.630 | 0.692 |
| **`3.0/0.5`** | **0.614** | 0.632 | **0.717** |
| **`4.0/0.5`** | **0.599** | 0.607 | 0.717 |

The leaf weight now has an **interior optimum**: 3.0 beats the shipped 2.0, and 4.0 is *worse
than the baseline*. That second row is the one I care about, because the release sets prefer
`4.0/0.5` — uv/release 0.616 against 3.0/0.5's 0.611 — and the grown dev set refuses it. A dev
set that only ever agreed with the held-out sets would have been worth nothing.

The dev/release gap on this corpus closed from +0.069 to **+0.005**. uv/dev's headline fell
0.710 → 0.609, which is not a regression: the cases I wrote are harder than the twelve that
were there.

Nothing shipped. The leaf weight is a retrieval change and the value of the commit order
evaporates if the set is grown and the candidate it enables lands beside it. Filed as 4.42.

## Four of the ten are a mistake, and I kept them

| case | slice | ours | grep |
|---|---|---:|---:|
| `u-0013`–`u-0015` | exact | **1.000** each | 1.000 |
| `u-0016` `uv build` | symbol | **0.947** | 0.389 |
| `u-0017` `uv venv` | symbol | 0.459 | 0.047 |
| `u-0018` `uv init` | symbol | 0.319 | 0.124 |
| `u-0019`–`u-0022` | relationship | **0.090** mean | 0.093 |

The `relationship` slice serves neither retriever, so as a discriminator it is nearly dead —
and that is my error, not the corpus's. I took `u-1022`'s note as a design rule — *"the query
uses neither's noun"* — and applied it to all four, which made every one of them a
**vocabulary-gap** case as well: the class ADR-0025 named as forgone and ADR-0064 found in
`u-1023`. A `relationship` case should test whether the retriever finds the section that
*relates* two things. It should not simultaneously test whether it can bridge "can another
tool read" to "tool-agnostic". The release set's four do not make that mistake: `u-1009` says
*lockfile* and *workspace*.

I found this **because I measured**, which is exactly the sequence the commit-order discipline
exists to distrust. So the cases stay. Rewriting a case after seeing it score badly is
indistinguishable from fitting the set whatever reason I give, and "my design rule was wrong"
is the reason someone fitting a set would give. Each of the four is verified against the
documents and correctly judged; their difficulty is information. The numbers are on the record
and any revision starts from them, in a change where the order is visible.

The three `exact` cases at 1.000 deserve the same scepticism from the other end: they are easy
because the slice is *defined* as trivially retrievable, and four such cases will not
discriminate much either. What the grown set demonstrably bought is in `symbol`, where four
cases span 0.319 to 0.947 — and that spread is what made the leaf weight visible.

## Found on the way: 4.26's coupling, from the other side

Nine of the ten cases judge documents that were previously unjudged **distractors** in the
ingested twin — and that corpus assigns `docx`/`html`/`pdf` in rotation over the *judged*
documents, everything else HTML. So six of them appended to `format-rotation.json` and took a
real format. Append-only did exactly what 4.26 built it for: nothing already rendered moved,
and the assignment went to 10/62/9.

But six documents' chunks changed, which moves the ingested corpus digest and switches G3
there from **enforcing** to *reporting*. Per ADR-0056 a bless then has to ride with the change
rather than wait for a tidier PR, because otherwise the only enforcing gate on that set is
left switched off with nobody accountable for switching it back. So:
uv-docs-ingested/release **0.6306 → 0.6341**, three cases moved (`u-1021` 0.289 → 0.315,
`u-1004` 0.431 → 0.387, `u-1022` 0.787 → 0.885), worst slice movement **`fact` −1.20 %** —
inside the −2 % bar, so the gate would have passed had it been able to compare.

The ingested *dev* set falls 0.596 → 0.548 for the same reason: six of its documents are now
read from DOCX and PDF instead of HTML. The Markdown corpus's release set is untouched and
still reads *"same corpus, same boundaries, same judgements, no enforced slice regressed."*

## What I did not do

I did not grow `conceptual` or `fact` — both already clear the four-case threshold, and every
case added is a judgement to defend. I did not touch `ours/dev`, which is not thin and is not
the set that could not see the candidate. I blessed exactly one baseline — the ingested
release set, because the re-rendering forced it — and no dev baseline, because dev sets carry
none. And I did not ship 3.0/0.5, which is the one thing this item makes possible and the one
thing it must not do.
