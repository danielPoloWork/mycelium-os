# ADR-0065: One section cannot be the documenting home of two commands

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.37 (this item), 4.34 (where it was filed); RFC-0001; spec 04 §7.1;
  D-010;
  [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0043](0043-judge-across-the-configurations-a-set-is-scored-under.md),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) — **narrowed here**,
  [ADR-0064](0064-measure-the-gate-that-decides-the-default.md)

## Context

`u-0006` (`uvx`, the `symbol` slice of **uv/dev**) has scored **0.0000** since it was
written. Its grade-3 anchor, `docs/concepts/tools.md#the-uv-tool-interface/0`, comes back at
rank **13**; its grade-2 anchor, `docs/guides/tools.md#/0`, is not in the candidate set at
all — that chunk is 25 tokens of overview and never contains the string `uvx`. Meanwhile
`docs/guides/tools.md#running-tools`, whose first sentence is *"The uvx command invokes a
tool without installing it"*, sits at rank **3** and is unjudged.

Roadmap 4.37 framed this as a question about the **second** anchor, on the grounds that the
grade-3 one is defensible where `u-1007`'s was not: that section really does define the
alias (*"a `uvx` alias is provided for `uv tool run` — the two commands are exactly
equivalent"*). ADR-0062 said the same thing more strongly — that this section is *"the right
one for a different query: `u-0006` … grades that same section 3, **correctly**"* — and
`eval/README.md` carries that sentence.

Read against the documents, that is the part which does not hold, and the reason is
structural rather than a matter of taste.

**ADR-0062's own rule decides it.** *"A `symbol` case names the section that **documents** it
at grade 3; a page that **frames** it, defines a sibling, or mentions it in passing is a
lesser grade or none."* Apply that to the two candidates:

| section | first sentence | subject |
|---|---|---|
| `concepts/tools.md#the-uv-tool-interface` | *"uv includes a dedicated interface for interacting with tools."* | the **interface** — it then names `uv tool run`/`uvx` in one clause and `uv tool install` in another |
| `guides/tools.md#running-tools` | *"The uvx command invokes a tool without installing it."* | the **command** — invocation, arguments, isolated environments, and when to use `uv run` instead |

**And the pair as it stood was internally inconsistent.** ADR-0062 graded
`concepts/tools.md#the-uv-tool-interface` **2** for `u-1007` (`uv tool install`) because its
subject is the interface — and simultaneously **3** for `u-0006` (`uvx`) because it defines
the alias. A section's subject does not change with the query asked of it. One section
cannot be the grade-3 *documenting* home of two sibling commands under a rule that says
grade 3 goes to the section that documents the thing. The corpus does not require it to be:
the guide has a section per command — `#running-tools` for `uvx`, `#installing-tools` for
`uv tool install` — which is exactly the structure ADR-0062 relied on for the sibling.

## Decision

**`u-0006` is re-judged on the convention its siblings already follow**, and the grades move
so that the same section carries the same grade for both commands:

| anchor | was | now | why |
|---|---:|---:|---|
| `docs/guides/tools.md#running-tools/` | — | **3** | the section that documents the command; section-scoped, as `u-1007`'s grade-3 anchor is (ADR-0043) |
| `docs/concepts/tools.md#the-uv-tool-interface/0` | 3 | **2** | the framing section — the grade it already carries in `u-1007` |
| `docs/getting-started/features.md#tools/0` | — | **1** | the feature-list entry (*"uvx / uv tool run: Run a tool in a temporary environment"*), the tier `u-1007` and `u-1019` use |
| `docs/guides/tools.md#/0` | 2 | **removed** | 25 tokens of overview that never names `uvx` |

**ADR-0062's aside about `u-0006` is narrowed, not its decision.** What that ADR decided —
`u-1007`'s re-judging, and the rule it wrote down — stands unchanged and is what this ADR
applies. What is narrowed is one sentence reasoned about a case that was explicitly deferred:
the section defines the alias, which is why it keeps a **2** rather than losing its place
altogether, but defining a thing in a clause is not documenting it.

**And this change makes us look worse, which is stated first.** Re-judged, `u-0006` goes
0.0000 → **0.3726** on uv/dev — and the incumbent goes 0.2275 → **0.4650**. So grep was
already ahead on this case while the old judgment scored us zero, and it is *still* ahead:
the `symbol` slice now reports `conceded on 1 of 1 case(s): u-0006 0.373 vs 0.465`. The
mechanism is one rank: both retrievers put `#running-tools` at rank 3, and grep also lands
the grade-2 framing section inside the top ten where we have it at rank 13.

We gain more than the incumbent here (+0.373 against +0.238), which is the opposite of
ADR-0062's honesty note — and it is *not* the reason for the change. The reason is the
inconsistency above. The score improving is grounds for extra scrutiny, so the alternative
that keeps the grade where it was is priced below, and it is what a maintainer who disagrees
should reverse to.

## Alternatives Considered

- **Keep grade 3 on `concepts/tools.md#the-uv-tool-interface` and only fix the second
  anchor** — what roadmap 4.37 proposed and what ADR-0062 asserted. Priced: `#running-tools`
  at 2 and the framing section staying at 3 scores `u-0006` **0.160** instead of 0.373, and
  leaves the section that documents the command graded below the section that mentions it.
  Rejected on the inconsistency, not on the number: it requires one section to be both the
  documenting home of `uvx` and the framing of `uv tool install`, which the rule cannot
  support. **This is the change to revert to if the maintainer reads the two sections the
  other way** — the judged set is one line, and the ADR is where the disagreement is
  recorded either way.
- **Grade `#running-tools` 3 and drop the framing section entirely.** Rejected: it *is*
  where the alias is defined, and a reader sent there has their question answered. ADR-0062's
  three tiers exist for exactly this — documenting 3, framing 2, mention 1 — and dropping a
  tier to sharpen a number is fitting.
- **Judge `#running-tools` by chunk (`/0`) rather than by section (`/`).** Rejected for the
  reason ADR-0043 gives: it is 307 tokens and one chunk *under this chunking setting*. Its
  sibling `u-1007` is section-scoped for the same reason, and a judgment that breaks when
  `pack_atomic` flips is a judgment measuring the chunker.
- **Re-judge `u-0006` on the release set too.** There is nothing to re-judge — `u-0006` is a
  dev case and `u-1007` is its release-side counterpart, already done at 4.34. No frozen set
  is touched by this change, which is why it can be one PR.
- **Leave `u-0006` at 0.0000 as a conceded case.** The honest option where a case is hard
  (as `u-1023` is, ADR-0064). Rejected because this case is not hard: the answer comes back
  at rank 3 and the judgment was pointing somewhere else.

## Consequences

- **uv/dev rises 0.673 → 0.710**, and uv-docs-ingested/dev 0.634 → 0.668. The `symbol` slice
  goes 0.000 → 0.373 and 0.000 → 0.339. It is a one-case slice on both, which is 4.39's
  argument and not a defence of these numbers.
- **A concession becomes visible where a zero hid one.** `symbol` on both dev sets now reports
  `conceded on 1 of 1 case(s)` against grep. Nothing got worse; a case we were losing while
  scoring zero is now a case we are losing while scoring 0.373, and the harness says so.
- **The dev surface moved, deliberately and once.** Every retrieval candidate measured from
  here is measured against this judgment — which is why 4.37 was filed as its own item rather
  than folded into 4.34, and why this ADR exists rather than a paragraph.
- **The derived set follows mechanically.** `tools/build_ingested_cases.py` carries the new
  grade-3 anchor to `tools-docx-cf7bdde6.md#using-tools/running-tools/0` at coverage **1.00**,
  and drops the grade-1 feature-list anchor at coverage 0.42 — the same anchor it already
  drops for `u-1007`, for the same reason. CI byte-compares the regeneration (4.16).
- **No baseline is blessed and no gate arms.** Dev sets carry no committed baseline, so G3
  reports "nothing to regress against" as it always has on them. No retrieval code changes.
- **`eval/README.md` and ADR-0062 are corrected where they made the claim** — a narrowing
  note in the ADR beside the sentence, and the sentence itself rewritten in the README, so a
  reader following either reference does not re-inherit it.

## References

- Spec 04 §7.1 (the dev/release split — why a dev judgment gets its own decision); D-010.
- Read from the documents: `docs/concepts/tools.md#the-uv-tool-interface` (127 tokens),
  `docs/guides/tools.md#running-tools` (307), `docs/guides/tools.md#/0` (25),
  `docs/getting-started/features.md#tools` (84).
- Measured this session: ranks 13 / absent / 3 / 17 for the four candidates under the shipped
  lexical profile; `u-0006` 0.0000 → 0.3726 for mycelium and 0.2275 → 0.4650 for grep; the
  alternative at 0.160; the carry at coverage 1.00.
- [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) — the rule this
  ADR applies, and the one sentence of it this ADR narrows.
- [ADR-0043](0043-judge-across-the-configurations-a-set-is-scored-under.md) — why the grade-3
  anchor is section-scoped.
