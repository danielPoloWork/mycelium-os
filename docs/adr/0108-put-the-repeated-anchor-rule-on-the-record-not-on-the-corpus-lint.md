# ADR-0108: Put the repeated-anchor rule on the record, where no path can route around it

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0104](0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md)
  (roadmap 5.33, which merged the carry and added the lint this supersedes in place),
  [ADR-0039](0039-measure-what-projection-costs.md) (the twin whose carry creates the shape),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (the section judgment, the other thing a
  judged anchor can be), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (why the judged-set lints exist at all),
  [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md) (records validate on construction);
  spec 03 §10, spec 04 §7.1; roadmap 5.30, 5.33, 5.37

## Context

Roadmap 5.37 was filed at 5.30 against a defect in how a judged case is scored: the harness
builds its ground truth as `{relevant.anchor: relevant.grade}`, so a case naming one anchor
twice is **one** judged unit at whichever grade was written last, not two. The twin's carry
produces exactly that shape whenever two source anchors of one case land on the same chunk,
which a headingless PDF page guarantees.

Roadmap 5.33 then shipped ([ADR-0104](0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md))
and did most of this item's work: the carry merges duplicates at the highest grade when it
writes them, and `validate_judged_set` gained a fourth lint, an error, refusing a repeated
anchor. So the honest first question for 5.37 was whether anything was left.

Something is. **The lint is on the generator path only.** `validate_judged_set` is called from
`tools/build_eval_cases.py`, `tools/build_ingested_cases.py` and `tools/build_uv_docs_cases.py`,
and from one test that reuses it to check the committed anchors still resolve. No other caller
exists, and in particular the scoring path does not touch it:

```
mycelium eval --set <path>  ->  load_cases(path)  ->  run_evaluation(...)  ->  _evaluate_case
```

`load_cases` refuses a duplicate `case_id` and a malformed line, by line number. It says
nothing about a repeated anchor *inside* a case. So a judged set that this repository did not
generate — a contributor's, a hand-edited one, a set carried by some future tool — still scores
the last-written grade, silently, through the public surface spec 04 §7.1 defines. That is the
original defect, unfixed, one surface further out than 5.33 looked.

The item states the choice: *"the carry could merge duplicates at the highest grade when it
writes them, or the harness could refuse a set that contains one — the second is the stronger
rule and the more expensive."* 5.33 took the first. This takes the second, and the interesting
part is **where** "the harness refuses" should actually live.

## Decision

**The rule goes on `EvalCase` itself, as a model validator, and the lint that duplicated it is
removed rather than left unreachable.**

Three reasons, and the third is the one that settles it.

**It needs no corpus, and the lints it was sitting among all do.** `validate_judged_set`'s other
three checks are questions about the corpus: does this anchor exist in it, is this unanswerable
query really unanswerable against both retrievers, does this grade-3 chunk actually carry the
answer. Each needs the store. "Is this anchor named twice in this case" needs only the case. It
was the odd one out in a function whose whole signature — `(cases, store)` — exists for the
other three.

**`EvalCase` already carries this exact class of invariant.** `_judgments_match_answerability`
refuses an answerable case with no anchors and an unanswerable case with anchors, because a
record must not be able to claim something the system cannot represent. A repeated anchor is
the same claim: `relevant` is a tuple in the wire format and a *mapping* in meaning, and a
record that contradicts itself about one key is as malformed as one that contradicts itself
about answerability.

**And it is the only place that covers every path.** Records validate on construction
(ADR-0004), `relevant` is frozen, and nothing in this repository builds an `EvalCase` through
`model_construct`. So the rule now holds for the generators, for `load_cases`, for
`mycelium eval --set`, and for any consumer of the SDK — which is the difference between this
and the version 5.33 shipped.

**The message is carried over intact**, because it was already the right one: it names the case,
the anchor, *both* grades, and what to do — the fix depends on which grade is true of the
anchor, so a message that dropped one would send the reader back to the file to find it. Through
`load_cases` it arrives prefixed with the file and line, which is what a set read off disk needs
and what the generator-side lint never had to provide.

**The lint is deleted, not deprecated.** With the invariant on the record it cannot fire — every
`EvalCase` reaching `validate_judged_set` has already been through construction. Leaving it
would leave a branch that reads as a gate and is not one, which is the thing this project keeps
removing.

## Alternatives Considered

- **Leave it in `validate_judged_set` and call that from `load_cases` too.** The smallest diff,
  and it keeps one rule in one place. Rejected: `validate_judged_set` needs a `SqliteStore`, and
  `load_cases` has none and should need none — reading a case set is not a question about a
  corpus. Threading a store into the loader to run one store-free check would invert the
  dependency for the convenience of not moving five lines.
- **Refuse in `_evaluate_case`, which is literally "the harness".** The item's own wording.
  Rejected: it is the latest possible moment, after the set has been loaded, reported and
  counted, and it would fail a run rather than a file. Validation belongs at the boundary the
  data crosses, not at the point the flawed value is finally read.
- **Keep both the record validator and the lint**, so a generator reports it in a list with its
  other errors rather than raising. Rejected: the lint would be unreachable, and two statements
  of one rule are two things that can disagree — the defect shape this project has removed
  before (one default in two places). The generators do not need it: the carry merges before it
  writes (ADR-0104), so it cannot construct one.
- **Make the harness merge duplicates at the highest grade**, mirroring what the carry does.
  Rejected, and it is the tempting symmetry: the carry merges because it is *deriving* a
  judgement onto a corpus that cannot express the distinction, and it records that it did
  (`eval/carry.json`). The harness is *reading* a judgement somebody wrote. Silently repairing
  it there would make two different files score the same and tell nobody, which is the original
  defect with better manners.
- **Do nothing, and close 5.37 as delivered by 5.33.** Rejected on the evidence: the lint is
  reachable from three tools and from no part of the scoring path, so the public surface was
  still silent. Closing it would have recorded a fix that does not cover the case the item
  describes.

## Consequences

- **`mycelium eval --set` can no longer mis-score a repeated anchor.** It refuses, naming the
  file, the line, the case, the anchor and both grades.
- **No artifact moves, and none could.** No judged set changes — no committed set has ever
  contained a duplicate since 5.33 merged the carry, which the suite asserts by loading every
  one of the six. `retrieval_identity()` is byte-identical, so gate G2's recorded verdict stays
  current without a re-record (it digests constants out of `retrieval.py`, and this touches
  none). Both baselines, G3's enforcement and G6's golden are untouched.
- **The exported JSON Schema is unchanged.** A pydantic `mode="after"` validator does not reach
  the schema document, exactly as `_judgments_match_answerability` does not — so a non-Python
  consumer of `mycelium/eval-case/v0` sees the same contract it saw yesterday, and learns this
  rule the way it learns the answerability one: by being refused. Stating the limit rather than
  implying coverage: the schema alone does not express this, and a consumer validating against
  the schema document by itself will not catch it.
- **`src/mycelium/eval/` is a tuning path, so this runs the retrieval gates** — the expense
  roadmap 5.37 predicted. It is paid rather than avoided: the change carries no judgement
  change with it, so `tools/check_frozen_release_sets.py`'s conjunction is not merely satisfied
  but irrelevant.
- **`validate_judged_set` is three lints again**, and its docstring now says what they have in
  common — each needs the store — which is the rule for deciding where the next one goes.
- **A generator that produced a duplicate would now raise rather than collect an error.** Noted
  as a real change and accepted: the carry cannot produce one, and a shape that cannot be
  represented is better met at construction than reported and written.

## References

- Spec: `.draft-specs/03-data-model.md` §10 (the eval-case record),
  `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (judged sets, and `mycelium eval` as a
  public surface).
- The paths that made the gap: `mycelium.eval.cases.validate_judged_set` (called by the three
  `tools/build_*_cases.py` generators only), `mycelium.eval.cases.load_cases`,
  `mycelium.eval.harness._evaluate_case`.
- Tests: `tests/test_eval.py` — the record refuses, the ordinary two-anchor shape does not, the
  loader names the line, and every committed set still loads.
