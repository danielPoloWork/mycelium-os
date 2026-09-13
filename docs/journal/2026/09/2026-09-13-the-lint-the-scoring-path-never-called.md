# 2026-09-13 — the lint the scoring path never called (roadmap 5.37)

- **Session scope:** roadmap 5.37 — a carried case can name one anchor twice, and the harness
  keeps whichever grade was written last. Decide where the rule against it belongs
  (spec 04 §7.1).
- **PR:** #136 (`fix/refuse-a-repeated-judged-anchor`). Follows #135, merged as `5a21b63`.
- **Milestone 5:** 5.37 done. 5.38–5.40 are the open follow-ups.
- **ADR:** [ADR-0108](../../../adr/0108-put-the-repeated-anchor-rule-on-the-record-not-on-the-corpus-lint.md).

## The first question was whether the item was already done

5.37 was filed at 5.30. 5.33 shipped afterwards, at PR #132, and its roadmap entry reads like a
complete answer to this one: the carry merges duplicates at the highest grade when it writes
them, and `validate_judged_set` gained a fourth lint — an error — refusing a repeated anchor in
any set, with a test that no committed set has one.

So the item could have been closed as delivered. Reading the code instead of the prose is what
stopped that, and it took one grep:

```
validate_judged_set  <-  tools/build_eval_cases.py
                     <-  tools/build_ingested_cases.py
                     <-  tools/build_uv_docs_cases.py
```

Three generators, and nothing else. The scoring path never goes near it:

```
mycelium eval --set <path>  ->  load_cases(path)  ->  run_evaluation(...)  ->  _evaluate_case
```

`load_cases` refuses a duplicate `case_id` and a malformed line, by line number, and says
nothing about a repeated anchor *inside* a case. `_evaluate_case` still builds
`{relevant.anchor: relevant.grade}`. So a judged set this repository did not generate — a
contributor's, a hand-edited one — was still scored against the last-written grade, silently,
through the surface spec 04 §7.1 calls public. 5.33 fixed the corpus; the defect was in the
contract.

## Where the rule belongs

The item framed the choice as *carry merges* against *harness refuses*, and 5.33 had taken the
first. Taking the second turned out to be a question about **which** "harness".

The answer is one level earlier than the word suggests: on `EvalCase` itself. Three reasons,
and the third decides it.

It needs no corpus. The three surviving lints are all questions about one — does this anchor
exist, is this unanswerable query really unanswerable against both retrievers, does this grade-3
chunk carry the answer — which is what the `(cases, store)` signature is for. "Is this anchor
named twice" needs only the case, and it was the odd one out.

The record already carries this class of invariant. `_judgments_match_answerability` refuses an
answerable case with no anchors and an unanswerable one with anchors, because a record must not
claim what the system cannot represent. `relevant` is a tuple in the wire format and a mapping
in meaning; a record that contradicts itself about one key is malformed in exactly the same way.

And construction is the only place that covers every path. Records validate on construction,
`relevant` is frozen, and nothing here builds an `EvalCase` through `model_construct` — so the
generators, `load_cases`, the CLI and any SDK consumer are all covered by the same five lines.

## Deleting the thing it replaces

With the invariant on the record the lint cannot fire: every `EvalCase` that reaches
`validate_judged_set` has already been through construction. So it is deleted rather than kept
"for safety". Two statements of one rule are two things that can disagree, and a branch that
reads as a gate and is not one is what this project keeps taking out.

The message was worth keeping exactly as 5.33 wrote it — the case, the anchor, and *both*
grades, because the fix depends on which grade is true of the anchor. Through `load_cases` it
now arrives with the file and line in front of it, which is what a set read off disk needs and
what a generator-side lint never had to supply.

One limit is stated rather than implied: a `mode="after"` validator does not reach the exported
JSON Schema, so a non-Python consumer validating `mycelium/eval-case/v0` against the schema
document alone still will not catch this. Neither does it catch the answerability rule. Both are
learned by being refused.

## The expense the item predicted, paid

5.37 said the harness-refuses option was "the more expensive, since `src/mycelium/eval/` is a
tuning path and cannot move with a judgement change". It is, and it was: removing the lint
touches `cases.py`, so `verify.py` derived `retrieval` and the gates ran.

Nothing moved. No judged set changed, so the frozen-set conjunction is not merely satisfied but
irrelevant. `retrieval_identity()` is byte-identical to the one `eval/g2-verdict.json` records —
checked before and after — so G2 needed no re-record, which is the case the memory of 5.19
already described: the digest reads constants out of `retrieval.py`, and this touched none.

## Lesson

An item that a later PR appears to have absorbed deserves a grep before it deserves a checkbox.
5.33's entry was accurate about everything it did; the gap was in what it did not say, and no
amount of reading it would have surfaced that. The call graph did, immediately.
