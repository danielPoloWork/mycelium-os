# ADR-0161: Close Milestone 7 as v0.7.0, carry the platform items past the cut, and plan v1.0.0 on the board's findings

- **Status:** Accepted
- **Date:** 2026-10-07
- **Deciders:** the maintainer (danielPoloWork), on the architecture review board's recommendation
- **Related:** [ADR-0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md) (amended here), [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md), [ADR-0138](0138-recut-the-adoption-gates-onto-acts-we-can-observe.md), [ADR-0154](0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md), [ADR-0155](0155-read-7-2s-three-triggers-and-say-which-one-cannot-be-read.md), [ADR-0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md); D-030; spec 06 §1, §3; AGENTS.md §11; [analysis 0002](../analysis/0002-architecture-review-board-v1-readiness.md) (decision D-01); roadmap 7.1, 7.2, 7.12, 7.14; issues #206–#235

## Context

ADR-0113's correction of 2026-09-14 put the v1.0.0 tag at **Milestone 7**, because AGENTS.md §11
increments the pre-1.0 `MINOR` once per completed milestone and M6 shipped v0.6.0. The same
heading kept the milestone's original identity — *Team & platform (spec Phase 5; separate RFC
cycle)* — and with it the rule that each item enters only through its spec 06 §3 trigger and its
own RFC. Three weeks later the two halves of that heading cannot both hold:

- **Two of M7's items cannot close.** 7.1 (the remote build cache) and 7.2 (the server profile)
  are held at their triggers. On 2026-10-05 `tools/adoption_report.py` read the four of them as
  *holding*, *holding*, *unreadable* by decision, and *holding*: nobody outside this repository
  builds it, no consumer has filed the *I cannot use MCP or the CLI* form, and code search finds
  no out-of-tree plugin. A trigger is a condition on the world (ADR-0118), so no change made here
  can fire one, and `tools/consistency_lint.py` refuses a milestone marked complete while it holds
  an unchecked item. A milestone that carries the v1.0.0 tag and two items that may never open
  would hold the tag forever.
- **Everything else in M7 is delivered.** 7.3–7.13 closed between 2026-09-23 and 2026-10-06:
  thirteen merged pull requests since the v0.6.0 tag, among them the Document record's change of
  shape (D-032) and the store's move from `mycelium/store/v8` to `v9`. None of it is released, and
  `main` still reports `mycelium 0.6.0` while writing a store v0.6.0 refuses — the drift the
  board recorded as governance-c19.
- **The board left the decision open by name.** Analysis 0002 returned CONDITIONAL GO and filed
  thirty issues (#206–#235). Its decision D-01 asks for one record of what v1.0.0 exits on; its
  challenger confirmed the missing exit gate at P1 and refuted the other half of the original
  finding, because the v1.0.0 label on M7 is this ADR's predecessor's recorded correction, not
  drift.
- **The maintainer decided on 2026-10-07**: close 7.1 and 7.2 out of the release path, cut
  v0.7.0, and correct the board's issues before v1.0.0 rather than after it.

## Decision

**Milestone 7 ships v0.7.0 and closes; v1.0.0 moves to a new Milestone 8 that holds the board's
findings and states its exit gates; the platform items are carried by name to a Phase-5
milestone, still held at their triggers.**

1. **Milestone 7 becomes *v0.7.0 — Readiness for the 1.0 cut*** and closes with 7.3–7.14, all
   delivered. Its heading says what it turned out to be: the milestone that made the platform
   triggers readable, armed the agent-task verdict, opened the contribution door and held the
   architecture review.
2. **7.1 and 7.2 are carried by name, not delivered and not refused**, to **Milestone 10 — v2.x —
   Team & platform (spec Phase 5; separate RFC cycle)** as **10.1** and **10.2**. In M7 they are
   checked as *carried*, which is ADR-0113's rule applied to an item rather than a gate: a
   milestone closes on what it can close, and what it cannot is carried with an owner and a
   place. Their triggers, their readings (ADR-0154, ADR-0155) and the checklist their RFC owes
   (`docs/rfc/server-profile-checklist.md`) move with them unchanged. `tools/adoption_report.py`
   prints the triggers under the new numbers, so the report names the item that is open.
3. **Milestone 8 — v1.0.0 — The stable foundation** holds twenty of the board's thirty issues,
   chosen by one rule: **before the tag goes whatever is release-blocking, and whatever would be an
   incompatible change to a frozen contract or the design of record if made after it** — the four
   release-blocking issues (#206–#209), the ten confirmed P1 groups, and six P2 groups that touch a
   contract (#215, #223, #224, #225, #228) or the normative documents the tag publishes (#227). It
   also holds the three decisions the board left the maintainer: the module-facing surface, whose
   ADR-0086 trigger *is* the tag (8.21); the performance envelope the tag advertises (8.22); and
   what v1.0.0 promises beyond the code (8.23).
4. **Milestone 9 — v1.1.0 — Hardening** holds the other ten issues (#221, #222, #226, #229–#235):
   each closes after the tag as a PATCH or a MINOR without breaking the promise, so none of them
   holds the tag.
5. **v1.0.0's exit gates are written on Milestone 8's heading**, restated from spec 06 Phase 4 and
   from the board: gates G1–G6 green on the frozen release set; zero critical findings open from a
   security review; the compatibility promise published (met at 6.1); the D-030 contribution gate
   or the maintainer's recorded decision to carry it by name; every M8 item closed or carried by an
   ADR naming its owner; `tools/check_repo_settings.py` exiting 0 and the package resolving on an
   index. **Whether the contribution gate binds the tag is left open on purpose** — it stands at
   zero of three external authors, no engineering work moves it, and it is the maintainer's call
   (8.23), exactly as it was at v0.6.0.
6. **Numbers order filing; the version label orders release.** Milestone 10 is numbered before any
   v1.x milestone filed later, and its label, v2.x, says when it ships. Renumbering it to keep the
   numbers in release order would be the renumbering the roadmap forbids.

## Alternatives Considered

- **Keep M7 as the v1.0.0 milestone and fix the issues inside it.** Rejected: M7 could not close
  until 7.1 and 7.2's triggers fire, which nothing here causes, and no v0.7.0 could be cut,
  because AGENTS.md §11 ties a pre-1.0 `MINOR` to a completed milestone.
- **Check 7.1 and 7.2 as delivered, or refuse them.** Rejected: nothing was delivered, and spec 06
  §3 defers them to their triggers rather than dropping them; a refusal would contradict the
  design of record.
- **Move the lines 7.1 and 7.2 under the new milestone and keep their numbers.** Rejected: the
  numbering lint requires an item to sit under the milestone its number names (roadmap 4.27),
  and a no-renumber rule with exceptions stops being one. The repository's precedent for an item
  that outlived its milestone is a fresh number and a note naming where it came from.
- **Cut v0.7.0 as an interim release without closing a milestone.** Rejected: it amends the
  versioning rule to buy a release this re-cut buys anyway, and leaves the 1.0 milestone unable to
  close.
- **Put all thirty issues before the tag.** It was the maintainer's first instinct, and it is
  narrowed rather than refused: what holds the tag is whether a fix made after it would break the
  promise. The ten in Milestone 9 would not, and holding v1.0.0 on them buys no guarantee a user
  can observe. Any of them moves to Milestone 8 by a one-line re-cut if the maintainer prefers.

## Consequences

- **The next release is v0.7.0**, cut by `docs/workflow/release.md` from step 0 (the
  `ours/release` re-bless as its own pull request, then the settings check) — the release PR
  refreshes the README's milestone table. The board's blockers are not in it unless fixed first;
  the release notes list them under known limits, as v0.6.0 listed its own.
- **GitHub carries the new structure after merge**: milestone M7 is renamed for v0.7.0, M8–M10 are
  created, and issues #206–#235 move to M8 or M9 as the roadmap lists them. Until then
  `tools/check_repo_settings.py` reports the three new milestones absent (§5).
- **The adoption report's trigger labels move** to 10.1 and 10.2 with this record, and the three
  tests that pin them move with them. Records that cite 7.1 or 7.2 as the decision they made —
  ADR-0154, ADR-0155, ADR-0160, the adoption page's history, the server-profile checklist — keep
  the number they were written against; the carried items say where they came from.
- **Records that place 1.0 at M7** — ADR-0113's correction (amended in place), ADR-0114,
  ADR-0138, the benchmark reports of 2026-09-17 and 2026-09-19, BUG-0033 and BUG-0035 — read as
  Milestone 8 from here; dated records are not rewritten. The live ones move now: the README's
  status line, spec 05 §5's note, spec 06 §1's Phase 4 and Phase 5, and the checklist's heading
  reference.
- **`orchestrator/project.yaml` still lists M1–M7**; roadmap 8.19, the board's amendment pass over
  the normative documents (#227), brings it up.
- **Analysis 0002 §7 is accepted in part**: the v1.0.0 cut and the v1.1 hardening milestone. Its
  ecosystem (v1.2) and scale (v1.3) milestones and its security and developer-experience tracks
  stay proposals for negotiation; the items they would hold that are already filed live in
  Milestones 8 and 9.

## References

- Analysis 0002, §0 (verdict and conditions), §4 (D-01, D-03, D-05), §7 (roadmap proposal), §8
  (the thirty issues).
- `tools/adoption_report.py` run of 2026-10-05; `tools/consistency_lint.py`'s `milestones` and
  `roadmap-numbering` checks.
- AGENTS.md §11; spec 06 §1 (Phase 4 exit gates; Phase 5), §3 (deferred decisions).
