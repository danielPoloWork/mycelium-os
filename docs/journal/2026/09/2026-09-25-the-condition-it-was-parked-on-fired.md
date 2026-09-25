# 2026-09-25 — the condition it was parked on fired (roadmap 7.8)

- **Session scope:** roadmap 7.8 — audit every open issue against what the milestones have
  since delivered, and say for each: still needed, solved, or superseded.
- **PR:** #200 (`docs/audit-open-issues-against-delivered-milestones`) carries this record;
  the audit's own deliverable is the comment posted on each issue, not a code change.
  Closing an issue is the owner's click, not this session's.
- **Milestone 7:** 7.8 closed.
- **Decision it records:** none — no code, no ADR. Three comments posted to public issues,
  listed below.

## The repository has three open issues, and they are the same three

No issue has been opened since roadmap 6.6 seeded `#149`–`#151` as reserved
`good first issue`s, and none of the forty-odd merged PRs since has touched what any of the
three asks for. The audit was short because the population was small, not because it was
skipped.

| Issue | Verdict | Evidence |
|---|---|---|
| [#149](https://github.com/danielPoloWork/mycelium-os/issues/149) — three repo settings the tool does not read | **still needed** | `tools/check_repo_settings.py` has no `check_secret_scanning`, `check_secret_scanning_push_protection` or `check_delete_branch_on_merge`; live repo reads `delete_branch_on_merge: false` |
| [#150](https://github.com/danielPoloWork/mycelium-os/issues/150) — translate `SECURITY.md` to Italian | **still needed, unclaimed** | `docs/i18n/translation-status.md`'s three `SECURITY.md` rows are still `pending`; no `docs/i18n/it/SECURITY.md` exists |
| [#151](https://github.com/danielPoloWork/mycelium-os/issues/151) — walk the tutorial on a clean machine | **still needed, unclaimed** | no comment or PR against it; the package is still off every index, so the tutorial's premise (install → cited answer) is untested by anyone but this project |

## The one real finding is in #149's comment thread, not in the code

`tools/check_repo_settings.py` not having the three checks is the issue as filed and nothing
more. What is worth surfacing is the maintainer's own comment on it, from 2026-09-16: they
parked review of both the branch and the PR-access setting that blocked it *"once Milestone 6
is complete."* Milestone 6 closed with the v0.6.0 release on 2026-09-23. The stated condition
has fired, and nothing in this repository was watching for that the way ADR-0118 taught
`check_repo_settings.py` to watch a security deferral — this is the same shape, one level up,
in a place no tool reads. Said in the issue comment rather than acted on: reopening intake is
roadmap **7.9**, filed the same day as this item, and it is the actual next step, not this
one.

## What this audit did not find

No issue is solved by a merged PR under another name, and none is superseded by a decision
that removed its premise. `#150` and `#151` are reserved work with no motion at all since
they were filed — worth naming plainly rather than padding the table, since a three-row audit
that reports three "still needed" rows is not a failure of the exercise.

## What the next session should know

- **Nothing here was closed.** All three comments end by naming the owner's next click
  without taking it.
- **7.9 is where #149's real blocker gets addressed**, not a re-run of this item.
- **The next audit of this kind is only worth running after new issues exist** — re-running
  7.8 today would reproduce this table exactly.
