# 2026-10-07 — the milestone that held the tag could not close (roadmap 7.14)

- **Session scope:** roadmap 7.14 — the maintainer asked, after the architecture review (7.12),
  whether 7.1 and 7.2 should close, whether to cut v0.7.0, and proposed correcting the board's
  issues before v1.0.0.
- **PR:** #236 (`docs/recut-milestone-seven`), from `23d8858` (#205).
- **Milestone 7:** 7.14 closed; 7.1 and 7.2 carried by name to Milestone 10; Milestone 7 complete
  and waiting for its release.
- **Decision it records:**
  [ADR-0161](../../../adr/0161-close-milestone-7-as-v0-7-0-and-plan-v1-0-0-on-the-boards-findings.md),
  amending ADR-0113's placement of 1.0 at M7.

## Three questions, one answer

Milestone 7 carried two things that cannot both hold: ADR-0113's v1.0.0 label, and the spec's
Phase-5 identity, under which 7.1 and 7.2 open only when a condition on the world fires. The
lint refuses a completed milestone with an unchecked item, so the milestone holding the tag could
not close, and no `MINOR` could be cut before it did. Closing 7.1 and 7.2 as delivered would have
been false; refusing them would have contradicted spec 06 §3. Carrying them by name — checked in
M7 as *carried*, re-filed as 10.1 and 10.2 — is ADR-0113's own rule applied to items instead of
gates, and it is what lets M7 ship as v0.7.0.

## The number was the expensive part

Keeping 7.1 and 7.2 under the new milestone with their old numbers fails the numbering lint, which
requires an item to sit under the milestone its number names. Re-filing them means every pointer
that names the item changes or goes stale. The ones that are records — ADR-0154, ADR-0155,
ADR-0160, the dated benchmark reports — keep the number they were written against. The ones that
are live moved: `tools/adoption_report.py` prints the triggers as roadmap 10.1 and 10.2, the three
tests that pin those labels moved with them, and the adoption page and the cache tool's docstring
say where the item came from.

## Where the line between Milestones 8 and 9 runs

The maintainer's instinct was to correct all thirty issues before the tag. The line drawn instead:
before v1.0.0 goes whatever is release-blocking, and whatever would be an incompatible change to a
frozen contract or to the design of record if made after it — twenty issues, plus the three
decisions the board left the maintainer. The other ten close after the tag as a PATCH or a MINOR
without breaking the promise. Any of them moves to Milestone 8 by a one-line re-cut.

## What the next session should know

- **GitHub follows the roadmap after merge**: rename milestone M7 for v0.7.0, create M8, M9 and M10
  (`docs/workflow/github-setup.md` §5), and move issues #206–#235 to M8 or M9 as the roadmap
  lists them. Until then `tools/check_repo_settings.py` reports the three milestones absent.
- **The release order the maintainer accepted**: this PR, then 8.2 (#207, the tree-sitter pin —
  one line, and without it v0.7.0 would also install the faulting release), then the
  `ours/release` re-bless as its own PR (`docs/workflow/release.md` step 0), then the v0.7.0 cut.
- **Whether the D-030 contribution gate binds v1.0.0 is open on purpose** (8.23). It stands at zero
  of three external authors; the first candidate is issue #149's contributor, whose rebased
  pull request was invited on 2026-10-06.
