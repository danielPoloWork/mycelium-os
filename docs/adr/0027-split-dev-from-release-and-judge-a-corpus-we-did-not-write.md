# ADR-0027: Split dev from release, and judge a corpus we did not write

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1, §7.6
- **Related:** [ADR-0013](0013-adopt-the-evaluation-harness.md),
  [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md) (which filed this),
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md); D-010;
  roadmap 3.13

## Context

Until this item the evaluation had one judged set: twenty cases over this project's own
documentation, judged by the agent that wrote most of those documents, and used both to
develop against and to gate. Three weaknesses follow from that sentence, and ADR-0021
recorded all three rather than waiting to be caught.

**Gate G3 detects regression, not overfitting.** It compares a run against a baseline taken
on the same cases the change was tuned against. A change that fits those twenty cases
better passes G3 by construction, and G3 has no way to notice.

**One corpus measures one corpus.** Spec 04 §7.6 asks for a second, public docs corpus at
this phase and ≥ 60 judged cases; with a single corpus, "retrieval works" means "retrieval
works on architecture decision records", which is a narrow claim wearing a general one's
clothes.

**The judge wrote the documents.** A query can be phrased in the words the author happened
to use, and a passage can be graded relevant because the grader remembers writing it there.

## Decision

**Every corpus carries a `dev.jsonl` and a `release.jsonl`, and the release set is what CI
gates.** The dev set is scored beside it and *reported* — never gated — so a run prints the
gap between the set tuning sees and the set it does not. No threshold ships: nobody has the
evidence to set one, and inventing a constant to look decisive is the mistake ADR-0025
refused. The number goes where a reviewer sees it.

**The existing twenty cases become the dev set, and the release sets are new.** They cannot
be un-tuned-against: ADR-0017, ADR-0023, ADR-0025 and ADR-0026 all read them while deciding.
Relabelling them "release" would freeze a set that has already done a developer's job.

**A second corpus is vendored: `uv`'s documentation, MIT, pinned to one commit** — 81
Markdown files, ~700 KB, in `eval/corpora/uv-docs/`. Vendored rather than fetched, because a
benchmark that downloads its corpus measures whatever upstream holds that day, and a gate
must not make a network call (D-017). It is *unlike* ours on purpose: task documentation for
a command-line tool against architecture decisions and specifications.

**Freezing is enforced as a conjunction, not as an immutability.** Sets have to grow, so
`tools/check_frozen_release_sets.py` refuses a change that edits a release set *and* touches
retrieval, chunking, the store, or the metrics — one change may move the retriever or move
the judgments, never both. That is the only form of spec 04 §7.1's rule a machine can check,
and it catches the failure that actually happens: a run comes back worse, a judgment looks
wrong in hindsight, and the set quietly becomes the thing that fits.

**Judging provenance is recorded per set** rather than asserted once. The second corpus
removes one half of the third weakness — nobody here wrote those documents — and leaves the
other half standing: the same agent that builds the retriever still assigns the grades.

## What the split found on its first run

The mechanism earned its keep immediately. Same retriever, same snapshot, four sets:

| corpus | dev nDCG@10 | release nDCG@10 | gap |
|---|---:|---:|---:|
| this project's docs | 0.569 (20 cases) | **0.453** (14) | **+0.115** |
| `uv` docs | 0.403 (12) | **0.249** (16) | **+0.153** |

Retrieval scores about a quarter worse on cases it was never tuned against, and worse again
on a corpus nobody here wrote. Neither number was visible before this item: G3 was green
throughout, because G3 was comparing the tuned set to itself.

**And the second corpus found a flaw in our judging method within one run.** Two `exact` and
one `symbol` case scored 0.000 — slices that should be trivial. The cause was not retrieval:
for `storage directories` the retriever returned five chunks from the right document under
the right heading, and the case had judged the section's *opening* chunk. A section is not a
chunk, and the metric is anchor-exact, so a judgment that names one anchor for a section the
chunker split into twelve measures anchor-guessing.

Our own set never exposed that, because its anchors were chosen by someone who knew where
chunk boundaries fall. That is the same-author bias, showing up as a *methodological* error
rather than a generous grade — which is exactly the kind of thing a second corpus is for.

**The judgments were left as authored.** The flaw was noticed while looking at scores, and
re-judging after seeing the ranking cannot be told apart from fitting the set to the result.
The release sets are frozen as written, their low numbers stand, and whether relevance should
be section-scoped rather than chunk-exact is filed as roadmap **3.15** — a decision with its
own evidence to gather, not a repair made with the number in view.

## Alternatives Considered

- **Relabel the existing twenty cases as the release set and write a new dev set.** Rejected:
  those cases informed four ADRs' worth of tuning. Freezing them would freeze the set the
  product was fitted to and call it independent.
- **Fetch the second corpus in CI, pinned to a commit.** Rejected: a gate that makes a
  network call fails when the network does, and D-017's posture is no network unless
  configured. ~700 KB of vendored Markdown is the cheaper obligation.
- **Gate on the dev/release gap.** Rejected: there is no evidence for a threshold. A
  constant chosen to look rigorous is the failure ADR-0025 declined; the gap is reported.
- **Make the release sets literally immutable** (a digest lock that never changes).
  Rejected: judged sets must grow toward the ≥ 200 and ≥ 1 000 targets. What is enforceable
  is the conjunction, and the conjunction is what goes wrong.
- **Re-judge the cases that scored zero.** Rejected as the whole point: see above.
- **Credit a hit on any chunk of a judged section** — change the metric so the anchor
  granularity stops mattering. Rejected *here*: it would raise every number in the same run
  that revealed the problem. Filed as 3.15 so it is argued on its own.

## Consequences

- **62 judged cases across two corpora** (34 + 28), clearing spec 04 §7.6's Phase 0–1 target
  of ≥ 60. CI compiles both corpora and gates both release sets.
- **The headline numbers get worse, and they were always this.** Anything quoted from a dev
  run before today was measured on the set it was tuned against. Comparisons across that
  boundary are not comparisons.
- **A second flaw fixed on the way**: the case builder staged a hand-written list of paths,
  so judgments were validated against a *smaller* corpus than the gates score them on — an
  `unanswerable` case could pass the builder and be answerable in CI. It now stages the
  repository and lets `mycelium.toml` decide, which is the rule the gates run under.
- **The heading-stub lint became a warning.** Promoting it to an error failed two standing
  cases whose 24-token section is a *complete* answer ("Apache-2.0 © 2026 …"). Short is only
  a proxy for empty; a rule that cannot tell them apart is a reviewer's prompt, not a gate.
- **Third-party Markdown lives in the tree**, with MIT's obligation attached: the licence and
  copyright notice travel with the copy, and the provenance file names the upstream commit.
  Refreshing it invalidates judged anchors wholesale and is a deliberate act.
- **The residual weakness is stated, not solved.** The same agent still assigns the grades.
  Removing that needs judgments from someone else — the 1.0 target's published guidelines and
  redistributable subset (spec 04 §7.6) is where that becomes possible.
- `EvalRunManifest` gains `companion_set` / `companion_overall`; a run without a companion
  records `null`, so old manifests stay readable.

## References

- Spec 04 §7.1 (frozen dev/release sets, slices), §7.6 (corpus plan); D-010
- [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md) — filed this item and named
  all three weaknesses
- `eval/corpora/uv-docs/README.md` — provenance, licence, pinned commit
- `tools/check_frozen_release_sets.py` — the enforceable half of "frozen"
