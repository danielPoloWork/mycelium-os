# 2026-09-25 — the door had a name (roadmap 7.9)

- **Session scope:** roadmap 7.9 — open pull requests to everyone, keep review and merge
  with the owner. Write the policy down and make the settings it needs checkable.
- **PR:** #201 (`chore/open-pull-requests-to-everyone`). Follows #200, merged as `288707f`.
- **Milestone 7:** 7.9 closed.
- **Decision it records:**
  [ADR-0158](../../../adr/0158-let-anyone-open-a-pull-request-and-keep-the-merge-with-named-reviewers.md).

## Ask the object, not the documentation

`adoption.md` said the block on #149 was *"not visible in today's settings"*, and that was
true of every setting in GitHub's documentation. Printing every key of `repos/{slug}` that
mentioned pulls turned up `pull_request_creation_policy: "collaborators_only"` — a field the
API serves and the REST schema does not list. One command undoes it, and it is the owner's.

## Opening the door made the merge rule urgent

With no branch protection, any collaborator with write access can merge an unreviewed pull
request, and one collaborator besides the owner has write. A user-owned repository cannot
restrict pushes to named people — that is an organisation feature — so the rule rests on
requiring a code owner's approval, with `enforce_admins` off because the owner is also the
account the agent opens pull requests under. The tool reads the reviewers from CODEOWNERS'
`*` line, so naming a second reviewer stays a one-line edit.

## What the next session should know

- **Three settings are absent and all three are the owner's**: the creation policy, the review
  gate (§3's call, which now documents one code-owner approval instead of zero), and
  `MatteFil`'s write access (triage, or a named reviewer).
- **Asking `blamevlan` to open #149's pull request is a message on the owner's behalf.** It
  waits for the first setting and for the owner's word; the agent did not send it.
