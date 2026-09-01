# 2026-09-01 — measure what can be measured (roadmap 4.5)

- **Session scope:** roadmap 4.5 — `mycelium verify` / `promote` / `demote` with grounding
  gate G7 (D-021, spec 04 §7.3), and the two configuration sections it needed.
- **PR:** #55 (`feat/verify-promote-demote`). Follows #54 (4.4), merged as `445e168`.
- **Milestone 4:** 4.1–4.5 done; 4.6, 4.7, 4.8, 4.9 open.

## The gate has two halves and only one of them is arithmetic

G7 reads as one rule — coverage ≥ 0.95 **and** sampled entailment ≥ 0.90 — and the whole
item turned on the fact that those are different kinds of claim.

Coverage was already settled: ADR-0035 fixed "claim-bearing block" as a KIR `paragraph` or
`list_item` of ≥ 5 words, so recomputing it is a pure function of the tree. And recomputing
is the point. The synthesis record holds what was true when the document was written; the
corpus has moved since. An evidence document that was edited, re-projected under a different
heading, or deleted leaves a candidate citing something that no longer says what it said, and
nothing at writing time can catch that. `citations-unresolved` is what that looks like now.

Entailment is a judgement about meaning. Nothing here can make it. Which leaves two honest
implementations — ask a model, or say it was not measured — and one dishonest one that I want
on the record because it is genuinely tempting: **term overlap between a claim and its
citation**. It runs offline, it needs no provider, it produces a float between 0 and 1, and
it is a fabricated grounding score. ADR-0035 called that class of artifact the most dangerous
thing this project could ship, and a number that means "these words look similar" while
sitting in a field called `grounding` is exactly it.

So `entailment` is `None` when nobody measured it, and `None` travels as `None` all the way
to the operator. *Null Object* went into the patterns catalogue as **rejected** for the same
reason: a null judge would have to answer, and every answer it could give is wrong —
`ENTAILED` passes a document nobody checked, `NOT_ENTAILED` fails one nobody found fault
with, and 0.5 is the fabrication again.

## The asymmetry I nearly got wrong

First cut: `verify --gate` fails whenever G7 is not satisfied. That is consistent, and it
would have made CI red on every checkout without an API key — including this repository's
own. A gate nobody can keep green is a gate everybody disables, which is worse than not
having one.

So the two callers ask different questions and get different answers:

- **`verify --gate`** (CI) asks *has grounding regressed*. It can answer that for coverage
  without a provider, so an unmeasured entailment is reported and does not fail it.
- **`promote`** asks *may this become truth*. There the unmeasured half **is** a blocker, and
  `--force` is the human's answer — which is what D-021 and spec 05 §1 both say.

The asymmetry lives in one function, `Grounding.blockers(..., require_entailment=)`, with the
reasoning in its docstring, because a reader who finds it anywhere else will assume it is a
bug.

## What a forced promotion has to leave behind

`--force` is in the spec, and it is right: someone who has read the document and its evidence
knows something the judge does not. The part worth designing was the *record*. A warning on
stderr is an override nobody can audit six months later, so the reason goes into the
document:

```yaml
verified_by: 'Daniel Polo (forced: entailment-not-measured)'
```

That is why blockers grew a short `code` alongside their sentence — the sentence is for the
terminal, the code is for a field that has to stay readable in a diff and greppable in a
year. And it is why `promote` **measures** rather than reading the `grounding` already in the
file: that number may predate the evidence moving, which is the failure the command exists to
find.

## Two things the frontmatter taught me

First, the writer. Verification stamps three fields into someone's tracked file, and the
build already had a private textual insert for `mycelium_id`. Two writers would be two
opinions about what a document may look like after a tool touches it, so there is now one —
`markdown.frontmatter.upsert` — and identity pinning uses it. The determinism golden not
moving is the proof that the refactor was byte-compatible.

Second, a real bug, found by running the command rather than by a test. PyYAML folded a long
`verified_by` across two lines; `demote` then removed the key by deleting *its* line and
orphaned the continuation, leaving a corrupted block. Two fixes: emit at an unreachable line
width so a value is never folded, and delete a key's continuation lines with it — which also
makes the writer safe against a multi-line value it did not write, like a vault's `tags:`
sequence. Both are tests now.

## A spec deviation I could not avoid

Spec 05 §2's table assigns `verified_at` to `mycelium promote` and the other two verification
fields to `verify`. Honouring that literally puts `verified_by` + `grounding` into every
candidate with no `verified_at`, and the compiler treats the three as a unit — so every
candidate in the corpus would carry a "partial verification block ignored" warning. All three
are written by the verify machinery instead, and `promote` runs that machinery rather than
writing a field itself. Recorded in ADR-0036 rather than left as a surprise.

## Where the numbers go, and what still bothers me

`grounding` is `min(coverage, entailment)`. An average would let a document with perfect
citations and 0.4 entailment record 0.7 and read as healthy; the minimum cannot hide a failed
component, and the gate is still checked per component against its own floor.

What bothers me, stated rather than hidden: with `[verification] model_id` unset, **the model
that wrote the document is the model that judges it**. The provider is the operator's single
LLM consent (D-017) and I did not want a second credential surface, so the default is
self-judgement — named in the report, in `verified_by`, and out loud by the CLI. It is weaker
than an independent judge and stronger than a bias nobody mentions. `model_id` is the knob for
anyone who cares, and they should.

## Also closed

`[verification]` and `[sources]` are honoured, which leaves `eval` as the only section
`mycelium.toml` accepts and nothing reads — and it may stay that way, since the harness takes
its case set on the command line. `[sources]` was pointed here by 4.1's own config comment:
trust per origin is stamped at acquisition and `verify` reports the weakest trust among a
candidate's cited evidence. It is **reported, never gated** — deciding whose documentation is
trustworthy is the operator's call, not this project's.
