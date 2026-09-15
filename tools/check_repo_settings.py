#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Report which of `docs/workflow/github-setup.md`'s steps are actually installed.

    python tools/check_repo_settings.py [--repo owner/name] [--json]

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

Needs `gh`, authenticated. Exit 0 when every documented step is installed, 1 when
one is not, 2 when GitHub could not be asked.
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
    """One documented step, whether it is installed, and how to install it."""

    step: str
    section: str
    installed: bool
    detail: str
    remedy: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "step": self.step,
            "section": self.section,
            "installed": self.installed,
            "detail": self.detail,
            "remedy": self.remedy,
            "notes": self.notes,
        }


class GitHubUnavailableError(RuntimeError):
    """`gh` is missing, unauthenticated, or the repository cannot be read."""


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
    protection = gh(f"repos/{slug}/branches/{branch}/protection")
    rulesets = gh(f"repos/{slug}/rulesets")
    active = [
        item
        for item in (rulesets if isinstance(rulesets, list) else [])
        if str(item.get("enforcement")) == "active"
    ]
    installed = protection is not None or bool(active)
    return Finding(
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
    state = gh(f"repos/{slug}/private-vulnerability-reporting")
    installed = bool(isinstance(state, dict) and state.get("enabled"))
    return Finding(
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


def collect(slug: str) -> list[Finding]:
    repo = gh(f"repos/{slug}")
    if not isinstance(repo, dict):
        raise GitHubUnavailableError(f"could not read repos/{slug}")
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="owner/name (default: this checkout's remote)")
    parser.add_argument("--json", action="store_true", help="emit the findings as JSON")
    arguments = parser.parse_args(argv)

    try:
        slug = arguments.repo or current_slug()
        findings = collect(slug)
    except GitHubUnavailableError as error:
        print(f"[github] {error}")
        print("This tool asks GitHub about settings; it needs `gh`, authenticated.")
        return 2

    if arguments.json:
        print(json.dumps([finding.as_dict() for finding in findings], indent=2, sort_keys=True))
    else:
        print(f"{slug} against {SETUP_DOC}\n")
        for finding in findings:
            mark = "ok     " if finding.installed else "ABSENT "
            print(f"  {mark} {finding.section} {finding.step}")
            print(f"          {finding.detail}")
            for note in finding.notes:
                print(f"          note: {note}")
            if finding.remedy:
                print(f"          install: {finding.remedy}")
        absent = [finding for finding in findings if not finding.installed]
        print()
        if absent:
            print(
                f"{len(absent)} documented step(s) are not installed. Each is a repository "
                "setting under the owner's account, so this tool reports and never changes "
                f"one; {SETUP_DOC} holds the full command."
            )
        else:
            print("Every documented setup step is installed.")
    return 1 if any(not finding.installed for finding in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
