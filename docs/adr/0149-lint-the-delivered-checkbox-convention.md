# ADR-0149: Lint the "delivered by PR #N" checkbox convention

- **Status:** Accepted
- **Date:** 2026-09-22
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / AGENTS.md §7
- **Related:** `tools/consistency_lint.py`, `.github/PULL_REQUEST_TEMPLATE.md`; roadmap 6.18,
  6.34; [ADR-0128](0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md)
  (roadmap 6.18 itself, whose merged PR #163 is the item this check would have caught)

## Context

PR #163 merged on 2026-09-18 and wrote a full delivery record onto roadmap item 6.18 — the
ADR, the before-and-after numbers, the two follow-ups it filed — while leaving the item's
checkbox at `- [ ]`. It read as open for two days, discovered only because a later session
picked 6.18 up as though it were unstarted.

Everything that should have caught it is advisory. `.github/PULL_REQUEST_TEMPLATE.md`
carries *"ROADMAP.md checkbox flipped"* as one line among many a human ticks by hand, and
`tools/consistency_lint.py` already asserts the two mechanical ROADMAP invariants it can
(`roadmap-numbering`: numbers unique, an item sits under the milestone it names) without an
opinion about this one. It is the same class of defect as the journal index that stopped
being written and nothing noticed (roadmap 5.32) and the setup steps nobody read back
(roadmap 6.6): a convention with no reader.

It is worth closing beyond tidiness. The M5 exit review's whole argument is that a
milestone closes on its gates and its list; an item that is done but reads as open makes
the list lie in the direction nobody audits, because nobody double-checks a milestone that
already looks incomplete. Left long enough, this shape would have held M6 open on a
checkbox rather than on remaining work.

## Decision

**`tools/consistency_lint.py` gains a twelfth check: an unchecked ROADMAP item whose own
text records a delivery is a congruence failure.** `delivered by PR #<digits>` is the
phrase every closed item since M1 uses to record its outcome, so matching it is a lint on
an existing convention rather than a new invention. The check requires actual digits after
`#` — never a bare `#N` — because this very item's own ROADMAP prose quotes the convention
with `#N` as a placeholder while filing the bug, and a looser pattern would fail on the
item that describes the rule.

The check fails **naming the item**, not repairing it: a ROADMAP.md edit is never a tool's
to make (the same posture `roadmap-numbering` and every other check in this lint already
take). The fix stays a one-line human edit; what changes is that forgetting it is no longer
silent.

**The mirror rule — a checked item with no delivery record — was considered and rejected.**
A survey of the committed ROADMAP found 31 of its 160 checked items whose text never says
`delivered by PR #<digits>`: items closed by an owner action taken outside a PR (1.6, 1.7),
items closed on a sibling item's CI evidence rather than new code of their own (1.4), items
delivered alongside another item in the same PR (1.5), and items reconciled into another
item's delivery entirely (2.1). Each of those is a legitimate closure, and none of them has
an unambiguous phrase to require in its place — "closed by owner action", "delivered
alongside 1.1", "reconciled" are three different shapes among several more, and inventing a
canonical replacement phrase for all of them is scope this item did not ask for. Asserting
the mirror would either fail on 31 legitimate items or require rewriting them to fit a
phrase invented for a lint, which is the item's own warning about reasoning backward from
a check to a rewrite. The forward rule has no such exception: nothing legitimately says
"delivered by PR #163" while remaining open.

## Alternatives Considered

- **Enforce both directions.** Rejected above: the mirror direction has no unambiguous
  phrase to check, and forcing one would mean rewriting 46 already-closed items to satisfy
  a tool rather than to record anything true.
- **Make the PR template's checklist line a required GitHub PR check** (e.g., a required
  status check blocking merge until the box is ticked in the template body). Rejected: this
  project's PRs are drafted by the agent and merged by the maintainer by hand (AGENTS.md
  §6), so a GitHub-side gate blocking merge on template-checkbox state adds CI surface for
  a defect the roadmap text itself already announces plainly enough to grep for.
- **Have the tool flip the checkbox itself** (a `--fix` mode). Rejected: every other check
  in this lint reports and leaves the repair to a human, and a ROADMAP.md edit specifically
  is called out as never a tool's to make — an autonomous edit to a document that records
  project history is a different kind of change than a lint script writing to itself.
- **Widen the phrase match beyond `delivered by PR #<digits>`** (e.g., also matching
  "merged as", "landed in"). Rejected for now: a survey of the committed ROADMAP found the
  phrase covers effectively every closed item's delivery language; widening speculatively
  adds false-positive risk without an observed case to justify it.

## Consequences

- **A twelfth congruence check.** `tools/consistency_lint.py`'s docstring, `CHECKS` tuple,
  and `check_roadmap_delivery_checkbox()` all land together; the module's own check-count
  claim now matches what it runs.
- **New test coverage**, `tests/test_consistency_lint_delivery_checkbox.py`, following the
  same synthetic-ROADMAP fixture pattern `test_consistency_lint.py` already uses for
  `roadmap-numbering`: a well-formed roadmap passes, an unchecked item recording a delivery
  fails and is named, a checked item with no delivery prose is not a failure, a bare `#N`
  placeholder is not mistaken for a real delivery, several failures in one roadmap are each
  named, and the check is confirmed registered in `CHECKS`.
- **Nothing about what is published moves.** The committed `ROADMAP.md` passes the new
  check as-is — this item's own line is the only "delivered by PR #" text without real
  digits in the whole file, and that is by construction of the regex, not luck.
- **The PR template's line stands unchanged.** It remains the human box; the tool now backs
  it up rather than replacing it.

## References

- `tools/consistency_lint.py` — `check_roadmap_delivery_checkbox`, registered in `CHECKS`
- `tests/test_consistency_lint_delivery_checkbox.py`
- Roadmap 6.18 — the item whose merged-but-unchecked state this lint now catches
- Roadmap 5.32 — the journal index's own "convention with no reader" precedent
