# ADR-0137: Let a gated default follow its ablation, and narrow the rule that would refuse it

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 / spec 04 §§3, 7.1
- **Related:** [ADR-0136](0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md)
  (the authoring that produced this evidence),
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (the leg, and the rule that its default follows the ablation),
  [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md) (which switched it on,
  on the measurement this supersedes),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md) (a ranking change earns
  its default on a set it was not developed against),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) and
  [ADR-0123](0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md) (what a four-case
  slice can say, and the count that makes a slice mean something),
  [ADR-0056](0056-make-the-format-assignment-append-only.md) (the precedent for retiring a
  proxy rule when the direct check exists),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) (the freeze
  this narrows, and why it exists), [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md),
  [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (the other two gated defaults); spec 04 §§2, 3, 7.1, 7.3; D-010; roadmap 5.25, 6.8

## Context

Roadmap 6.8 authored the judged release sets to the count `enforceable_at` derives (ADR-0136).
One of the rows it grew was `uv`'s `symbol` slice: **four cases to fifty-eight**. The cases were
written from the documents and committed before anything was scored on them, and then the
ablation was run.

It inverted.

| set | lexical | with the leg | symbol slice | verdict |
|---|---:|---:|---:|---|
| `ours/release` | 0.4826 | 0.4826 | — | inert |
| `uv/dev` | 0.6143 | 0.6224 | +7.7 % | earns |
| `uv/release` | 0.6903 | 0.6954 | **+5.0 %**, overall +0.7 % | earns |
| `uv-ingested/dev` | 0.6127 | 0.6193 | +7.3 % | earns |
| `uv-ingested/release` | 0.6477 | 0.6431 | **−5.8 %**, overall **−0.7 %** | does not |

The bar has not moved: a default flip needs a *release-set* gain **with no overall regression on
any set** (ADR-0080, following ADR-0070). `uv-ingested/release` regresses, so the leg no longer
clears it.

**What changed is the denominator, not the leg.** ADR-0096 switched `symbol_lookup` on at
roadmap 5.25 on a held-out gain of **+5.6 % on a slice of four cases** — and said so at the time,
in the caveat it insisted on putting in the record rather than a footnote: *"on the release sets
the gain is one case"*. Fifty-eight cases later, that one case is a minority of a slice that
moves the other way on the projected corpus. This is exactly the failure ADR-0044 described and
ADR-0123 quantified, caught by the instrument built to catch it.

**And it collided with a rule.** `tools/check_frozen_release_sets.py` refuses a change that moves
a release set *and* a tuning path, because *"a run comes back worse, the judgment looks wrong in
hindsight, and the set quietly becomes the thing that fits"*. Flipping the flag means editing
`src/mycelium/config.py`, which is a tuning path. But the evidence for the flip **is** the new
set, and no ordering of two pull requests avoids the conjunction: the sets alone leave
`measure_symbol_leg.py --check` red on `main`, and the flag alone has no evidence, because on
the old four-case slice the leg still earns it.

## Decision

**`[retrieval] symbol_lookup` ships off again, because its ablation says so.** The rule
ADR-0080 wrote — the flag follows the measurement, in both directions — is applied in the
direction it was always going to be applied in one day. Nothing about the leg, its constants or
its routing changes; it stays supported, explained and one line away
(`[retrieval] symbol_lookup = true`).

**And `check_frozen_release_sets.py` is narrowed rather than bypassed.** A *gated default* — one
whose agreement with a measurement is enforced by an ablation runner that runs on the same tree
— may move in the same change as a release set. Three defaults qualify today, and each is named
beside the runner that holds it: `symbol_lookup` (`measure_symbol_leg.py --check`),
`graph_expansion` (`measure_graph_expansion.py --check`) and `profile`
(`measure_hybrid_gate.py --check`). The exemption applies only when the gated default is the
**whole** of what the change binds in `config.py`: the script reads the diff, ignores prose —
because a default flip carries its reasoning in the docstring beside it — and refuses as before
if any other name is bound.

This is ADR-0056's argument applied a second time: *a proxy is retired where the direct check
exists and is stronger.* The conjunction rule is a proxy for "the set was fitted to the
retriever". For these three flags the direct check exists: the runner fails unless the flag
agrees with a measurement taken over those very sets, so a default cannot be chosen to flatter a
set, and a set that flattered a default would have to do it through a measurement the runner
re-takes. The proxy stays in force everywhere else, because nothing else in the tuning paths has
such a runner.

## Alternatives Considered

- **Hold the symbol cases back and land the rest.** Rejected by the maintainer, and the reason is
  the item's own: a judged set exists to be able to falsify things, and 58 cases that were
  authored blind, validated against a build and then withheld *because* of what they showed is
  the shape of evidence suppression, however procedurally tidy.
- **Land the sets and leave `--check` red until a follow-up flips the flag.** Rejected: a known
  red gate on the default branch is what the ladder exists to prevent, and "it will be green
  after the next PR" is how a gate becomes something people learn to ignore (ADR-0053's own
  argument about gates that cannot fail, read the other way round).
- **Flip the flag in a PR that touches no release set, before the sets land.** Rejected as
  impossible rather than unattractive: on the committed four-case slice the ablation still
  *earns* the default, so that PR's own `--check` would fail. The evidence does not exist until
  the sets do.
- **Move the bar instead — accept a regression on a projected corpus.** Refused outright. That is
  re-cutting a bar in the act of failing it, which this project has refused twice already
  (ADR-0131, ADR-0136), and the regression is on a held-out set of 58 cases rather than a
  rounding error.
- **Exempt all of `config.py` from the tuning paths.** Rejected: most of that file is not gated
  by anything — `pack_atomic` moves every chunk boundary and no runner re-measures it — and the
  conjunction rule is exactly what catches a change that flips such a default beside a re-judged
  set (roadmap 4.11, ADR-0042).
- **Make the script run the ablation itself rather than reading the diff.** Rejected on cost and
  on layering: the check is a fast git-only step that runs before the corpora are built, and the
  ablation it would call is already a rung of the same ladder. Two runs of the same measurement
  to satisfy one rule is the slow way to be no safer.

## Consequences

- **A leg that was on for one milestone is off again, and the record says why in one line:** the
  slice that judged it grew by fourteen times and the reading inverted. Nothing was tuned.
- **The shipped default now disagrees with `uv/release`'s own measurement**, where the leg gains
  +5.0 %. That is deliberate: the bar is a gain *with no regression anywhere*, and a leg that
  helps one corpus and hurts its projection has not earned a default that applies to both. The
  per-set numbers are in the ablation's output and in `README.md`, so a user who only indexes
  authored Markdown can turn it on knowing which half of the evidence they are acting on.
- **`check_frozen_release_sets.py` has an exemption, and exemptions rot.** The mitigation is that
  it is narrow (three named flags), mechanical (the diff must bind nothing else), and printed
  when it fires — the run says which flag was allowed and which runner authorised it, so the next
  reader sees the reasoning rather than a silent pass.
- **Every baseline is re-blessed again**, because the retriever's shipped default changed after
  the first bless of this change — six arms rather than three, and the verdict `g2-verdict.json`
  re-recorded with it.
- **The determinism golden moved, and it is supposed to.** `observe_build` records a
  `config_digest` (ADR-0012), so flipping a shipped default changes it:
  `sha256:f4f735…` → `sha256:26e3dc…`, re-blessed with
  `python tools/update_determinism_golden.py` and carried in the pull request as a one-line diff.
  Gate G6 is unweakened — a golden that did *not* move here would have meant the digest does not
  cover the defaults it claims to.
- **The two ablations that did not move are unaffected**, and the graph leg's `--check` still
  passes: the narrowing changes no measurement, only which changes may travel together.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §2 (routing), §3 (the symbol leg), §7.1
  (the freeze this narrows), §7.3 (the gates).
- Assets: `src/mycelium/config.py` (`symbol_lookup`), `tools/check_frozen_release_sets.py`
  (`GATED_DEFAULTS`, `gated_default_only`), `tools/measure_symbol_leg.py`; tests:
  `tests/test_symbol_leg.py`, `tests/test_frozen_release_sets.py`.
- Re-runnable: `python tools/measure_symbol_leg.py` (the table above),
  `python tools/measure_symbol_leg.py --check`,
  `python tools/check_frozen_release_sets.py origin/main`.
