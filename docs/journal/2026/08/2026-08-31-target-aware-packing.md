# 2026-08-31 — the knob that was never wired (roadmap 3.8)

- **Session scope:** roadmap 3.8 — make `[chunking] target_tokens` steer chunk size instead
  of being advisory (spec 03 §5, spec 05 §2), and let the evaluation harness say what the
  default should be.
- **PR:** #39 (`feat/target-aware-packing`). Follows #38 (the G3 comparability fix), merged
  as `34f0799`.
- **Milestone 3:** 3.1–3.8 and 3.10 done; 3.9, 3.11–3.13 open.

## The feature is small; the question it carries is not

The packer built at 2.5 read one number, `max_tokens`, and filled toward it. `target_tokens`
existed in the config file, was validated, was digested, and was ignored — ADR-0014 wrote
that down rather than hiding it, and the generated `mycelium.toml` said `advisory today` on
that very line. Making it real is a three-line change to the packing loop: close a prose run
when it has *reached* the target, as well as when the next block would breach the ceiling.

What made it a roadmap item rather than a commit is that chunk size is the most consequential
retrieval parameter a corpus owner can reach, and turning the knob moves every boundary,
every anchor and every number at once. So the item is really a question — **do smaller chunks
retrieve better?** — and 3.8 exists to answer it with the harness rather than with taste.

## The answer is no, and the shape of the no matters

Seven clean builds of this repository, targets 150 to 800, same ceiling, same 20 judged cases:

| target | chunks | nDCG@10 | Recall@10 | task tokens |
|-------:|-------:|--------:|----------:|------------:|
| 150 | 692 | 0.5371 | 0.7708 | 1613 |
| 300 | 651 | 0.5952 | 0.8021 | 1978 |
| 400 | 641 | 0.5955 | 0.8021 | 2089 |
| 500 | 636 | 0.5978 | 0.8021 | 2169 |
| 800 | 632 | 0.5978 | 0.8021 | 2217 |

From 500 up every slice is *identical* — at these sizes the authored paragraph boundaries,
not the budget, decide where chunks end. Below 500 exactly one slice moves, and it moves the
wrong way: `relationship` 0.3040 → 0.2856, −6.1 %, past the −2 % per-slice bar this project
already used to refuse hybrid retrieval the default (ADR-0017). Below 300 the loss spreads —
`conceptual` −28 % at 200 tokens.

So the default stays at the ceiling, and the honest form of that sentence is: *the knob is
real, and it did not earn a smaller default on the only corpus we can measure.* The deciding
slice holds two cases. Roadmap 3.13 is what would let this be settled instead of indicated.

The one thing a smaller target does buy is context — 2217 → 1978 mean tokens per agent-task
answer at 300, −11 %, success rate unchanged. Whether that trade is worth 6 % worse ranking
is a question about the *agent*, and ADR-0022's harness deliberately has no agent in it. The
ADR records the trade rather than pretending the harness resolved it.

## Two things the tests said and I did not

**A literal default breaks a one-key edit.** With `target_tokens` defaulting to 800,
`[chunking] max_tokens = 700` on its own became a validation error: the untouched default
now exceeded the ceiling the author had just lowered. Two existing config tests caught it
within a minute of the change. The default is not a number, it is *the ceiling* — an unset
target tracks `max_tokens`, so lowering the ceiling stays a one-line edit.

**The equivalence is a property, not a comment.** `target_tokens == max_tokens` has to pack
exactly as the ceiling-only rule did, or the target is a second ceiling rather than a
steering knob. Both tests in the loop read the run *already accumulated*, never the run it
would become, which is what makes the first test unreachable when the two numbers meet —
and there is now a test that says so.

## What the golden proved

`CHUNK_STAGE_VERSION` goes to 2 and the chunk build-key slice carries `target_tokens`, so
editing it recompiles every document — which is the correctness point, since a cached chunk
built under another target is simply wrong. But the shipped default changes no output, and
the determinism golden is the evidence rather than the claim: it re-blesses with a
**one-field** diff, `config_digest`, because the config record gained a key. Every chunk is
byte-identical.

That is the second time a golden with per-chunk detail has answered a question in one line
that would otherwise have needed an argument (the first was ADR-0014's own config digest).
A hash-only golden could not have done it.
