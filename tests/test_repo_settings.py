# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The deferral watcher's own rules (roadmap 6.16, ADR-0118).

`tools/check_repo_settings.py` asks GitHub, so most of it cannot be tested without
a network and an authenticated `gh`. What *can* be tested is the part that decides
what an answer means, and that is the part 6.16 exists for: whether a condition has
fired, and what an unverifiable remedy counts as.

Nothing here makes a network call. The repository object is a fixture, because the
question under test is the arithmetic on top of it.
"""

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_repo_settings as checker  # noqa: E402

pytestmark = pytest.mark.boundary("B1")
"""The threat-model boundary these tests hold (docs/security/threat-model.md §4)."""

REGISTER = ROOT / "docs" / "security" / "audit-2026-08-29-bootstrap.md"


def repo(*, private: bool) -> dict[str, Any]:
    return {"private": private, "default_branch": "main"}


def finding(key: str, installed: bool | None) -> checker.Finding:
    return checker.Finding(key=key, step=key, section="§x", installed=installed, detail="fixture")


# ---------------------------------------------------------------------------
# The condition
# ---------------------------------------------------------------------------


def test_a_private_repository_still_holds_every_deferral() -> None:
    """Both current deferrals were accepted *because* the repository was private.
    While that is true they are not findings, and the tool must not manufacture one."""
    expired = checker.expiries(repo(private=True), [])
    assert expired
    assert not any(item.fired for item in expired)
    assert not any(item.unremedied for item in expired)


def test_going_public_voids_both_deferrals() -> None:
    """The event that actually happened, and that nothing observed for seventeen days."""
    expired = checker.expiries(repo(private=False), [])
    assert {item.deferral.finding for item in expired} == {"F2", "F3"}
    assert all(item.fired for item in expired)


# ---------------------------------------------------------------------------
# What an answer counts as
# ---------------------------------------------------------------------------


def test_a_fired_deferral_with_its_remedy_installed_is_not_a_finding() -> None:
    """The state the owner's two commands produce. The row then leaves `DEFERRALS`
    when the register records the closure, which is what keeps the list finite."""
    findings = [finding("branch-protection", True), finding("vulnerability-reporting", True)]
    assert not any(item.unremedied for item in checker.expiries(repo(private=False), findings))


def test_an_unverifiable_remedy_counts_as_unremedied() -> None:
    """The rule that decides the tri-state's whole point: in a security record
    "I could not check" is not a pass. A caller without administrative rights sees
    `installed is None`, and that must not read as green."""
    findings = [finding("branch-protection", None), finding("vulnerability-reporting", None)]
    expired = checker.expiries(repo(private=False), findings)
    assert all(item.remedy_installed is None for item in expired)
    assert all(item.unremedied for item in expired)


def test_triggers_only_has_no_remedy_to_read_and_still_reports() -> None:
    """`--triggers-only` passes no findings at all: it makes one call that needs no
    administrative rights. A fired condition is a finding there regardless, because
    what it asks for is the register entry closed by someone who looked."""
    expired = checker.expiries(repo(private=False), [])
    assert all(item.remedy_installed is None and item.unremedied for item in expired)


def test_a_finding_reports_whether_it_could_be_read() -> None:
    assert finding("x", None).unverifiable
    assert not finding("x", False).unverifiable
    assert not finding("x", True).unverifiable


# ---------------------------------------------------------------------------
# The list and the register do not drift apart
# ---------------------------------------------------------------------------


def test_every_deferral_names_a_remedy_the_tool_actually_checks() -> None:
    """A row whose remedy no check produces would evaluate to `None` forever and
    read as permanently unremedied — a gate that can never go green."""
    keys = {
        "merge-strategy",
        "labels",
        "branch-protection",
        "discussions",
        "milestones",
        "vulnerability-reporting",
    }
    assert {deferral.remedy for deferral in checker.DEFERRALS} <= keys


def test_every_deferral_is_still_open_in_the_register() -> None:
    """`DEFERRALS` holds what the register still defers, and that is what makes it
    self-limiting. A row for a finding the register has closed would be a gate
    nobody can satisfy; a closed finding still listed here is the drift this checks."""
    register = REGISTER.read_text(encoding="utf-8")
    for deferral in checker.DEFERRALS:
        row = next(
            line for line in register.splitlines() if line.startswith(f"| {deferral.finding} |")
        )
        assert "open" in row, (
            f"{deferral.finding} is listed in DEFERRALS but its register row no longer says "
            "open; drop the row in the change that closes the finding"
        )


def test_the_register_and_the_threat_model_record_the_expiry() -> None:
    """The re-assessment landed with the mechanism rather than after it — a
    correction that arrives later is the same failure repeating (ADR-0118)."""
    register = REGISTER.read_text(encoding="utf-8")
    assert "Re-rated 2026-09-15" in register
    assert "condition fired, owner action pending" in register
    model = (ROOT / "docs" / "security" / "threat-model.md").read_text(encoding="utf-8")
    assert (
        "repo currently private"
        not in model.split("Corrected 2026-09-15")[0].split("| **B1")[-1].split("|")[-1]
    ), "B1's stale assumption must not stand as an assumption"
    assert "Voyagerroc-Lab" in model


def test_the_release_procedure_runs_the_check() -> None:
    """It is not in CI, by a decision about credentials, so the release is where it
    runs — and a step nobody wrote down is a step nobody takes."""
    release = (ROOT / "docs" / "workflow" / "release.md").read_text(encoding="utf-8")
    assert "tools/check_repo_settings.py" in release


def test_no_workflow_runs_the_check_unattended() -> None:
    """Reading these settings unattended needs a long-lived token, which is the one
    thing ADR-0116 and ADR-0117 removed from this supply chain. If a workflow ever
    wants this, it takes a decision and this test is where the decision surfaces."""
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in workflow.get("jobs", {}).values():
            for step in job.get("steps", []):
                assert "check_repo_settings" not in str(step.get("run", "")), path.name


@pytest.mark.parametrize("private", [True, False])
def test_the_condition_is_derived_from_github_not_from_a_stored_flag(private: bool) -> None:
    """The property that makes this different from the register it watches: nothing
    here records *whether* a condition fired, so nothing here can go stale."""
    expired = checker.expiries(repo(private=private), [])
    assert all(item.fired is not private for item in expired)
