# ADR-0113: Close a milestone on its gates, and carry an unmet one by name

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 / spec 06
- **Related:** [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md) (the first gate, and
  why a refusal is a pass), [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (the second, and the one core change), [ADR-0112](0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md)
  (the re-bless that must precede the release cut), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (a gate that fires on everything selects for being ignored); `.draft-specs/06` §Phase 3;
  roadmap 5.3, 5.5, 5.6, 5.43, 6.8, 6.11, 6.12

## Context

Milestone 5 closed its last open item on 2026-09-14 and the maintainer asked for the exit
review before cutting the release. The question a review has to answer is not "is the list
empty" — it was empty — but *which of the milestone's exit gates hold*, because the list and
the gates are different objects and only one of them is the contract.

`.draft-specs/06` §Phase 3 sets four exit gates. Measured against the repository rather than
against the roadmap's restatement of them:

| gate | status | evidence |
|---|---|---|
| graph expansion earns default-on or stays opt-in, **measured either way** | **met** | 5.3 / ADR-0075: built, ablated, refused, ships off |
| `chats` passes its document-08 gates using zero core patches | **met** | 5.5 / ADR-0077: a test class per gate in `contrib/chats/tests/test_acceptance.py` |
| stale-anchor handling proven on a heavily refactored corpus | **met** | 5.6: eleven named refactorings, outcome pinned per citation |
| ≥ 10 external repos dogfooding | **not met** | zero |

The second deserves its precision, because "zero core patches" and "one core change" sound
like a failed gate. Document 08 §10's sixth gate reads *"the module uses only public D-023
mechanisms — zero core patches. **Any needed core change is an API fix, made before the 1.0
freeze.**"* The one change — the configuration carrying a `[chats]` table to the module that
owns it — is that sentence's own case, made a milestone before the freeze.

### Two things the review found that the roadmap said otherwise

**The roadmap's copy of the gates had drifted in both directions.** It listed *≥ 200 judged
cases across ≥ 3 corpora*, which §Phase 3 puts under **Scope**, and omitted stale-anchor
handling, which is an exit gate. So the milestone had been tracked against a criterion that is
not a gate while a real one went unlisted — and, as it happens, the unlisted one is met and the
mis-listed one is not: 133 case records across three corpora, of which only 86 are
independently judged, the twin's 47 being mechanically carried (ADR-0039).

**The version labels would have mis-cut this release.** The roadmap named M5 *v0.3*, which is
what the spec's phase numbering calls Phase 3. But M1 and M2 shipped v0.1.0 and v0.2.0, which
the phase numbering does not count, so every label since has been two behind what shipped: M3
released v0.3.0 under the label *v0.1*, M4 released v0.4.0 under *v0.2*. M5 cuts **v0.5.0**.

### The blocker under the unmet gate, which nothing had named

The repository is public with one star and no forks, and every merged pull request is authored
by the owner or by Dependabot. Forty-three M5 items could not have moved that number, and the
reason is one step earlier than adoption: **the package is not published anywhere.**
`release.yml` builds the wheel and the sdist, refuses a build whose version does not equal the
tag, attaches both to a draft GitHub Release, and stops. No registry appears anywhere in
`.github/`. `docs/workflow/packaging.md` nonetheless described a publish flow in the present
tense — *"A human approves the publish step; CI pushes to the registry"* — and the README tells
a reader to `pip install mycelium-os[embeddings]`.

## Decision

**Milestone 5 closes on three of its four exit gates, and the fourth is carried into Milestone 6
by name rather than waived.** Roadmap **6.12** owns it, states that it stands at zero, and lists
what it actually needs in order: a published package (6.11), the docs site (6.2), the
contribution ladder (6.6), and then outreach, which is the maintainer's and not an agent's.

**A milestone closes on its exit gates, not on an empty item list, and an unmet gate is carried
with an owner.** This is the stopping rule the M4 review asked for, now applied and recorded.
The alternative — holding M5 open until every gate is met — would keep a milestone open on a
criterion no engineering work inside it can move, which makes the milestone boundary meaningless
in the other direction.

**The roadmap's copy of the gates is restated from the spec**, with the deviation noted where it
was, so the next review reads the contract rather than a paraphrase of it. The ≥ 200 case figure
is not dropped: 6.8 owns it and has measured that the per-slice conditions need far more.

**Every milestone heading carries the version it shipped or will ship.** M6 keeps v1.0.0,
because there the phase name and the release agree.

> **Corrected by the maintainer, 2026-09-14, before the v0.5.0 cut.** The second sentence does
> not survive the rule the first one applies. AGENTS.md §11 increments `MINOR` with each
> completed milestone pre-1.0, and that is exactly how M1–M5 were relabelled here — so M6 ships
> **v0.6.0** and 1.0 lands at **M7**, which is now labelled v1.0.0. "The phase name and the
> release agree" was the spec's *Phase 4* name reasserting itself in the one place I had not
> checked it against the cadence, which is the same mistake this ADR was written to fix, made
> once more inside the fix. The roadmap and the README carry the corrected labels.
>
> One thing this leaves open, and it is not settled here: M6's exit gates still include
> *"1.0 compatibility promise published"* while M6 now ships v0.6.0. Whether that promise
> publishes at M6 or at M7 belongs with 6.1, the contract freeze, which is where it has to be
> answered anyway.

**`packaging.md` is corrected to describe what exists**, with the intended registry step named as
roadmap 6.11 instead of written as fact. Making the README's install lines true belongs to that
item, not to this one.

## Alternatives Considered

- **Hold M5 open until the dogfooding gate is met.** Rejected: it is an adoption number, it is
  blocked on a package that does not exist, and no 5.x item could move it. A milestone that
  cannot close by working on it is not a milestone.
- **Waive the gate, or quietly drop it from the list.** Rejected, and it is the outcome this ADR
  exists to prevent: the roadmap had *already* dropped a gate by paraphrase, and nobody noticed
  for a milestone. A gate that can be lost by restatement is not a gate.
- **Re-cut the number now** — say ≥ 3 repos, or count installs instead of repositories. Rejected
  *here* while keeping the question open in 6.12: ten may well be the wrong number for a pre-1.0
  tool nobody has heard of, but re-cutting a gate in the same act as failing it is how a bar
  becomes whatever was achieved. The re-cut, if it comes, is its own decision with its own
  evidence.
- **Fix the version labels inside the release PR.** Rejected on ordering. The release PR rewrites
  the README status table and the changelog index — the very places the labels are wrong — so
  fixing them there would mean cutting a release whose own notes carry the mistake, and the
  correction would be invisible among the release's other edits.
- **Leave `packaging.md` and let 6.11 fix it.** Rejected: it states as fact a CI step that does
  not exist, and this repository has twice now found a docstring promising something nobody
  built (ADR-0100, ADR-0107). The sentence is corrected on sight; the capability is filed.

## Consequences

- **M5 ships as v0.5.0**, and the ordering is fixed by ADR-0112: the corrections land first,
  then `ours/release` is re-blessed as its own PR (release.md step 0), then the release PR is
  cut. Each step moves the corpus, and the baseline has to describe the corpus the release is
  cut from.
- **Two exit gates now have owners that did not exist before this review.** 6.11 (publish) and
  6.12 (dogfooding) are the first roadmap items in the project's history that are not
  engineering work on the compiler or the evaluation.
- **The trajectory is on the record.** 43 items closed against 7 planned at the plan phase, so
  84 % were self-filed, across 44 pull requests in five days — the same self-filing ratio M4 ran
  at. Unlike M4, whose open count oscillated between two and eight, M5's reached zero. The
  stopping rule is what makes that a closure rather than a coincidence.
- **What M5 built for retrieval ships mostly off, and that is the gates working.** Hybrid and
  graph expansion are disabled because the ablation refused them; symbol lookup is on because at
  5.25 it finally earned it, after the same ablation had refused it three times.
- **A limit, stated:** three of the four gates were verified against artifacts in this
  repository, and the fourth is a fact about the world that this repository cannot observe. If
  6.12's number is ever re-cut, it should be re-cut to something the project can measure without
  asking anyone to self-report.

## References

- `.draft-specs/06-roadmap-and-governance.md` §Phase 3 — the four exit gates, verbatim.
- `.draft-specs/08-module-chats.md` §10 — the six acceptance gates, and the sixth's second
  sentence.
- `.github/workflows/release.yml` — the draft-only flow, and the absent registry step.
- The M4 exit review, 2026-09-08, which asked for the stopping rule this applies.
