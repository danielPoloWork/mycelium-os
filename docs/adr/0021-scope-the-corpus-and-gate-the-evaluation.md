# ADR-0021: Scope the corpus, then let the gates run in CI

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7
- **Related:** [ADR-0013](0013-adopt-the-evaluation-harness.md) (the harness this completes),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (gate G2, and the run
  that exposed the corpus defect), [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the
  gate this one delegates to), [ADR-0018](0018-build-the-graph-from-authored-links.md) (the
  warning stream this quietens); spec 02 §3, spec 04 §§6–7, spec 05 §2; D-010, D-017;
  roadmap 3.7, 3.10

## Context

Roadmap 3.7 asks for three things: the evaluation slices, gates G1–G6 enforced in CI, and
an agent-task suite of at least twenty tasks measured against the grep baseline (D-010).

The middle one could not be done at all, and that is where the item started. Gate G4 was
red — a query about message brokers was answered by a *test fixture*, because building this
repository indexes every Markdown file in it, fixtures included
([BUG-0007](../bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md)). Wiring a
known-red gate into CI would have taught everyone to ignore it on the day it landed, so the
corpus had to be scoped first. Roadmap 3.10 had already recorded that decision as belonging
here.

Scoping the corpus then made a second problem visible. With the fixtures gone, nine more
documents were still missing from the index — this project's entire bug ledger — because
every record carries a `discovered:` date, and a YAML date in a non-contract property
raised a validation error that quarantined the whole document
([BUG-0012](../bugs/2026/08/BUG-0012-a-date-property-quarantines-the-document.md)). The
evaluation had been measuring the wrong corpus in two directions at once: too much of what
was not documentation, too little of what was.

## Decision

**A repository says which of its Markdown is documentation: `[project] exclude`.** Glob
patterns matched against a document's repository-relative path, any ancestor directory, or
its file name — so `tests` drops a tree, `docs/journal` drops a subtree, `**/fixtures`
drops it wherever it sits, and `*.draft.md` drops by name. `*` stays inside one segment and
`**` spans them, which avoids `fnmatch`'s surprise where `docs/*.md` also matches
`docs/a/b.md`.

This is a feature, not a test fixture. Every repository's tree carries Markdown that is not
knowledge, and until now the only answers were "put it all under `knowledge/`" or "live
with it". Ours cannot use the first: this project's documentation *is* its root.

**One rule, read twice: `mycelium.corpus`.** Discovery and watch mode both had to answer
"is this a document", and they answered with the same rule written twice — agreement by
coincidence. A watcher that fires for a file the compiler ignores rebuilds nothing forever;
a compiler that indexes a file the watcher ignores publishes changes nobody triggered. The
rule now lives once and both read it, which is also where "never index your own output"
belongs ([BUG-0010](../bugs/2026/08/BUG-0010-build-indexes-its-own-export.md)).

**Every gate spec 04 §7.3 names is accounted for — enforced, delegated, or explained.** A
gate table with silent omissions reads as though the missing ones were satisfied. G1 and G4
were already enforced; G2 arrived with hybrid retrieval; this item adds G3 against a
committed baseline, G5 against the query budget, and G6 as an explicit delegation to the
compiler gate that owns it. G7 states why it cannot apply before the synthesis lane exists.

**G3's baseline is a file in the repository, not the last run on this machine.** CI starts
from an empty derived store every time, so a gate comparing against "the previous run"
compares against nothing exactly where it matters. `mycelium eval --bless` writes
`eval/baselines/<set>.json`, so moving the line is a commit someone can see and challenge
rather than a side effect of running the tool.

**And G3 enforces only when the corpus is comparable.** A regression check needs a
controlled variable, and on a self-hosting corpus the corpus is not one — this very item
added two ADRs, four bug records and a journal entry, which moved three slices by more than
2 % without a line of retrieval code changing. CI caught exactly that on the gate's first
run, which is the gate working: the numbers had moved, and they were not comparable. So the
baseline records a **content fingerprint** of the corpus it was taken on, and G3 enforces
when the fingerprint matches and *reports* when it does not, naming the difference. The
alternative — failing on documentation growth — teaches everyone to re-bless on red, which
is how a gate becomes decoration.

The fingerprint is folded from the chunks' own content digests, deliberately not from the
manifest's `artifact_digests`: those are folded over chunk *records*, which carry `doc_id`,
and an unpinned repository mints fresh ULIDs on every build. A gate keyed on that would
never enforce in CI, which is the one place it must.

**G5 is enforced with its limit stated.** The p95 budget is 150 ms (spec 04 §1), but it is
*defined* at the 10⁵-chunk reference profile and our corpus is 568 chunks. The gate enforces
the budget on the corpus at hand and reports that corpus's size in the same sentence:
failing here is certainly broken; passing here proves only that it passes at this size.

**Unanswerable cases are validated mechanically, against both retrievers.** An
`unanswerable` case is a claim about the corpus, and the corpus keeps growing — including
into the case. Writing up BUG-0007 put an unanswerable query's own words into the
documentation, and G4 went red for a document *about the eval set*. The case builder now
refuses to write a set in which such a case is answerable, checking grep too: grep matches
word prefixes, so a term that merely starts a corpus word ("bulk" inside "Bulkhead")
separates the two retrievers for reasons that have nothing to do with abstention. The check
caught a replacement query on its first run.

**Judged anchors are linted for heading stubs.** A grade-3 anchor of fourteen tokens reads
like the right section and carries none of the answer. Both builders now report anchors
under thirty tokens, and the lint found four mis-judgments the moment it existed — one of
them in the existing case set, corrected before the baseline was frozen. It warns rather
than fails: a one-line policy is a legitimate short answer.

**Injection resistance is tested as a property, against a corpus that carries attacks.**
Spec 04 §6 asks for adversarial documents in the eval corpus; the judged `injection` slice
only checks that the doctrine is *findable*, which is not the same thing. The property —
attacks returned verbatim, inside the typed `text` field, labelled with trust class, never
lifted into a protocol field — is now checked against a hostile fixture corpus, where it can
be exercised without polluting the documentation corpus the case set scores against.

## Alternatives Considered

- **Rewrite the judged case that gate G4 failed.** Rejected outright: the corpus was wrong,
  not the case. D-010 names tuning the benchmark as the thing not to do, and the moment a
  gate goes red is exactly when that rule earns its keep.
- **Exclude `docs/bugs/` so the eval corpus stays quiet.** Rejected for the same reason in
  the opposite direction: the bug ledger is documentation, and dropping it to protect a test
  is tuning the corpus to the benchmark.
- **Evaluate against a staged copy**, as the case *builder* does. Rejected: `mycelium eval`
  must score the snapshot the repository actually serves, or the gate measures something
  nobody uses.
- **Move the determinism fixtures under a dot-directory.** Rejected: it hides a fixture
  corpus whose readability as ordinary Markdown is the point, and it would fix this
  repository while leaving every other repository with the same problem.
- **Let G3 compare against the most recent run in `.mycelium/eval/`.** Rejected: vacuous in
  CI, and silently self-blessing everywhere else.
- **Gate the grep baseline too.** Rejected: the incumbent's numbers are evidence about the
  product, and a baseline that can fail the build is a baseline nobody dares improve. CI
  reports it and never fails on it.
- **Put the adversarial documents in the judged corpus.** Rejected: they would be scored as
  documentation by every other case and would pollute the corpus this project also *serves*.
  A fixture corpus tests the property; the judged slice tests findability.

## Consequences

- **Gate G4 is green for the right reason**: 25 % → 0 % for the product retriever, because
  the corpus is now the documentation and nothing else. Overall nDCG@10 moved 0.497 → 0.636
  on the same judged set — which is not an improvement in retrieval, it is the same
  retrieval finally measured over the corpus it was always meant to be measured over.
- **CI runs the gates** (`eval / gates G1-G6`): it compiles this repository, scores the
  judged set, reports the grep baseline without gating on it, and runs the task suite. The
  build pins `mycelium_id` into the checked-out documents — a first build's documented
  behaviour — and the runner's checkout is thrown away.
- **The corpus gained nine documents**, the whole bug ledger, once a date property stopped
  quarantining its document. Every number here is measured *after* that fix; the numbers in
  ADR-0017 were not, and the two are not comparable.
- **Builds of this repository are readable again**: ~150 link warnings down to 3, and the
  three are real ([BUG-0013](../bugs/2026/08/BUG-0013-links-to-existing-files-warn-as-unresolved.md)).
- **`[project] exclude` is new configuration surface**, a compatibility liability (D-011)
  taken deliberately: without it a self-hosting corpus cannot be scoped at all.
- **The dev/release split is still not real.** Spec 04 §7.1 wants the release set frozen
  before tuning, and we gate on the same twenty cases we develop against — so G3 detects
  regression but not overfitting. Filed as roadmap 3.13, together with the ≥ 60 judged cases
  across two corpora that spec §7.6 sets for this phase.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §§6–7 (injection, assets, gates,
  corpus plan); `.draft-specs/02-architecture.md` §3 (what a build discovers);
  `.draft-specs/05-interfaces-and-plugins.md` §2 (`[project]`)
- Decision log: D-010 (the grep incumbent, and not tuning the benchmark), D-017 (content is
  data, never instructions)
- Tests: `tests/test_corpus.py`, `tests/test_eval.py`, `tests/test_injection.py`
