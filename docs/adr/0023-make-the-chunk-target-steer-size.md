# ADR-0023: Make `target_tokens` steer chunk size, and let the evaluation pick its default

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §5, spec 05 §2
- **Related:** [ADR-0007](0007-adopt-structure-first-chunking.md) (amended),
  [ADR-0014](0014-adopt-partial-strict-configuration.md) (amended),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md),
  [ADR-0013](0013-adopt-the-evaluation-harness.md); spec 03 §5, spec 05 §2; roadmap 3.8

## Context

Spec 05 §2 puts `target_tokens = 400` next to `max_tokens = 800` in `mycelium.toml`, and
spec 03 §5 describes the policy as "target 200–800 tokens". The chunker built at 2.5
implemented the ceiling and nothing else: prose accumulated until the next block would
breach `max_tokens`, so every full chunk landed just under 800 and the target had no effect
on anything. ADR-0014 wired the key through the config loader anyway, mapped it onto a
policy field named `target_min_tokens`, and said in as many words that it was advisory —
lowering it did not shrink a single chunk. The generated `mycelium.toml` template said the
same, so at least the file did not lie.

Two things were wrong with leaving it there. A knob a config file offers and a compiler
ignores is worse than no knob: the reader has no way to tell it apart from one that works.
And chunk size is not a cosmetic setting — it is the single most consequential retrieval
parameter a corpus owner can reach, because it decides how much unrelated text rides along
with every hit and how many hits a section is split into.

The reason it was deferred rather than fixed is that turning the knob on moves **every**
chunk boundary in every corpus: anchors change, digests change, the determinism golden
changes, and every evaluation number moves at once. That is a question for the harness
(ADR-0013), not a side effect of wiring up a config loader — which is why roadmap 3.8 asks
for the measurement in the same breath as the feature.

## Decision

**`target_tokens` steers chunk size, and the default is the ceiling.** The packer closes a
prose run at the first paragraph boundary *after* the run reaches `target_tokens`, and
still never lets a run cross `max_tokens`; both tests read the run already accumulated, so
`target_tokens == max_tokens` packs exactly as the ceiling-only rule did. The policy field
`target_min_tokens` is renamed `target_tokens` — it was never a minimum — and `chunk`'s
build-key slice now carries it, so editing either number recompiles every document
(`CHUNK_STAGE_VERSION` 2).

**An unset `[chunking] target_tokens` means the ceiling**, and that is what ships. The
evaluation was asked whether smaller chunks retrieve better on this repository's corpus,
and the answer was no. Sweeping the target from 150 to 800 over the 20 judged cases:

| target | chunks | nDCG@10 | MRR | Recall@10 | task tokens |
|-------:|-------:|--------:|----:|----------:|------------:|
| 150 | 692 | 0.5371 | 0.6016 | 0.7708 | 1613 |
| 200 | 670 | 0.5439 | 0.6053 | 0.7708 | 1870 |
| 300 | 651 | 0.5952 | 0.6632 | 0.8021 | 1978 |
| 400 | 641 | 0.5955 | 0.6632 | 0.8021 | 2089 |
| 500 | 636 | 0.5978 | 0.6663 | 0.8021 | 2169 |
| 600 | 634 | 0.5978 | 0.6663 | 0.8021 | 2178 |
| 800 | 632 | 0.5978 | 0.6663 | 0.8021 | 2217 |

From 500 upwards every slice scores *identically* — the boundaries barely move. Below it
the only slice that changes is `relationship`, and it changes for the worse: 0.3040 →
0.2856, **−6.1 %**, against a −2 % per-slice bar this project already applied when it
refused hybrid retrieval the default (ADR-0017). Below 300 the loss spreads: `conceptual`
falls 28 % at 200 tokens and Recall@50 with it. Nothing in the sweep pays for that. The
one thing a smaller target does buy is context: the agent-task suite's mean tokens per
answer fall from 2217 at 800 to 1978 at 300, **−11 %**, at an unchanged success rate — a
real saving, and not one worth a ranking regression while the evidence for it is two cases.

## Alternatives Considered

- **Ship spec 05 §2's `target_tokens = 400` as the default** — the number the example
  config file shows, and a 6 % context saving. Rejected: it is the smallest change that
  still regresses `relationship` by 6.1 %, and a default is exactly the setting that has to
  clear the bar. The template names 400 in a commented line instead, so the value the spec
  suggests is one uncomment away from being measured on someone else's corpus.
- **Default `target_tokens` to a literal 800 rather than to `max_tokens`** — simpler to
  read. Rejected on the first test run: it makes `max_tokens = 700` on its own a validation
  error, because the untouched default now exceeds the ceiling the author just lowered.
  Tracking the ceiling keeps a one-key edit a one-key edit.
- **Close a run *before* it crosses the target** (`pending + next <= target`) — chunks would
  land under the target rather than just over it. Rejected: it makes `max_tokens`
  unreachable, so the two knobs stop being a target and a ceiling and become one number
  with a decorative sibling. The equivalence at `target == max` is what makes this a
  steering knob, and that rule loses it.
- **Enforce the target as a minimum too**, merging small sections up to it. Rejected for
  the reason ADR-0007 already gave: it crosses heading boundaries, so a chunk would answer
  to two heading paths and its anchor would lie about where the text lives.

## Consequences

- **Nothing changes for an existing repository.** The default packs as before, and the
  determinism golden re-blesses with a **one-field** diff — `config_digest`, because the
  config record gained a key — with every chunk byte-identical. That is the evidence for
  the claim, not a hope about it.
- **`[chunking] target_tokens` is now a real knob**, and editing it recompiles every
  document. That is correct and it is not free: a corpus owner experimenting with sizes
  pays a full rebuild per experiment, and every anchor they had cited moves.
- **The measurement is narrow, and this ADR does not pretend otherwise.** One corpus, 20
  judged cases, and the deciding slice holds two of them. Roadmap 3.13 (≥60 cases across
  two corpora, independent judgments) is what would let this be settled rather than
  indicated; until then, "the ceiling" is the default because it is the one that changes
  nothing, not because 800 is a good number.
- The token saving a smaller target offers is the ADR-0022 measurement, which puts the
  substrate in front of a model without a model in the loop. Whether 11 % fewer tokens per
  answer is worth 6 % worse ranking is a question about the agent, and that is precisely
  the question that harness cannot answer.

## References

- Spec 03 §5 (chunking policy, "target 200–800 tokens"), spec 05 §2 (`[chunking]`)
- [ADR-0007](0007-adopt-structure-first-chunking.md) — the ceiling-only packer this amends
- [ADR-0014](0014-adopt-partial-strict-configuration.md) — where the knob was declared advisory
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the −2 % per-slice bar
- [ADR-0022](0022-measure-the-agent-loop-without-an-agent.md) — the task-token measurement
- Sweep: `mycelium eval --json` and `--tasks --json` over targets 150–800, roadmap 3.8
