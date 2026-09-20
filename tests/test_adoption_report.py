# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The adoption instrument's own rules (roadmap 6.12, ADR-0138).

`tools/adoption_report.py` asks GitHub, so most of it cannot be tested without a
network and an authenticated `gh`. What *can* be tested is the part that decides
what an answer means, and on this gate that part is the whole argument: who counts
as external, what an act is worth, and which of GitHub's numbers are ours rather
than somebody else's.

Nothing here makes a network call.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adoption_report as report  # noqa: E402

OWNER = "danielPoloWork"


# ---------------------------------------------------------------------------
# Who counts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("login", "external"),
    [
        ("blamevlan", True),
        (OWNER, False),
        (OWNER.lower(), False),  # GitHub logins are case-insensitive
        ("dependabot[bot]", False),
        ("app/dependabot", False),
        (None, False),  # a deleted account, which GitHub reports as a null user
    ],
)
def test_only_a_stranger_who_is_not_a_bot_counts(login: str | None, external: bool) -> None:
    """Dependabot authored three merged pull requests here. It is a real
    contributor to the dependency tree and it is not adoption, and the owner is
    never adoption - counting either is the *"do not close it by counting this
    repository"* failure the roadmap item forbids in those words."""
    assert report.is_external(login, OWNER) is external


def test_an_actor_is_counted_once_however_many_acts_it_performed() -> None:
    """The bar is three *people*, not three events: one enthusiast leaving five
    comments must not read as five adopters."""
    actors = report.tally(
        [
            ("blamevlan", "opened issue #149"),
            ("blamevlan", "commented on an issue or pull request"),
            ("blamevlan", "commented on an issue or pull request"),
            (OWNER, "opened issue #150"),
        ],
        OWNER,
    )
    assert [actor.login for actor in actors] == ["blamevlan"]
    assert actors[0].acts == (
        "commented on an issue or pull request",
        "opened issue #149",
    )


def test_the_acts_are_kept_so_the_verdict_can_be_audited() -> None:
    """A gate that says *three actors* and cannot name them is the assertion it
    replaced (5.43's stopping rule, applied to its own evidence)."""
    actors = report.tally([("a", "opened issue #1"), ("b", "opened issue #2")], OWNER)
    assert [actor.as_dict() for actor in actors] == [
        {"login": "a", "acts": ["opened issue #1"]},
        {"login": "b", "acts": ["opened issue #2"]},
    ]


# ---------------------------------------------------------------------------
# A fork's commits, and whose they are
# ---------------------------------------------------------------------------


def test_only_commits_an_outsider_wrote_make_a_fork_count() -> None:
    """The mistake the second draft of the tool made, pinned. `Voyagerroc-Lab`'s
    fork read as *three commits ahead* on `ci/declared-mode` - an upstream branch
    that outlived its squash merge and was copied when the fork was taken. The
    three commits were ours. A fork reflecting this repository's own undeleted
    branches back at it is the purest form of *closing the gate by counting
    ourselves*."""
    ours = [{"author": {"login": OWNER}}, {"author": None}, {"author": {"login": OWNER}}]
    assert report.external_commits(ours, OWNER) == 0

    theirs = [{"author": {"login": "blamevlan"}}]
    assert report.external_commits(theirs, OWNER) == 1

    assert report.external_commits([*ours, *theirs], OWNER) == 1


# ---------------------------------------------------------------------------
# The number that is ours
# ---------------------------------------------------------------------------


def test_clone_traffic_is_attributed_only_on_the_days_ci_did_not_run() -> None:
    """The finding 6.12 exists for, in arithmetic. GitHub reported 3 988 clones
    from 340 unique cloners in the fortnight to 2026-09-19; every CI run checks
    the repository out fourteen times, and on the two days no workflow ran the
    clones were 8 and 14."""
    clones = [
        {"timestamp": "2026-09-14T00:00:00Z", "count": 460, "uniques": 61},
        {"timestamp": "2026-09-15T00:00:00Z", "count": 357, "uniques": 34},
        {"timestamp": "2026-09-16T00:00:00Z", "count": 14, "uniques": 8},
    ]
    dates, total, uniques = report.clone_baseline(
        clones, {"2026-09-14": 28, "2026-09-15": 4, "2026-09-16": 0}
    )
    assert dates == ["2026-09-16"]
    assert (total, uniques) == (14, 8)


def test_a_window_in_which_ci_ran_every_day_attributes_nothing() -> None:
    """Silence is the honest answer: with no quiet day there is no subtraction to
    make, and the series says nothing about anybody outside this repository."""
    clones = [{"timestamp": "2026-09-14T00:00:00Z", "count": 460, "uniques": 61}]
    assert report.clone_baseline(clones, {"2026-09-14": 28}) == ([], 0, 0)


def test_clone_traffic_never_carries_a_verdict() -> None:
    """It is reported as context and excluded from every bar (D-030). A signal
    that cannot be attributed must not be able to pass a gate."""
    signal = report.Signal(
        key="clone-traffic", condition="c", phase="context", met=None, observed="o"
    )
    assert report.verdict([signal]) is True  # it cannot fail one either
    assert signal.met is None


# ---------------------------------------------------------------------------
# What the verdict is allowed to say
# ---------------------------------------------------------------------------


def test_one_unmet_condition_fails_the_report() -> None:
    signals = [
        report.Signal(key="a", condition="a", phase="3", met=True, observed=""),
        report.Signal(key="b", condition="b", phase="3", met=False, observed=""),
    ]
    assert report.verdict(signals) is False


def test_an_unreadable_condition_is_reported_not_guessed() -> None:
    """Three-valued for ADR-0118's reason: collapsing *could not see* into either
    answer reports something nobody measured. It does not fail the run - the run
    says what was readable - and it is never rendered as met."""
    signals = [report.Signal(key="a", condition="a", phase="4", met=None, observed="")]
    assert report.verdict(signals) is True
    assert signals[0].met is not True


def test_offline_reports_the_index_unreadable_rather_than_absent() -> None:
    """`--no-network` has not learned that the package is missing from PyPI; it
    has learned nothing about PyPI. The distinction is the whole three-valued
    design, and it is the difference between a finding and an artefact."""
    signal = report.index_presence(report.DISTRIBUTION, offline=True)
    assert signal.met is None
    assert "not asked" in signal.observed


# ---------------------------------------------------------------------------
# The bars themselves
# ---------------------------------------------------------------------------


def test_the_bars_are_the_ones_d030_recut() -> None:
    """The numbers are a decision, not an implementation detail: if one moves, it
    moves in an ADR and this test is how the code finds out."""
    assert report.ENGAGED_ACTORS_BAR == 3
    assert report.RECURRING_CONTRIBUTORS_BAR == 3
    assert report.RECURRING_MERGES_BAR == 2
    assert report.COMMUNITY_PLUGINS_BAR == 1
    assert report.DISTRIBUTION == "mycelium-os"
