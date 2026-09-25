# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The adoption instrument's own rules (roadmap 6.12, ADR-0138).

`tools/adoption_report.py` asks GitHub, so most of it cannot be tested without a
network and an authenticated `gh`. What *can* be tested is the part that decides
what an answer means, and on this gate that part is the whole argument: who counts
as external, what an act is worth, and which of GitHub's numbers are ours rather
than somebody else's. Since roadmap 7.4 it also decides when a deferral's trigger
has fired, from reports strangers paste into issues - so what a hostile report can
and cannot do is pinned here too.

Nothing here makes a network call.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

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


def test_also_exclude_drops_a_second_login() -> None:
    """The parameter roadmap 7.13 added: a plugin's tally must exclude its own
    owner *and* this repository's, and `is_external` is where every caller reads
    that rule from."""
    assert report.is_external("acme", "acme", also_exclude=OWNER) is False
    assert report.is_external(OWNER, "acme", also_exclude=OWNER) is False
    assert (
        report.is_external(OWNER.upper(), "acme", also_exclude=OWNER) is False
    )  # case-insensitive
    assert report.is_external("blamevlan", "acme", also_exclude=OWNER) is True
    assert report.is_external("blamevlan", "acme") is True  # unset, the old behaviour


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


def test_tally_drops_the_also_excluded_login_too() -> None:
    """The mistake roadmap 7.13 found: `tally(acts, plugin_owner)` alone let this
    repository's owner read as a stranger to somebody else's plugin. Threading
    `also_exclude` through is how a caller stops that."""
    actors = report.tally(
        [("acme", "opened issue #1"), (OWNER, "commented on an issue or pull request")],
        "acme",
        also_exclude=OWNER,
    )
    assert actors == []


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


# ---------------------------------------------------------------------------
# The deferral it watches: spec 06 §3's remote-cache trigger (roadmap 7.4)
# ---------------------------------------------------------------------------


def _report(**overrides: object) -> dict[str, object]:
    """A well-formed `measure_cache_ceiling.py` report: a team, and a real saving."""
    payload: dict[str, object] = {
        "schema": report.CACHE_REPORT_SCHEMA,
        "documents": 4_000,
        "people": 5,
        "cold_s": {"p50": 360.0, "min": 355.0, "max": 371.0},
        "seeded_s": {"p50": 190.0, "min": 186.0, "max": 197.0},
        "ceiling_s": 170.0,
        "cold_builds_per_week": 40,
    }
    payload.update(overrides)
    return payload


def _body(payload: object) -> str:
    return "Measured on our docs:\n\n```json\n" + json.dumps(payload) + "\n```\n"


def _issue(number: int, login: str, body: str, state_reason: str | None = None) -> dict[str, Any]:
    return {"number": number, "user": {"login": login}, "body": body, "state_reason": state_reason}


def _comment(number: int, login: str, body: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{OWNER}/mycelium-os/issues/{number}"
    return {"issue_url": url, "user": {"login": login}, "body": body}


def test_one_team_s_measured_pain_fires_the_trigger() -> None:
    reports = report.cache_reports([_issue(12, "a-team-lead", _body(_report()))], [], OWNER)
    trigger = report.remote_cache_trigger(reports)
    assert trigger.fired is True
    assert trigger.item == "roadmap 7.1"
    assert "a-team-lead on #12" in trigger.evidence[0]


def test_a_report_in_a_comment_counts_against_its_issue() -> None:
    reports = report.cache_reports([], [_comment(31, "a-team-lead", _body(_report()))], OWNER)
    assert [(item.login, item.issue) for item in reports] == [("a-team-lead", 31)]


@pytest.mark.parametrize("login", [OWNER, "dependabot[bot]", "app/dependabot"])
def test_our_own_reports_do_not_fire_it(login: str) -> None:
    """The trigger is a *team's* pain: ours is a performance item, and counting it
    would be closing the gate by counting this repository (roadmap 6.12's rule)."""
    reports = report.cache_reports([_issue(3, login, _body(_report()))], [], OWNER)
    assert reports == []
    assert report.remote_cache_trigger(reports).fired is False


def test_one_person_is_not_a_team() -> None:
    reports = report.cache_reports([_issue(4, "solo", _body(_report(people=1)))], [], OWNER)
    trigger = report.remote_cache_trigger(reports)
    assert trigger.fired is False
    assert "one person is not a team" in trigger.evidence[0]


def test_a_saving_inside_the_noise_is_not_pain() -> None:
    """Overlapping ranges: the instrument cannot tell the cache from the weather."""
    noisy = _report(
        cold_s={"p50": 30.0, "min": 27.0, "max": 34.0},
        seeded_s={"p50": 29.0, "min": 26.0, "max": 31.0},
        ceiling_s=1.0,
    )
    trigger = report.remote_cache_trigger(
        report.cache_reports([_issue(5, "a-team-lead", _body(noisy))], [], OWNER)
    )
    assert trigger.fired is False
    assert "the saving is noise" in trigger.evidence[0]


def test_a_report_whose_cache_saved_nothing_is_a_report_and_not_pain() -> None:
    """A negative saving is a measurement - the seeded build was slower - not a
    malformed block. Refusing it made the reader drop exactly the report that says
    *no pain*, and made a timing-dependent test of the round trip (BUG-0036)."""
    nothing = _report(
        cold_s={"p50": 0.61, "min": 0.58, "max": 0.66},
        seeded_s={"p50": 0.63, "min": 0.60, "max": 0.70},
        ceiling_s=-0.02,
    )
    reports = report.cache_reports([_issue(11, "a-team-lead", _body(nothing))], [], OWNER)
    assert len(reports) == 1
    assert reports[0].is_pain is False
    trigger = report.remote_cache_trigger(reports)
    assert trigger.fired is False
    assert "saved nothing" in trigger.evidence[0]
    assert "the saving is noise" in trigger.evidence[0]


def test_closing_the_issue_as_not_planned_withdraws_its_reports() -> None:
    """The owner's lever against a fabricated report, with no code change: GitHub's own
    record of the decision. It withdraws the comments on that issue too."""
    issues = [_issue(6, "a-stranger", _body(_report()), state_reason="not_planned")]
    comments = [_comment(6, "another-stranger", _body(_report()))]
    assert report.cache_reports(issues, comments, OWNER) == []
    completed = [_issue(6, "a-stranger", _body(_report()), state_reason="completed")]
    assert len(report.cache_reports(completed, comments, OWNER)) == 2


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            '```json\n{"schema": "mycelium/cache-ceiling/v0", "documents": \n```',
            id="malformed",
        ),
        # `bool` is an int to Python and not to JSON.
        pytest.param(_body(_report(people=True)), id="bool-as-count"),
        pytest.param(_body(_report(people=-3)), id="negative-count"),
        pytest.param(_body(_report(documents="4000")), id="string-as-count"),
        pytest.param(_body(_report(ceiling_s=float("nan"))), id="nan"),
        pytest.param(
            _body(_report(cold_s={"p50": 10**400, "min": 1.0, "max": 2.0})), id="overflow"
        ),
        pytest.param(_body(_report(seeded_s="fast")), id="string-as-arm"),
        pytest.param(_body(_report(cold_builds_per_week=2.5)), id="fractional-rate"),
        # Parses as an int, then overflows the first float it is multiplied by.
        pytest.param(_body(_report(cold_builds_per_week=10**400)), id="absurd-count"),
        pytest.param(_body(_report(people=10**9)), id="count-at-the-bound"),
        pytest.param(_body(_report(ceiling_s=1e308)), id="absurd-duration"),
        pytest.param(_body(_report(ceiling_s=-1e308)), id="absurd-negative-saving"),
        # A cache cannot save more than the build it replaces.
        pytest.param(_body(_report(ceiling_s=400.0)), id="saving-above-the-build"),
        pytest.param(_body(_report(schema="mycelium/cache-ceiling/v1")), id="other-schema"),
        pytest.param(
            '```json\n{"schema": "mycelium/cache-ceiling/v0", "x": '
            + "[" * 100_000
            + "]" * 100_000
            + "}\n```",
            id="nesting-bomb",
        ),
        pytest.param("no fence at all: " + json.dumps(_report()), id="unfenced"),
    ],
)
def test_a_block_that_is_not_a_report_is_skipped_never_fatal(body: str) -> None:
    """A report is text a stranger wrote. Malformed JSON, the wrong types, NaN (which
    `json` admits), an integer too large for a float or for any real count, and nesting
    deep enough to exhaust the parser - BUG-0030's shape - each read as *no report*."""
    assert report.reports_in(body, login="a-stranger", issue=9) == []


def test_a_report_s_strings_are_never_repeated_back() -> None:
    """Only numbers survive the read, so nothing a stranger typed reaches a terminal."""
    hostile = _report(note="\x1b]0;owned\x07", mycelium="\x1b[2J")
    reports = report.cache_reports([_issue(8, "a-team-lead", _body(hostile))], [], OWNER)
    trigger = report.remote_cache_trigger(reports)
    rendered = " ".join([trigger.observed, *trigger.evidence])
    assert "\x1b" not in rendered


def test_no_report_holds_the_trigger_and_says_how_to_post_one() -> None:
    trigger = report.remote_cache_trigger([])
    assert trigger.fired is False
    assert "adoption.md" in trigger.evidence[0]


def test_a_fired_trigger_fails_the_report_and_a_holding_one_does_not() -> None:
    """ADR-0118's polarity: a deferral is a failure once its condition has fired,
    because the decision it deferred is owed - not before."""
    met = [report.Signal(key="a", condition="a", phase="3", met=True, observed="")]
    fired = report.remote_cache_trigger(
        report.cache_reports([_issue(12, "a-team-lead", _body(_report()))], [], OWNER)
    )
    holding = report.remote_cache_trigger([])
    assert report.verdict(met, [holding]) is True
    assert report.verdict(met, [fired]) is False
    unreadable = report.Trigger(
        key="t", item="i", decision="d", condition="c", fired=None, observed=""
    )
    assert report.verdict(met, [unreadable]) is True


def test_the_trigger_is_the_one_spec_06_wrote_given_readings() -> None:
    """*≥ 1 team* stays one, as the spec wrote it; *team* reads as two or more people.
    If either moves, it moves in a decision and this test is how the code finds out."""
    assert report.TEAM_REPORTS_BAR == 1
    assert report.TEAM_PEOPLE_BAR == 2
    assert report.CACHE_REPORT_SCHEMA == "mycelium/cache-ceiling/v0"


# ---------------------------------------------------------------------------
# The three deferrals that gate the server profile (roadmap 7.5, ADR-0155)
# ---------------------------------------------------------------------------

FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "surface_request.yml"


def _form_body(**answers: str) -> str:
    """An issue body as GitHub renders a filled-in issue form: `### <label>` per field."""
    filled = {
        "Which client cannot use MCP or the CLI": "a browser extension",
        "Why MCP (stdio) does not fit it": "no process to spawn",
        "Why the CLI does not fit it": "no shell either",
        **answers,
    }
    return "\n\n".join(f"### {label}\n\n{answer}" for label, answer in filled.items()) + "\n"


def test_the_form_and_the_reader_agree_on_the_fields_and_the_label() -> None:
    """The reader recognises the form by its headings, so the two are one list held
    together here: rename a field in the YAML and this is how the code finds out."""
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    labels = [field["attributes"]["label"] for field in form["body"] if field["type"] != "markdown"]
    for expected in report.SURFACE_REQUEST_FIELDS:
        assert expected in labels
    required = [
        field["attributes"]["label"]
        for field in form["body"]
        if field["type"] != "markdown" and field.get("validations", {}).get("required")
    ]
    for expected in report.SURFACE_REQUEST_FIELDS:
        assert expected in required, f"{expected!r} must be required, or a request can omit it"
    assert report.SURFACE_REQUEST_LABEL in form["labels"]
    declared = yaml.safe_load((ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))
    assert report.SURFACE_REQUEST_LABEL in {entry["name"] for entry in declared}


def test_a_consumer_that_files_the_form_fires_the_http_api_trigger() -> None:
    requests = report.surface_requests([_issue(40, "a-consumer", _form_body())], OWNER)
    trigger = report.surface_trigger(requests)
    assert trigger.fired is True
    assert trigger.item.startswith("roadmap 7.2")
    assert trigger.evidence == ["a-consumer on #40"]


def test_what_the_consumer_typed_is_never_printed() -> None:
    hostile = _form_body(**{"Which client cannot use MCP or the CLI": "\x1b]0;owned\x07"})
    trigger = report.surface_trigger(report.surface_requests([_issue(41, "x", hostile)], OWNER))
    assert "\x1b" not in " ".join([trigger.observed, *trigger.evidence])


@pytest.mark.parametrize(
    "issue",
    [
        pytest.param(_issue(1, OWNER, _form_body()), id="our-own"),
        pytest.param(_issue(2, "dependabot[bot]", _form_body()), id="a-bot"),
        pytest.param(_issue(3, "x", _form_body(), state_reason="not_planned"), id="withdrawn"),
        pytest.param(
            _issue(4, "x", "### Problem\n\nI want REST\n\n### Proposed solution\n\nadd it\n"),
            id="a-feature-request",
        ),
        pytest.param(
            _issue(5, "x", _form_body().replace("### Why the CLI does not fit it", "### Why not")),
            id="a-field-missing",
        ),
        pytest.param({**_issue(6, "x", _form_body()), "pull_request": {}}, id="a-pull-request"),
        pytest.param(_issue(7, "x", "surface-request " + _form_body()[:20]), id="the-label-alone"),
    ],
)
def test_what_is_not_a_consumer_appearing(issue: dict[str, Any]) -> None:
    """Ours, a bot's, a withdrawn one, a feature request, a form with a field missing,
    a pull request, and the label's name typed by hand: none is a consumer appearing."""
    assert report.surface_requests([issue], OWNER) == []
    assert report.surface_trigger([]).fired is False


def test_the_server_profile_row_is_unreadable_and_never_fires() -> None:
    """A commitment is a promise and the profile does not exist: `None`, by decision
    (2026-09-24), and `None` never fails the report (ADR-0118)."""
    trigger = report.server_profile_trigger()
    assert trigger.fired is None
    assert "7.2" in trigger.item
    met = [report.Signal(key="a", condition="a", phase="3", met=True, observed="")]
    assert report.verdict(met, [trigger]) is True


def _hit(slug: str, *, fork: bool = False, path: str = "pyproject.toml") -> dict[str, Any]:
    owner = slug.partition("/")[0]
    return {
        "path": path,
        "repository": {"full_name": slug, "fork": fork, "owner": {"login": owner}},
    }


def test_only_somebody_elses_repository_is_a_third_party_plugin() -> None:
    """Ours is excluded by owner, every fork by flag - a fork of this repository
    carries `contrib/chats` and the cookiecutter back to us - and one repository
    declaring both groups is one plugin, not two."""
    hits = [
        _hit(f"{OWNER}/mycelium-os", path="contrib/chats/pyproject.toml"),
        _hit("someone/mycelium-os", fork=True),
        _hit("acme/mycelium-jira"),
        _hit("acme/mycelium-jira"),
        _hit("Zed/mycelium-notion", path="plugin/pyproject.toml"),
        "not a dict",
    ]
    found = report.plugin_candidates(hits, OWNER)
    assert [plugin.slug for plugin in found] == ["acme/mycelium-jira", "Zed/mycelium-notion"]
    assert found[0].owner == "acme"


def test_a_plugins_tally_excludes_this_repositorys_owner_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Roadmap 7.13's own scenario: this repository's owner comments on somebody
    else's plugin, and that comment must not read as an adopter. `is_external`
    and `tally` are already pinned to honour `also_exclude`; this pins that
    `third_party_plugins` actually passes it down to `engaged_actors`, which is
    where the mistake lived - only the plugin's own owner was ever excluded."""
    calls: list[tuple[str, str, str | None]] = []

    def fake_engaged_actors(
        slug: str, owner: str, *, also_exclude: str | None = None
    ) -> tuple[list[report.Actor], list[str], list[Any], list[Any]]:
        calls.append((slug, owner, also_exclude))
        return [], [], [], []

    monkeypatch.setattr(report, "search_plugin_declarations", lambda: [_hit("acme/mycelium-jira")])
    monkeypatch.setattr(report, "engaged_actors", fake_engaged_actors)

    report.third_party_plugins(OWNER)

    assert calls == [("acme/mycelium-jira", "acme", OWNER)]


def test_a_plugin_fires_the_trigger_only_when_somebody_else_engaged_with_it() -> None:
    adopter = report.Actor(login="a-user", acts=("opened issue #1",))
    adopted = report.PluginRepository("acme/mycelium-jira", "acme", "pyproject.toml", (adopter,))
    lonely = report.PluginRepository("solo/mycelium-x", "solo", "pyproject.toml", ())
    holding = report.plugin_trigger([lonely])
    assert holding.fired is False
    assert holding.evidence == [
        "not counted (nobody but its owner has engaged with it) - solo/mycelium-x"
    ]
    fired = report.plugin_trigger([adopted, lonely])
    assert fired.fired is True
    assert fired.observed == "1 adopted of 2 third-party plugin repositor(y/ies)"
    assert fired.evidence[0] == "acme/mycelium-jira: 1 engaged actor(s) - a-user"


def test_a_refused_code_search_is_unreadable_not_a_verdict() -> None:
    trigger = report.plugin_trigger(None, unreadable="GitHub code search refused: 403")
    assert trigger.fired is None
    assert "403" in trigger.observed
    assert report.plugin_trigger([]).fired is False


def test_the_readings_are_the_ones_the_owner_took_on_2026_09_24() -> None:
    assert report.SURFACE_REQUESTS_BAR == 1
    assert report.THIRD_PARTY_PLUGINS_BAR == 1
    assert report.PLUGIN_ADOPTERS_BAR == 1
    assert report.PLUGIN_ENTRY_POINT_GROUPS == ("mycelium.plugins", "mycelium.modules")
