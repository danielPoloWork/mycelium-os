# ADR-0068: Give gate G2 a runner by dating its verdict, not by re-running it everywhere

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.40 (this item), 4.33 (where it was filed), 4.41, 4.43; RFC-0001;
  spec 04 §§3, 7.3, 7.5; D-010, D-013;
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md),
  [ADR-0051](0051-hold-the-judgements-fixed-too.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0055](0055-run-the-gates-the-change-implicates.md),
  [ADR-0059](0059-make-the-plan-one-implementation-too.md),
  [ADR-0064](0064-measure-the-gate-that-decides-the-default.md)

## Context

Gate G2 decides the product's default retrieval profile. ADR-0064 found that nothing had
run it for three milestones: it fires only when a human passes `mycelium eval --retriever
hybrid`, CI never does and cannot — the hybrid arm needs the 133 MB embedding model and
D-013 downloads nothing unless configured — and `tools/verify.py` had no step for it.
Meanwhile the *lexical* leg G2 is measured against moved four times: chunk packing (roadmap
4.15), stemming (4.19), function-word stripping (4.28) and the heading split (4.36). A
comparison whose two arms move independently and are never re-compared is a claim.

Roadmap 4.40 proposed the shape: a step in `verify.py`'s `retrieval` mode that runs G2 when
the model is present and says so by name when it is not, plus — as "a cheaper half-measure
worth pricing" — asserting in CI that the committed verdict carries a date and a corpus
fingerprint.

Three facts, established while building it, decided the design instead.

**One: G2 cannot be run as a pass/fail gate at all.** `--gate` exits non-zero when *any*
gate reports `passed=False`, and `_gate_g2` reports `passed=False` when hybrid does not
earn the default — which is the shipped configuration. Milestone 3's own exit gate says
"lexical-only default is a legitimate G2 outcome"; spec 04 §7.3 puts the burden on hybrid.
So `mycelium eval --retriever hybrid --gate` would have been red on every correct build.
That is not an oversight in the wiring; it is the reason no wiring was ever possible.

**Two: the thing that goes stale is not the number, it is the claim.** G2's verdict is
"hybrid has not earned the default *against this lexical leg, on these corpora, under these
judgements*". Every one of those qualifiers is checkable without the model. The verdict's
*numbers* are not: ADR-0017 declares the embedder non-deterministic across platforms,
runtime versions and instruction sets, so a float measured on a runner is not comparable to
one measured on a maintainer's machine.

**Three: nothing described the lexical arm faithfully enough to notice it moving.** The
retriever's own `config` — what a run manifest records to be reproducible — carried
`"weights": "title=3.0,heading=2.0,body=1.0,ancestors=0.5"` as a **hand-typed string**, in
two places, beside the numbers it claimed to describe. Roadmap 4.42 is a pending change to
exactly those weights. A currency check keyed on that string would have looked current
through the very change it exists to catch. `stopwords` was recorded as a *count*, so
swapping one function word for another would also have been invisible.

## Decision

**Commit G2's verdict with the fingerprints that date it, and make the runner ask whether
the record still describes this product.**

`eval/g2-verdict.json` records, for all six judged sets, both arms' nDCG@10, the per-slice
figures, the verdict, and what each set was measured on — plus one decision (`lexical`), the
shipped profile it must agree with, the date, the model id, and a **retrieval identity**.

`tools/measure_hybrid_gate.py --check` is the runner, and it is what `tools/verify.py`'s
`retrieval` mode and CI's `eval` job run. It has two tiers, and the split is the whole point:

| tier | needs the model | what it fails on |
|---|---|---|
| currency | no | the retrieval identity, the shipped default, the dated corpora's content, the judged sets' digests |
| reproduction | yes | a per-set **verdict** that flipped, or a decision that moved |

The reproduction tier compares verdicts, never floats, for fact two above; the measured
numbers are printed beside the recorded ones so drift is visible without being gated on.
Where the model is absent the runner **says so by name** — the shape the embeddings tests
skip in — because a run that could not re-measure must say it, or no output reads as a pass.

**It never fails because hybrid lost.** What it fails on is a verdict that no longer
describes the product, which is a mistake someone can act on in one command.

**`retrieval_identity()` is added to `mycelium.retrieval`**, and it reads every field from
the module that owns it at call time: the BM25 field weights, the stem weight, the stopword
**membership**, the fusion constants, and the FTS schema version. Each of the four lexical
changes that moved G2's verdict underneath itself moves at least one of them — which is the
check that it is a fingerprint and not a decoration. To make that true, the weights string
is now **rendered from `_SURFACE_WEIGHTS`** (`describe_field_weights()`) rather than typed,
and the two hand-written copies are gone. G2's two thresholds move from
`measure_hybrid_gate.py`'s private constants into `mycelium.eval.harness` as
`G2_OVERALL_MIN` / `G2_SLICE_FLOOR`, so the tool that dates the gate and the gate itself
cannot disagree about what the gate says (ADR-0059's lesson).

**CI does not fetch the model, and this is the argument rather than the omission.** The cost
is small and measured — 127.6 MB of model files, and the six-set measurement runs in 12–25 s
on this machine — so cost is *not* the reason. The reason is that a measurement CI took
could not be compared with the committed one except by verdict, and a verdict computed on a
runner is a different measurement from the one on record: recording CI's would make the
verdict a property of the runner image. What CI can do without ambiguity is refuse a stale
claim, and that is what it now does. Reversing this needs one thing measured first — whether
the per-set verdicts agree across machines — and that measurement requires a runner, so it
is a piece of work rather than a line to add.

**`ours` is measured and reported, never gated.** This repository is its own corpus and
every pull request moves it — an ADR, a roadmap line, this file. A check that failed on its
content fingerprint would demand a re-measurement of G2 for a typo in a README. The two
vendored corpora, which move only when someone vendors something, are what the check is keyed
on. That is the distinction gate G3 already makes (ADR-0045) for the same reason: a control
that fires on everything selects for being ignored.

**And the ladder test now reads scripts, not only `mycelium` commands.** 4.40 asked that
`tests/test_verify_ladder.py` keep the new step and the workflow in agreement; the step is a
tool, and the test read only `mycelium` invocations. Widening it exposed two gates that were
already CI-only — `build_ingested_corpus.py --check` and `build_ingested_cases.py --check`,
the ingestion reproductions — so ADR-0059's defect was still live in a job it had not looked
at. Both join `verify.py`'s `code` plan, measured at 64 s and 15 s on this machine. A tool's
**flags** are compared and its positional arguments are not: `--check` asks a different
question from the bare form, while `check_frozen_release_sets.py` legitimately takes the
PR's base SHA in CI and `origin/main` locally.

## Alternatives Considered

- **Run `mycelium eval --retriever hybrid --gate` as the step** — the obvious reading of
  "give G2 a runner". Rejected on fact one: `--gate` exits non-zero on `passed=False`, and
  for G2 that is the shipped configuration. It would be red on every correct build, which is
  how a gate becomes something everyone passes a flag to skip.
- **Change G2's boolean so "lexical earns it" is a pass.** Tempting, and it is the right
  question — but it is **4.41's** question, filed explicitly to be answered *while no
  candidate is pending*, and the per-set form cannot express the decision anyway: the
  decision is over all three release sets together, and today `ours/release` passes while
  the two `uv` sets fail. Answering it inside a PR that also ships a runner would settle a
  gate's meaning as a side effect. 4.41's line now carries the finding.
- **Have CI fetch the model and re-measure.** Priced rather than dismissed: 127.6 MB and
  12–25 s, cacheable to about nothing after the first run. Rejected for comparability, not
  for cost — see the Decision. The half of it that *is* attractive, a neutral second machine
  for the numbers, is what the reversal above would buy.
- **Gate on the recorded floats within a tolerance.** Rejected: the tolerance would be a
  parameter with no evidence behind it, on a project that has refused thirteen re-rankings
  for exactly that reason. Verdict comparison needs no constant.
- **Fingerprint the retriever's `config` dict as it stood.** Rejected on fact three: it was a
  hand-typed weights string and a stopword *count*. Fixing those was the precondition for the
  check being worth running, so the fix ships here rather than being assumed.
- **An age bar on the record** ("re-measure if older than N days"). Rejected: N is a
  parameter nobody has evidence for, and a verdict does not go stale with time — it goes
  stale when something it was measured against moves, which is what the fingerprints say.
- **A `deferred: true` escape hatch in the record**, so a ranker change could land without
  the model. Rejected: an escape hatch one field away is the same as no gate. The remedy is
  one local command, and the pressure it applies — a ranking change must say what it did to
  the default-profile decision — is the pressure whose absence this ADR is about.
- **Exempt the two ingestion reproductions instead of running them.** Rejected: writing an
  exemption for drift discovered *by the test whose job is to catch drift* is indefensible,
  and the tool's own doctrine is to over-verify rather than skip (`DOC_SUFFIXES`).

## Consequences

- **G2 has a runner, and it runs on every retrieval change.** Locally at `retrieval` mode,
  in CI's `eval` job, and — where the model is present — as a real re-measurement whose
  verdicts must reproduce.
- **A ranking change must now re-record G2 to land.** Moving a field weight, the stem weight,
  a stopword, a fusion constant or the FTS schema moves the retrieval identity, and `--check`
  fails naming the remedy. Roadmap 4.42 is the first change that will pay this, which is the
  intended order: it is a change to the lexical arm G2 is measured against.
- **A contributor without the model can still verify everything else.** The currency tier
  needs no model and the runner names what it could not do. What they cannot do is *record* a
  new verdict — which is the honest constraint, not a defect in the tool.
- **The verdict is unchanged, and re-measured here.** On the current tree: `ours/dev` fails
  (+6.8 %, `fact` −5.6 %), `ours/release` passes (+20.9 %), `uv/dev` passes (+23.2 %),
  `uv/release` fails (+10.7 %, `conceptual` −13.1 %), `uv-ingested/dev` passes (+23.1 %),
  `uv-ingested/release` fails (−3.1 %). Three of six, exactly ADR-0064's shape; the release
  rows put the decision at `lexical`, and hybrid keeps the burden of proof.
- **The numbers moved since ADR-0064 and the record explains why.** `uv/dev` reads 0.6092
  lexical against 0.6727 a day earlier — 4.39's ten new cases (ADR-0067) — and `ours/*` moves
  with this repository's own documents. That is precisely the drift the record exists to date.
- **No product behaviour changes.** `describe_field_weights()` renders the string the two
  literals contained, byte-for-byte, so no run manifest's `config_digest` moves and no
  baseline is re-blessed.
- **`verify.py`'s `code` mode costs about 79 s more on this machine.** Two gates that were
  CI-only now run locally, which is the point; the number is stated so it can be argued
  with.
- **Filed on the way: roadmap 4.43.** `tools/` is neither linted nor type-checked — the plan
  and CI both run `ruff check src tests` and `mypy --strict src` — so this tool, which CI now
  gates on, is unchecked. `ruff check tools` reports one error; `mypy --strict tools` reports
  184, almost all of them cascading from `mycelium` shipping no `py.typed` marker, which is
  also a gap for anyone consuming the SDK it advertises.

## References

- Spec 04 §7.3 (gate G2's two conditions), §7.5 (a report without a manifest is
  exploratory), §3 (field weights, fusion); D-010, D-013.
- Reproducible with `python tools/measure_hybrid_gate.py --check`; re-recorded with
  `--record` (needs the model). The bare form and `--cases` are unchanged, so ADR-0064's
  own reproduction command still means what it said.
- [ADR-0064](0064-measure-the-gate-that-decides-the-default.md) — the measurement that
  found the gate had no runner, and filed this.
- [ADR-0059](0059-make-the-plan-one-implementation-too.md) — the drift this extends: one
  implementation for the plan, now including the gates written as scripts.
- [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md),
  [ADR-0051](0051-hold-the-judgements-fixed-too.md) — the two fingerprints this record
  reuses, and the enforce/report distinction it borrows.
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the original G2
  verdict, and the non-determinism declaration that makes verdict comparison the only
  portable one.
