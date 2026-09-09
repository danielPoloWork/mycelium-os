# 2026-09-08 — the gate that never ran (roadmap 4.33)

- **Session scope:** roadmap 4.33 — two judged cases no shipped profile can serve
  (spec 04 §§2, 7.3; ADR-0017/0025).
- **PR:** #87 (`fix/serve-the-two-unserved-cases`). Follows #86 (4.36), merged as `01ee12e`.
- **Milestone 4:** 4.33 done; 4.37, 4.38, 4.39 open, plus 4.40 and 4.41 filed here.

## Two of the item's three claims did not survive being read

The item said both cases score 0.0000 under both shipped profiles, that this points at
ADR-0025's precondition, and that it is not an inflection failure because "every word
appears as spelled". Checked:

- **Hybrid serves `u-1024`** on uv/release at rank 5, nDCG 0.3549. The vector leg puts its
  answer at **3 of 568** where lexical has it at 227.
- **The precondition never fires.** It withholds the vector leg only when the lexical leg
  returns *nothing*; these queries return 538 and 517 candidates. ADR-0025 also explicitly
  *rejected* the per-hit form that the item attributes to it.
- **"Every word appears as spelled" is true of the queries and false of the answers.** Of
  `u-1023`'s search terms only `can`, `uv`, `all` appear in the judged chunk; of `u-1024`'s
  only `python`, `project`. Every content word — `adopt`, `part`, `record`, `needs`, `reads`
  — is absent. The answers say "usable independently or together" and "can be used to create
  a default Python version request". This is the vocabulary-gap class ADR-0025 wrote down as
  forgone, in writing, three milestones ago.

Three cases in the table, three different failures where the item had one:

```text
case     corpus         lexical     vector   fused
u-1023   uv            421/538    276/568       -   reach: no leg finds it
u-1023   uv-ingested   403/582    286/618       -   the same, on the projection
u-1024   uv            227/517      3/568       5   served, by hybrid
u-1024   uv-ingested   120/535     39/618       -   fusion depth: inside the 50, short of ten
```

I checked the cheap way out before defending against it. If `u-1023` were mis-judged, the
embedder's own second choice would be the better answer — and
`sync.md#partial-installations` turns out to be about `--no-install-project` flags for Docker
layer caching, not about adopting part of uv's toolchain. The judgement stands and the case
stays conceded.

## The item's real content was the gate

`u-1024` is servable, by hybrid, and hybrid is not the default because gate G2 refused it.
So I went to re-read G2's numbers and found there were none to re-read. **G2 runs only when
a human passes `--retriever hybrid`.** CI never does and cannot — the hybrid arm needs the
133 MB model and D-013 forbids fetching it unless configured — and `tools/verify.py` has no
step for it either. Its verdict has been prose since ADR-0017, while the lexical leg it is
measured *against* moved four times underneath it: packing, stemming, function-word
stripping, and last PR's heading split.

Re-measured on six judged sets, G2 **cannot decide**:

| set | lexical | hybrid | overall | G2 |
|---|---:|---:|---:|---|
| ours/dev | 0.5404 | 0.5795 | +7.2 % | FAIL — `fact` −3.8 % (4 cases) |
| ours/release | 0.5051 | 0.6112 | +21.0 % | pass |
| uv/dev | 0.6727 | 0.8271 | +23.0 % | pass |
| uv/release | 0.6035 | 0.6680 | +10.7 % | FAIL — `conceptual` −13.1 % |
| uv-ingested/dev | 0.6344 | 0.7732 | +21.9 % | pass |
| uv-ingested/release | 0.6306 | 0.6194 | −1.8 % | FAIL — four slices |

Three pass, three fail, and it is not a dev-versus-release story: `ours/release` passes where
`ours/dev` fails. Five of the six clear the +5 % overall bar; every failure but one is the
per-slice condition tripping over a four-to-seven-case slice, which is one or two cases
moving. ADR-0044 and ADR-0052 established exactly this about thin slices and fixed it for
**G3** by arming only the slices that have cases. G2 never got that treatment, so the
decision that picks the product's default retrieval profile is currently a coin flip.

**So the lexical default stands on the burden of proof, not on a measurement.** Spec 04 §7.3
puts the burden on hybrid to *earn* the default, and a candidate failing three of six sets
has not. That is a weaker sentence than "hybrid was measured and refused", and it is the true
one.

## What I did not do

No retrieval change. `u-1023` is missed by both legs; bridging `record` to *request* is
lexical expansion, refused at ADR-0048 for failing G3 and G4. Flipping the default to hybrid
would be shipping on the dev sets, where it reads +22 % to +23 % against failures on both
frozen release sets — the fit ADR-0027's split exists to prevent, and the dev/release gap
under hybrid widens from +0.069 to +0.159.

And I did not touch G2's bar. The measurement says the gate is underpowered; the answer to an
underpowered gate is more cases, never a wider bar. What G2's second condition *should* say
at these set sizes is filed as 4.41, to be argued when no candidate is pending — because a
bar moved with a candidate in flight is not a bar.

## Found on the way

The tool printed latency for one revision, and the figures moved by **10×** between two runs
of the same tree on this machine — lexical p95 15 ms, then 141 ms — while every nDCG stayed
identical to four decimals. I had already started writing a "hybrid misses G5 by 5×" finding
off the first reading. It was machine load. The column is gone, G5 stays with the harness
that measures it where the product runs, and the docstring says why so the next person does
not add it back.
