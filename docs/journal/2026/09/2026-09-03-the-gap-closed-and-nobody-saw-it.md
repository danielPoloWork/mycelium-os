# 2026-09-03 — the gap closed, and nobody saw it (roadmap 4.8)

- **Session scope:** roadmap 4.8 — the product loses to the grep incumbent on the second
  corpus (D-010, spec 04 §7.4).
- **PR:** #70 (`feat/measure-against-the-incumbent`). Follows #69 (4.19), merged as `0a11a9b`.
- **Milestone 4:** 4.8 done; 4.20, 4.21, 4.22, 4.23, 4.24 open, plus 4.25 filed here.

## The item was already closed when I opened it

I expected to spend this session on a ranking hypothesis. The first thing to do was
re-measure, and the measurement ended the item:

| release set | ours | grep |
|---|---:|---:|
| `uv`'s documentation | **0.548** | 0.519 |
| this repository | **0.504** | 0.271 |

Filed at 3.15, that first row read grep **0.409** against our **0.249**. All four sets now
favour the product.

Two things about that are worth more than the closure.

**Nothing in this item's own family closed it.** Thirteen re-rankings had been measured and
refused across ADR-0031 and ADR-0041 — length priors, coverage-first, six forms of the
section unit, the incumbent's own formula. All thirteen are still refused. What closed the
gap was the packed chunker (4.15) and the stemmed index (4.19): both changes to *what gets
indexed*, neither a change to how candidates are ordered. ADR-0041's closing line — "the
unit of indexing is not where this gap closes", followed by "the hypothesis left standing is
a chunking one" — was right twice.

**The incumbent's own score went up too**, 0.409 → 0.519. The corpus was re-judged at 3.17
and 4.12 and the chunker moved at 4.15, so "0.249 → 0.548" would be a sentence about two
different corpora. The only claim that survives contact is the one measured on both sides at
once, which is what this PR makes structural.

## The part that is actually a defect

The gap closed somewhere between PR #67 and PR #69. Neither PR noticed, and neither was
careless: 4.15's PR body reports the second corpus going 0.306 → 0.492 against grep's 0.519
and correctly says we are still behind; 4.19's reports its own before/after and never asks
about grep at all. In between, the answer changed and nothing said so.

It could not have said so. The comparison lived in two places, and both were blind:

- an ADR table, which is a photograph;
- one CI step, `mycelium eval . --retriever grep`, pointed at **our** corpus — while the
  finding was about the **second** one, which CI never compared.

That is the same failure mode as a stale baseline, one level up: the measurement existed,
nobody could see it move. So the deliverable is not the closure, it is
`mycelium eval --against grep`: the incumbent scored **inside** the run, on the same
snapshot and the same cases, recorded in the manifest spec 04 §7.5 already demands, and run
by CI on all three corpora. The same shape gate G2 already uses to score the lexical leg
beside the hybrid one — because two numbers from two runs are a comparison only if someone
checked nothing moved between them, and nobody ever does.

## What the report says that the number does not

The line that matters is not the delta:

```text
vs grep: nDCG@10 0.548 against grep's 0.519 (+0.029) - ahead of the incumbent;
         still conceded: fact 0.403 vs 0.497
```

An overall lead of +0.029 is one sentence away from "closed, moving on". `fact` on that
corpus is seven cases — the largest slice on the set, and the shape the corpus is made of:
short imperative task pages. The incumbent leads it by 23 % relative. `symbol` is 0.000 for
both, which is not a concession but an absence, and is not the same problem.

Filing the residue as 4.25 rather than folding it into the closure is the whole discipline
here. The alternative — one number, one tick, done — is how an item comes back.

## Reported, never gated

Spec 04 §7.4 quantifies the grep gate at 1.0 (roadmap 6.4), and I did not bring it forward.
On a seven-case slice "the incumbent wins by 23 %" is one case moving, and a gate nobody
believes is a gate everyone re-blesses — ADR-0039's finding, which this project has now paid
for twice. What did tighten is cheap and real: the test that asserted we beat grep ran on
our own **dev** set, the one tuning is allowed to read. It now asserts the release set too.
