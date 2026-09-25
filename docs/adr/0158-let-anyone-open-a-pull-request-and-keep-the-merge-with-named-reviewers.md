# ADR-0158: Let anyone open a pull request, and keep the merge with named reviewers

- **Status:** Accepted
- **Date:** 2026-09-25
- **Deciders:** the maintainer (who filed the policy as roadmap 7.9) with the tech-lead
  (EADOS delivery agent), per RFC-0001 / spec 06 §4
- **Related:**
  [ADR-0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md)
  (the contribution ladder and CODEOWNERS),
  [ADR-0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) (settings reported,
  never changed, by `tools/check_repo_settings.py`),
  [ADR-0138](0138-recut-the-adoption-gates-onto-acts-we-can-observe.md) (the adoption gate
  this unblocks); D-030; issue #149; threat model B1; roadmap 6.6, 6.12, 7.9

## Context

The first external contribution this repository received — issue #149, a reserved
`good first issue`, finished by `blamevlan` in their fork on 2026-09-15 — could not become a
pull request: GitHub answered *"pull request creation is limited to collaborators"*. The
maintainer asked the contributor to wait until Milestone 6 closed. M6 has closed, and the
adoption gate (D-030, ADR-0138) cannot move while the door is shut: its Phase 4 condition is
*merged* external pull requests.

`docs/workflow/adoption.md` recorded that whatever blocked the pull request *"is not visible
in today's settings"*. It is visible. The repository object carries
`pull_request_creation_policy`, a field GitHub serves (values `all` and `collaborators_only`)
but has not yet added to its documented REST schema, and on 2026-09-25 it read
`collaborators_only`. Nobody had looked at a field that is not in the documentation.

Opening the door has a second half. With no branch protection on `main` (absent since 6.6)
any collaborator with write access can merge an unreviewed pull request, and one collaborator
besides the owner holds write access. "Anyone may open" is only safe beside "only named people
merge".

## Decision

**Anyone may open a pull request; only named reviewers may review and merge.** The named
reviewers are the owners `.github/CODEOWNERS` lists on its catch-all `*` line — today the
owner alone — so naming a second reviewer is one edit to a file GitHub already reads.

Five settings make that true, and each is a finding in `tools/check_repo_settings.py`
(`github-setup.md` §6):

1. `pull_request_creation_policy` is `all`;
2. `main` requires one approving review **from a code owner**. A user-owned repository has no
   push restriction (that is an organisation feature), so this is the mechanism that keeps a
   merge with the named reviewers: a collaborator with write access cannot merge what no code
   owner approved. `enforce_admins` stays `false`, because the owner is also the account the
   agent opens pull requests under and cannot approve their own;
3. no collaborator outside the named reviewers holds write, maintain or admin — the review
   gate narrows such a right, it does not remove it (a write collaborator can still merge a
   pull request a code owner approved);
4. a first-time contributor's workflows wait for approval (`first_time_contributors` or
   stricter) — the control boundary B1 now depends on;
5. no interaction limit is active.

**The agent's part is the record and the check, never the setting.** The tool reports and
prints the command; the owner installs. An agent is never a named reviewer, whatever account
it runs under: it may triage an outside pull request and may not approve or merge one
(`AGENTS.md` §6.1).

## Alternatives Considered

- **Leave intake closed until the hardening baseline is complete.** The maintainer's position
  of 2026-09-16, and superseded by the maintainer filing 7.9: the baseline that matters for an
  outside diff is the review gate and the workflow approval, and both are here.
- **Branch protection with push restrictions naming the owner.** The strongest form, and not
  available: restrictions apply only to organisation-owned repositories. Moving the repository
  into an organisation is a larger owner decision than this item.
- **A ruleset instead of classic protection.** Equivalent for this purpose, and
  `check_branch_protection` already accepts either for the direct-push rule; the review gate
  reads classic protection because that is what `github-setup.md` §3 installs. A ruleset-only
  setup would read as absent here and is left for the item that adopts rulesets.
- **List the reviewers in the tool.** Rejected: a second list beside CODEOWNERS is a second
  place to forget, which is the drift ADR-0118 was written against.

## Consequences

- `tools/check_repo_settings.py` reports five more findings. On 2026-09-25 three are absent
  (the creation policy, the review gate, and `MatteFil`'s write access) and two hold (fork
  workflow approval, no interaction limit). Whether `MatteFil` becomes a named reviewer or
  moves to triage is the owner's decision; the tool states the choice.
- `github-setup.md` §3's documented protection now requires one code-owner approval; it used to
  document zero.
- Threat model B1 is widened on purpose and says which two controls carry it.
- Once the owner installs setting 1, the adoption gate's own blocker is one message away:
  asking the contributor of #149 to open the pull request. That message is the owner's to
  authorise.
