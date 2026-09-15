#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Report which documented repository settings are installed, and which accepted
risks were deferred on a condition that has since come true.

    python tools/check_repo_settings.py [--repo owner/name] [--json] [--triggers-only]

Everything in this repository that can be checked is checked, and the settings of
the repository itself were the exception: `github-setup.md` writes down six
one-time configuration steps, nothing reads them back, and **three of them had
never been run**. Found at roadmap 6.6 by asking GitHub instead of reading the
document (ADR-0117):

- `main` had no branch protection and no ruleset at all, so *"agents never push to
  the default branch — this enforces it server-side"* was enforced by nothing. It
  was violated once already, at roadmap 3.7, and undone with a force-push.
- Private vulnerability reporting was **off**, while `SECURITY.md` and the issue
  chooser both send a reporter to the advisory form — which, with the setting off,
  an outside reporter cannot use. The documented disclosure channel did not exist.
- `.github/labels.yml` did not declare `good first issue` or `help wanted`, so the
  manifest that calls itself canonical was not.

This is the same failure the labels import had (`fix`, `refactor` and `security`
were missing until 2026-09-11, and `gh pr create --label fix` is what found it):
a setup document is a list of things somebody did once, and nothing says which.

**It reports and never changes anything.** Every remaining step is a repository
setting under the owner's account, which is theirs to make — the same boundary
`publish.yml` draws around the index side. The command to install each one is
printed beside the finding, and `github-setup.md` holds the full version.

## Expired deferrals (roadmap 6.16, ADR-0118)

The survey above answered *what is installed*. It did not answer the question that
mattered more, which 6.16 exists for: **two of those three settings were never
oversights.** They were risks formally accepted on 2026-08-29, with a severity, an
owner and an explicit condition for revisiting — and the condition came true with
nothing watching it.

- register **F2** (medium) — accepted because branch protection is unavailable on
  a private free-plan repository (API 403); revisit *"at public/Pro"*.
- register **F3** (low) — accepted because *"there are no external reporters
  (private repo), so exposure is nil"*; revisit *"the day the repo goes public,
  before any announcement"*.

The repository went public. Roadmap 1.8, which carried F3's trigger in its own
text, was ticked and closed. Nobody re-reads a risk register, so both conditions
fired unobserved — F3's stated impact ("exposure is nil") had been void for weeks
before a manual survey noticed.

So :data:`DEFERRALS` makes those conditions **executable**, and the two halves are
deliberately separated by what they cost to ask:

- **Evaluating the condition** reads only ``repos/{owner}/{repo}``, which any token
  can fetch. This is the half that had been missing, and it is the half that
  matters: a deferral whose premise is void is a finding again whether or not
  anyone can verify the remedy.
- **Verifying the remedy** reads branch protection and the vulnerability-reporting
  setting, which need administrative rights. Where the caller does not have them
  the tool says the remedy is *unverifiable* rather than absent, and never reports
  a green it did not earn.

``--triggers-only`` runs the first half alone: no admin, no secret, suitable for an
unattended caller. `docs/workflow/release.md` runs the full check, where a
maintainer's own `gh` is already authenticated (ADR-0118 records why this is not a
scheduled workflow: it would need a long-lived token, which is the one thing the
supply-chain design has been built to avoid).

Needs `gh`, authenticated. Exit 0 when every documented step is installed and no
deferral has expired unremedied, 1 when one has, 2 when GitHub could not be asked.
"""

import argparse
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SETUP_DOC = "docs/workflow/github-setup.md"


@dataclass
class Finding:
    """One documented step, whether it is installed, and how to install it.

    ``installed`` is deliberately **three-valued**. ``True`` and ``False`` are the
    obvious two; ``None`` means *this caller could not see*, which happens when the
    endpoint needs administrative rights the token does not carry. Collapsing that
    into ``False`` would invent a finding, and collapsing it into ``True`` would
    report a green nobody earned (roadmap 6.16).
    """

    key: str
    step: str
    section: str
    installed: bool | None
    detail: str
    remedy: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def unverifiable(self) -> bool:
        return self.installed is None

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "step": self.step,
            "section": self.section,
            "installed": self.installed,
            "detail": self.detail,
            "remedy": self.remedy,
            "notes": self.notes,
        }


class GitHubUnavailableError(RuntimeError):
    """`gh` is missing, unauthenticated, or the repository cannot be read."""


class PermissionDeniedError(RuntimeError):
    """The endpoint exists and this token may not read it.

    Distinct from a 404, which means the thing is genuinely not there, and from a
    transport failure, which means nothing is known. Branch protection and the
    vulnerability-reporting setting both need administrative rights, so a caller
    without them gets this and the finding is reported as unverifiable.
    """


def gh(*arguments: str) -> object:
    """One `gh api` call, returning parsed JSON, or ``None`` for a 404.

    A 404 is an answer here rather than an error: "this repository has no branch
    protection" is exactly what the endpoint says by not finding one.
    """
    result = subprocess.run(  # noqa: S603 - fixed argument vector, never a shell string
        ["gh", "api", *arguments],  # noqa: S607 - `gh` is resolved from PATH by design
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if "Not Found" in result.stderr or "404" in result.stderr:
            return None
        if "403" in result.stderr or "Must have admin rights" in result.stderr:
            raise PermissionDeniedError(result.stderr.strip())
        raise GitHubUnavailableError(result.stderr.strip() or "gh api failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:  # pragma: no cover - gh always emits JSON here
        raise GitHubUnavailableError(f"gh returned unreadable JSON: {error}") from error


# ---------------------------------------------------------------------------
# The steps github-setup.md documents
# ---------------------------------------------------------------------------


def check_merge_strategy(repo: dict[str, object]) -> Finding:
    """§1 — squash only, because the PR body becomes the commit on `main`."""
    squash = bool(repo.get("allow_squash_merge"))
    others = [name for name in ("allow_merge_commit", "allow_rebase_merge") if repo.get(name)]
    installed = squash and not others
    return Finding(
        key="merge-strategy",
        step="squash-only merges",
        section="§1",
        installed=installed,
        detail=(
            "squash is the only merge method"
            if installed
            else f"squash={squash}, also enabled: {others or 'none'}"
        ),
        remedy=(
            ""
            if installed
            else "gh api -X PATCH repos/:owner/:repo -F allow_squash_merge=true "
            "-F allow_merge_commit=false -F allow_rebase_merge=false"
        ),
    )


def check_labels(slug: str) -> Finding:
    """§2 — every label the manifest declares exists, with its declared colour."""
    declared = yaml.safe_load((ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))
    live = gh(f"repos/{slug}/labels", "--paginate")
    assert isinstance(live, list)
    by_name = {str(item["name"]): item for item in live}

    missing = [str(item["name"]) for item in declared if str(item["name"]) not in by_name]
    mismatched = [
        str(item["name"])
        for item in declared
        if str(item["name"]) in by_name
        and str(by_name[str(item["name"])].get("color", "")).lower() != str(item["color"]).lower()
    ]
    installed = not missing and not mismatched
    problems = []
    if missing:
        problems.append(f"{len(missing)} absent: {missing}")
    if mismatched:
        # A colour that drifted is the manifest failing to be canonical, which is the
        # same defect as an absent label and is invisible until somebody compares.
        problems.append(f"{len(mismatched)} exist with a different colour: {mismatched}")
    return Finding(
        key="labels",
        step="labels imported from .github/labels.yml",
        section="§2",
        installed=installed,
        detail=(
            f"all {len(declared)} declared labels exist, at their declared colours"
            if installed
            else "; ".join(problems)
        ),
        remedy="" if installed else f"the yq+gh loop in {SETUP_DOC} §2 (idempotent)",
    )


def check_branch_protection(slug: str, branch: str) -> Finding:
    """§3 — the default branch refuses a direct push, server-side.

    Either mechanism counts. A classic branch-protection rule and a repository
    ruleset express the same thing, and this asks whether the property holds
    rather than which feature provides it.
    """
    try:
        protection = gh(f"repos/{slug}/branches/{branch}/protection")
        rulesets = gh(f"repos/{slug}/rulesets")
    except PermissionDeniedError as error:
        return Finding(
            key="branch-protection",
            step=f"`{branch}` refuses a direct push",
            section="§3",
            installed=None,
            detail=f"not readable by this token (needs administrative rights): {error}",
            remedy=f"re-run as a maintainer, or see {SETUP_DOC} §3",
        )
    active = [
        item
        for item in (rulesets if isinstance(rulesets, list) else [])
        if str(item.get("enforcement")) == "active"
    ]
    installed = protection is not None or bool(active)
    return Finding(
        key="branch-protection",
        step=f"`{branch}` refuses a direct push",
        section="§3",
        installed=installed,
        detail=(
            f"protected ({'branch protection' if protection else f'{len(active)} ruleset(s)'})"
            if installed
            else "no branch protection and no active ruleset - a direct push to "
            f"`{branch}` is possible, and AGENTS.md's rule against it is procedural only"
        ),
        remedy="" if installed else f"the `gh api -X PUT ... /protection` call in {SETUP_DOC} §3",
    )


def check_discussions(repo: dict[str, object]) -> Finding:
    """§4 — Discussions, which the issue chooser sends questions to."""
    installed = bool(repo.get("has_discussions"))
    return Finding(
        key="discussions",
        step="Discussions enabled",
        section="§4",
        installed=installed,
        detail="enabled"
        if installed
        else "disabled, and .github/ISSUE_TEMPLATE/config.yml links a reader to it",
        remedy="" if installed else "gh api -X PATCH repos/:owner/:repo -F has_discussions=true",
    )


def check_vulnerability_reporting(slug: str) -> Finding:
    """§4 — the private channel `SECURITY.md` promises.

    The one finding here that is a defect rather than a gap: with this off, an
    outside reporter following `SECURITY.md` reaches a form they cannot submit,
    and their fallback is the public issue tracker — which is precisely what a
    disclosure policy exists to prevent.
    """
    try:
        state = gh(f"repos/{slug}/private-vulnerability-reporting")
    except PermissionDeniedError as error:
        return Finding(
            key="vulnerability-reporting",
            step="private vulnerability reporting",
            section="§4",
            installed=None,
            detail=f"not readable by this token (needs administrative rights): {error}",
            remedy=f"re-run as a maintainer, or see {SETUP_DOC} §4",
        )
    installed = bool(isinstance(state, dict) and state.get("enabled"))
    return Finding(
        key="vulnerability-reporting",
        step="private vulnerability reporting",
        section="§4",
        installed=installed,
        detail=(
            "enabled"
            if installed
            else "DISABLED, while SECURITY.md and the issue chooser both send reporters "
            "to the advisory form - which an outside reporter cannot submit while it is off"
        ),
        remedy="" if installed else f"gh api -X PUT repos/{slug}/private-vulnerability-reporting",
    )


def check_milestones(slug: str) -> Finding:
    """§5 — a milestone per roadmap milestone, since every PR is delivered against one."""
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    numbers = {
        int(match.group(1)) for match in re.finditer(r"^## Milestone (\d+) ", roadmap, re.MULTILINE)
    }
    # The state goes in the query string: `gh api -f` builds a request *body*, which a
    # GET turns into an HTTP 422 rather than a filter.
    live = gh(f"repos/{slug}/milestones?state=all&per_page=100", "--paginate")
    assert isinstance(live, list)
    seeded = {
        int(match.group(1))
        for item in live
        if (match := re.match(r"M(\d+)\b", str(item.get("title", ""))))
    }
    missing = sorted(numbers - seeded)
    installed = not missing
    return Finding(
        key="milestones",
        step="a GitHub milestone per roadmap milestone",
        section="§5",
        installed=installed,
        detail=(f"all {len(numbers)} seeded" if installed else f"no milestone for M{missing}"),
        remedy="" if installed else f"the `gh api -X POST .../milestones` call in {SETUP_DOC} §5",
        # The titles differ from the roadmap headings by the owner's choice, so this
        # matches on the `MN` prefix only and never on the rest (AGENTS.md §6.4).
        notes=[f"titles: {sorted(str(item['title']) for item in live)}"] if installed else [],
    )


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Risks accepted on a condition, and whether the condition still holds
# ---------------------------------------------------------------------------

REGISTER = "docs/security/audit-2026-08-29-bootstrap.md"


@dataclass(frozen=True)
class Deferral:
    """A finding accepted on a stated condition, and the setting that lifts it.

    The register records both halves in prose; this is the half a machine can
    evaluate. `condition` is what the acceptance rested on, `fired` decides whether
    it still holds, and `remedy` names the :class:`Finding` that closes it once it
    does not.
    """

    finding: str
    severity: str
    accepted_because: str
    revisit_when: str
    remedy: str

    def fired(self, repo: dict[str, object]) -> bool:
        """Whether the premise the acceptance rested on is void.

        Both current deferrals rest on the same premise — *the repository is
        private* — which is why this reads one field rather than taking a
        predicate. A deferral resting on something else gains its own test here,
        and the shape stays honest as long as the condition is *derived* rather
        than restated: a hand-maintained "has it fired" flag would be one more
        thing nobody re-reads, which is the defect this exists to end.
        """
        return not bool(repo.get("private"))


DEFERRALS: tuple[Deferral, ...] = (
    Deferral(
        finding="F2",
        severity="medium",
        accepted_because="branch protection is unavailable on a private free-plan repository",
        revisit_when="the repository is public or on a plan that offers protection",
        remedy="branch-protection",
    ),
    Deferral(
        finding="F3",
        severity="low",
        accepted_because='"there are no external reporters (private repo), so exposure is nil"',
        revisit_when="the day the repository goes public, before any announcement",
        remedy="vulnerability-reporting",
    ),
)
"""The register's **open** deferrals, with their conditions made executable.

Two, both from the 2026-08-29 bootstrap audit, and both fired when the repository
went public with nothing watching.

This list holds what the register still calls deferred, so it is self-limiting: the
owner installs the remedy, the register records the closure, and the row leaves
here in the same change. That is why `--triggers-only` may report a fired condition
as a failure without knowing whether the remedy is in place — a fired condition on
a still-open deferral is a finding regardless, and the thing it asks for is the
register entry to be closed by someone who looked.

Adding a row is what a future *"accepted for now, revisit when X"* costs: if X
cannot be written as code against what GitHub reports, the deferral has no expiry
and should not be granted (ADR-0118).
"""


@dataclass
class Expiry:
    """One deferral, whether its condition fired, and whether the remedy is in place."""

    deferral: Deferral
    fired: bool
    remedy_installed: bool | None

    @property
    def unremedied(self) -> bool:
        """Fired, and the remedy is not known to be in place.

        An unverifiable remedy counts as unremedied on purpose: this is a security
        record, and "I could not check" is not a pass.
        """
        return self.fired and self.remedy_installed is not True

    def as_dict(self) -> dict[str, object]:
        return {
            "finding": self.deferral.finding,
            "severity": self.deferral.severity,
            "accepted_because": self.deferral.accepted_because,
            "revisit_when": self.deferral.revisit_when,
            "fired": self.fired,
            "remedy": self.deferral.remedy,
            "remedy_installed": self.remedy_installed,
            "unremedied": self.unremedied,
        }


def expiries(repo: dict[str, object], findings: Sequence[Finding]) -> list[Expiry]:
    """Evaluate every deferral's condition, and pair it with its remedy's state."""
    by_key = {finding.key: finding for finding in findings}
    return [
        Expiry(
            deferral=deferral,
            fired=deferral.fired(repo),
            remedy_installed=(
                by_key[deferral.remedy].installed if deferral.remedy in by_key else None
            ),
        )
        for deferral in DEFERRALS
    ]


# ---------------------------------------------------------------------------


def repository(slug: str) -> dict[str, object]:
    """The repository object every check and every deferral condition reads.

    One call, and the only one `--triggers-only` makes: no administrative rights,
    no secret, nothing an unattended caller cannot have.
    """
    repo = gh(f"repos/{slug}")
    if not isinstance(repo, dict):
        raise GitHubUnavailableError(f"could not read repos/{slug}")
    return repo


def collect(slug: str, repo: dict[str, object]) -> list[Finding]:
    branch = str(repo.get("default_branch", "main"))
    return [
        check_merge_strategy(repo),
        check_labels(slug),
        check_branch_protection(slug, branch),
        check_discussions(repo),
        check_vulnerability_reporting(slug),
        check_milestones(slug),
    ]


def current_slug() -> str:
    """`owner/name` of the repository this checkout points at."""
    result = subprocess.run(  # noqa: S603 - fixed argument vector
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise GitHubUnavailableError(result.stderr.strip() or "could not resolve the repository")
    return result.stdout.strip()


def render(slug: str, findings: Sequence[Finding], expired: Sequence[Expiry]) -> None:
    if findings:
        print(f"{slug} against {SETUP_DOC}\n")
        for finding in findings:
            mark = {True: "ok        ", False: "ABSENT    ", None: "UNVERIFIED"}[finding.installed]
            print(f"  {mark} {finding.section} {finding.step}")
            print(f"             {finding.detail}")
            for note in finding.notes:
                print(f"             note: {note}")
            if finding.remedy:
                print(f"             install: {finding.remedy}")
        absent = [finding for finding in findings if finding.installed is False]
        blind = [finding for finding in findings if finding.unverifiable]
        print()
        if absent:
            print(
                f"{len(absent)} documented step(s) are not installed. Each is a repository "
                "setting under the owner's account, so this tool reports and never changes "
                f"one; {SETUP_DOC} holds the full command."
            )
        if blind:
            print(
                f"{len(blind)} step(s) could not be read by this token. They need "
                "administrative rights; re-run as a maintainer to see them."
            )
        if not absent and not blind:
            print("Every documented setup step is installed.")

    print(f"\n{slug} against the deferrals in {REGISTER}\n")
    for item in expired:
        state = "EXPIRED" if item.fired else "holds  "
        print(f"  {state} {item.deferral.finding} ({item.deferral.severity})")
        print(f"             accepted because: {item.deferral.accepted_because}")
        print(f"             revisit when: {item.deferral.revisit_when}")
        if item.fired:
            remedy = {True: "installed", False: "NOT installed", None: "not verified here"}[
                item.remedy_installed
            ]
            print(f"             the condition has come true; remedy is {remedy}")
    unremedied = [item for item in expired if item.unremedied]
    print()
    if unremedied:
        names = ", ".join(item.deferral.finding for item in unremedied)
        print(
            f"{len(unremedied)} accepted risk(s) rest on a premise that is void: {names}. "
            "Each was granted on a condition that has since come true, so the register entry "
            "has to be closed by someone who looked - install the remedy, then record the "
            f"closure in {REGISTER} and drop the row from DEFERRALS."
        )
    else:
        print("No accepted risk rests on a premise that has since become void.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="owner/name (default: this checkout's remote)")
    parser.add_argument("--json", action="store_true", help="emit the findings as JSON")
    parser.add_argument(
        "--triggers-only",
        action="store_true",
        help=(
            "evaluate only the register's deferral conditions. One unauthenticated-grade "
            "API call, no administrative rights, nothing a scheduled caller cannot have"
        ),
    )
    arguments = parser.parse_args(argv)

    try:
        slug = arguments.repo or current_slug()
        repo = repository(slug)
        findings = [] if arguments.triggers_only else collect(slug, repo)
    except PermissionDeniedError as error:
        print(f"[github] {error}")
        print("Reading these settings needs administrative rights on the repository.")
        return 2
    except GitHubUnavailableError as error:
        print(f"[github] {error}")
        print("This tool asks GitHub about settings; it needs `gh`, authenticated.")
        return 2

    expired = expiries(repo, findings)

    if arguments.json:
        print(
            json.dumps(
                {
                    "repository": slug,
                    "settings": [finding.as_dict() for finding in findings],
                    "deferrals": [item.as_dict() for item in expired],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        render(slug, findings, expired)

    failed = any(finding.installed is not True for finding in findings) or any(
        item.unremedied for item in expired
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
