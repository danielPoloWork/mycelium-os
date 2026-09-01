# ADR-0036: Measure what can be measured, and let a human outrank the gate

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.5; RFC-0001; spec 03 §3; spec 04 §7.3 (gate G7); spec 05 §§1-2;
  D-013, D-017, D-020, D-021; [ADR-0014](0014-adopt-partial-strict-configuration.md),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md),
  [ADR-0035](0035-let-an-llm-write-only-what-a-machine-can-check.md)

## Context

D-020 let an LLM author documentation. D-021 is the other half of that bargain: nothing an
LLM wrote becomes *truth* without passing a gate and a human. Roadmap 4.5 builds that gate —
`mycelium verify`, `promote`, `demote` — and gate G7 defines it (spec 04 §7.3):

> A synthesized doc is *eligible* for promotion only if `cites` coverage ≥ 0.95 of
> claim-bearing statements AND sampled entailment vs cited evidence ≥ 0.90.

The two conjuncts are not the same kind of claim, and the whole design follows from that.

**Coverage is decidable here.** ADR-0035 already fixed the measure — a KIR `paragraph` or
`list_item` of ≥ 5 words is a claim-bearing block, and a wikilink resolving into the evidence
layer covers the block it sits in. It is a pure function of the tree.

**Entailment is not.** "Does this evidence actually say this" is a judgement about meaning.
Nothing in this repository can make it, and there are exactly two honest implementations: ask
a model, or report that it was not measured. A third option exists and is a trap — term
overlap between a claim and its citation would produce a float in the right range and it
would be a *fabricated grounding score*, which ADR-0035 called the most dangerous artifact
this project could ship.

Three more forces shape the rest:

- **D-013/D-017:** the default profile is offline. A verification that required a network
  call would make gate G7 unreachable for every default install.
- **The corpus moves.** A candidate's citations were checked when it was written; the
  evidence has been edited, re-projected, or deleted since. `SynthesisRecord` says so in its
  own docstring, and nothing at write time can catch it.
- **Frontmatter carries one `grounding` float** (spec 03 §3) and the compiler treats the
  three verification fields as a unit, warning about a partial block.

## Decision

**Measure both components; report the one that could not be measured as *not measured*;
never as a number.**

`mycelium verify` recomputes coverage against the corpus as it is — that recomputation *is*
the command's reason to exist, and its failures name the drift (`citations-unresolved`).
Entailment is a **sampled, deterministic, fail-closed** LLM check: claims are ordered by a
digest of `(document digest, node id)` and the first *n* judged, so two runs judge the same
claims; a verdict the parser cannot read counts as **not** entailed. With no judge,
`entailment is None`, and `None` travels as `None` through every layer.

**The recorded number is `min(coverage, entailment)`.** An average would let a document with
perfect citations and 0.4 entailment record 0.7 and look healthy. The gate is still
per-component against its own floor; the recorded float is a summary, never the test.

**The gate is asymmetric between CI and promotion, deliberately.** `verify --gate` fails on
a *measured* shortfall and passes an unmeasured entailment — a gate that were red on every
offline checkout is a gate everyone learns to ignore, and coverage regression is a real thing
it can still catch. `promote` is the stronger question, so there an unmeasured half **is** a
blocker — and `--force` is the human override spec 05 §1 provides.

**A forced promotion records why, in the document.** `verified_by` becomes
`<name> (forced: <blocker codes>)`. The override then lives in Git, in the file, in every
later diff — not in whatever terminal scrollback the operator had open. This is why blockers
carry a short `code` as well as a sentence.

**Demotion strips the verification block.** A demoted document is not badly grounded, it is
no longer vouched for, and a `verified_by` left behind would be a false claim in the file.

**The judge rides on `[synthesis]`'s provider**, because that is where this project's single
LLM consent lives (D-017): one credential, one place an operator says "yes, call out".
`[verification] model_id` points the judge at a different *model* through that provider. When
it is unset, the model that wrote grades its own work — a known bias, so it is **named**:
`self_judged` in the report, "self-judged" in `verified_by`, and a line from the CLI.

**`[sources]` is honoured too, and reported rather than gated.** Trust per origin is stamped
at acquisition and travels with the document; `verify` reports the weakest trust among a
candidate's cited evidence. Refusing a promotion because the evidence is `unknown` would be
this project deciding whose documentation is trustworthy, which is the operator's call.

Two deviations from spec 05 §2's own table, both taken deliberately:

1. **All three verification fields are written by the verify machinery**, not `verified_at`
   by `promote` alone. The compiler ignores a partial block and warns (spec 03 §3), so
   splitting the owners would put a warning on every candidate in the corpus. `promote` runs
   the measurement rather than writing the field itself.
2. **`[verification]` gains two keys beyond the spec's three** — `sample_size`, because
   "sampled entailment" has to say how many, and `model_id`, because self-judgement is worth
   being able to avoid.

**Stamping is conditional.** The block is rewritten only when the score or the checker
changed, so `verified_at` records when the grounding last *moved* rather than when it was
last looked at. A nightly `verify` over a corpus nothing happened to produces no diff and
therefore no rebuild.

## Alternatives Considered

- **An offline entailment approximation** (term overlap, embedding cosine between claim and
  citation). Rejected, and this is the load-bearing rejection: it produces a plausible number
  for a question it did not answer. A grounding score's whole value is that an operator can
  act on it, and a number that means "these words look similar" invites exactly the wrong
  action. `None` is less convenient and it is true.
- **Fail `verify --gate` when entailment is unmeasured.** Consistent, and it would make CI
  red on every checkout without an API key — including this repository's own. A gate nobody
  can keep green is a gate everybody disables. The asymmetry with `promote` is the price, and
  it is documented at the one function that implements it.
- **Refuse promotion outright below G7, with no override.** Rejected because spec 05 §1
  specifies `--force`, and because it is right: a human who has read the document and its
  evidence knows something the judge does not. What matters is that the override is
  *recorded*, which is the part this ADR adds.
- **Let `promote` trust the `grounding` already in the file.** Cheaper — no measurement on
  the promotion path. Rejected: that number may predate the evidence moving, which is the
  exact failure `verify` exists to catch. Promotion measures.
- **A separate `[verification] provider` with its own credential.** Rejected: a second place
  to configure the same key, for a judge that is the same seam. `model_id` gets the part that
  actually matters.
- **Store each verify run as a custody record** (as the synthesis lane does). Deferred rather
  than rejected: the frontmatter carries the score, Git carries the history, and `--json`
  carries the per-claim judgements for whoever wants to keep them. A blob nothing points at
  would be unreachable; a pointer to it is a frontmatter key, and adding one needs a reason
  better than completeness.
- **Verify everything under `candidate/` and `verified/`.** Rejected: a hand-written note has
  no citations, would score a meaningless 1.0, and would bury the documents that matter.
  Provenance (`origin: synthesized`) is what selects a subject, which is also what gate G7's
  own words say.

## Consequences

- **Gate G7 is real, per document, and offline-usable for half of itself.** A default install
  measures coverage, catches citation drift, and refuses promotion with a specific reason
  and a specific override.
- **A new public surface**: `mycelium verify [--gate] [--json] [--dry-run]
  [--no-entailment]`, `mycelium promote [--by] [--force]`, `mycelium demote`. Spec 05 §1's
  table now has four commands' worth fewer gaps.
- **One frontmatter writer, not two.** `mycelium.markdown.frontmatter.upsert` is textual, is
  what identity pinning now uses too (the build's only tier-2 write), and never
  re-serializes: a tool stamping one number has no business rewriting a human's quoting. Its
  hard rule is *one key, one line* — a folded value would leave a continuation line the
  remover cannot see, which corrupted a document during development and is now a test.
- **A forced promotion is auditable forever**, because it is in the document rather than in a
  log. The cost is a slightly ugly `verified_by`.
- **Self-judgement is possible and visible.** With `[verification] model_id` unset the writer
  grades itself; the report, the document and the CLI all say so. That is weaker than an
  independent judge and stronger than a hidden bias.
- **`mycelium doctor` gained a `verification` line** naming the floors, the judge, the sample
  size and whether promotion is automatic — the facts an operator wants *before* `promote`
  refuses on them. It appears only once a provider is configured, because with no provider
  there are no candidate documents.
- **`[verification]` and `[sources]` reach the config digest**, so the G6 golden is re-blessed
  — with a **one-line** diff (`config_digest` only; every chunk byte-identical), the same
  evidence shape ADR-0032's config change produced.
- **`UNHONOURED_SECTIONS` is down to `eval` alone**, and that one may never be honoured: the
  harness takes its case set on the command line.
- **What this does not do**: change what retrieval does with a `grounding` score (weighting
  by it is a Phase-3 question), gate on trust, archive verify runs, or make entailment
  exhaustive. The last is a cost decision — eight claims per document rather than one model
  call per block — and `sample_size` is where an operator disagrees with it.

## References

- Spec 04 §7.3 (gate G7); spec 03 §3 (frontmatter ownership, the `Verification` record);
  spec 05 §1 (the command table, `--force`), §2 (`[verification]`, `[sources]`).
- D-020 (the synthesis lane), D-021 (verification as a first-class workflow, folder-encoded
  status, promotion as a human/Git action), D-013/D-017 (offline default, one consent).
- [ADR-0035](0035-let-an-llm-write-only-what-a-machine-can-check.md) — the citation measure
  G7's coverage threshold is applied to, and the reason it is a block rather than a sentence.
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the `deterministic`
  declaration and the opt-in-network shape this reuses.
