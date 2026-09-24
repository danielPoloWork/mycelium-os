#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Report where the adoption gates stand, against signals this project can observe.

    python tools/adoption_report.py [--repo owner/name] [--json] [--no-network]

Spec 06 gives Phase 3 the exit gate *"≥ 10 external repos dogfooding"* and Phase 4
*"≥ 3 recurring external contributors and ≥ 5 community plugins"*. Roadmap 5.43
carried the first into M6 at **zero** rather than waiving it, and roadmap 6.12 is
where it was read properly. Two things were wrong with it, and only the second is
about the number:

1. **It is not observable.** A repository that vendors this tool, builds its docs
   with it and never says so is invisible from here — there is no telemetry, by
   design (D-016), and there will not be. A gate nobody can evaluate cannot be
   passed *or* failed; it can only be asserted, which is the failure mode 5.43
   was written to prevent.
2. **The one number that looks like adoption is manufactured by this repository.**
   GitHub reported **3 988 clones from 340 unique cloners** in the fortnight to
   2026-09-19 — against **225 views from 1 unique visitor**, the owner. The
   explanation is in the two days in that window when CI did not run
   (2026-09-06 and 2026-09-16): clones were **8** and **14**. Every other day
   carries 12–28 workflow runs at 14 jobs each, and every job's `actions/checkout`
   is a clone. Counting it would have been closing the gate by counting ourselves,
   which the roadmap item forbids in those words.

So D-030 re-cuts both gates onto acts that **cost the actor something** and that
GitHub reports to us, and this tool is the instrument (ADR-0138). It counts, it
subtracts this repository's own activity, and it never reports a signal it could
not read.

## What counts, and what does not

An **engaged actor** is a GitHub login that is neither the owner nor a bot, and
that did at least one of:

- opened an issue,
- opened a pull request,
- commented on an issue, a pull request or a discussion, or opened a discussion,
- holds a fork carrying **≥ 1 commit this repository does not have**.

What is deliberately *not* counted, with the reason, because a gate is as much
about the exclusions:

- **stars and watches** — one click, no evidence anybody ran anything;
- **forks with no commits ahead** — a bookmark. Both of this repository's forks
  (2026-09-14, 2026-09-15) are exactly this: `ahead_by == 0`;
- **clone traffic** — see above. Reported with its CI arithmetic beside it so the
  number is never quoted bare, never summed into the verdict;
- **unique visitors** — the owner.

## The deferral it also watches

Spec 06 §3 defers the remote build cache (roadmap 7.1) until **"≥ 1 team dogfooding
with measured duplicate-build pain"**, and until roadmap 7.4 nothing could evaluate
that either: the pain had no unit and no instrument. Now *measured* means a report
from `tools/measure_cache_ceiling.py`, run on the team's own corpus and pasted into
an issue or an issue comment, and a *team* is more than one person building that
corpus (ADR-0154). This tool reads those reports and says whether the trigger has
fired. A fired trigger is a **finding**, in the sense ADR-0118 gave a void premise:
the deferral no longer holds and the decision it deferred is owed.

A report is text a stranger wrote, so it is read as data and nothing else: only its
numbers are taken, none of its strings is ever printed, and a block that does not
parse, carries the wrong types or nests deeper than the parser allows is skipped
rather than fatal. What a fabricated report can do is fire a trigger, and a fired
trigger decides nothing — it puts a decision in front of the owner, who can withdraw
the report by closing its issue as *not planned*.

## Exit codes

0 when every gate in scope is met and no deferral's trigger has fired, 1 when a
condition is not met or a trigger has fired, 2 when GitHub could not be asked.
`--no-network` skips the index lookups and reports them unverifiable rather than
absent, which is what an offline caller has actually learned.

Needs `gh`, authenticated. Reading clone traffic needs push rights; without them
the CI arithmetic is reported as unverifiable and nothing else changes.
"""

import argparse
import json
import math
import re
import subprocess
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

#: The re-cut Phase-3 bar (D-030, ADR-0138). Three, not ten, and against acts we
#: can see: the number is the smallest that cannot be one person having a bad week.
ENGAGED_ACTORS_BAR: Final[int] = 3

#: The re-cut Phase-4 bar. A *recurring* contributor is one with two or more merged
#: pull requests — "recurring" means they came back, and one merge cannot show that.
RECURRING_MERGES_BAR: Final[int] = 2
RECURRING_CONTRIBUTORS_BAR: Final[int] = 3

#: Phase 4's "≥ 5 community plugins" re-cut to one, in the tier D-029 permits before
#: the freeze. Pre-1.0 the plugin API may break at any minor and plugins live in
#: `contrib/`; five external plugin *repositories* before 1.0 is a gate our own
#: topology decision forbids anyone from satisfying.
COMMUNITY_PLUGINS_BAR: Final[int] = 1

#: The distribution name D-024 decided.
DISTRIBUTION: Final[str] = "mycelium-os"

#: The tag a report from `tools/measure_cache_ceiling.py` carries, and the one thing
#: that makes a block of JSON in an issue *evidence* for spec 06 §3's remote-cache
#: trigger (roadmap 7.4, ADR-0154). The instrument imports it from here: the gate
#: owns the shape of what it reads.
CACHE_REPORT_SCHEMA: Final[str] = "mycelium/cache-ceiling/v0"

#: *A team* is more than one person building one corpus. The spec's own word, read
#: literally: one person with a slow build is a performance item, not a team's pain.
TEAM_PEOPLE_BAR: Final[int] = 2

#: *≥ 1 team*, as spec 06 §3 writes it. Not re-cut: 7.4 made the trigger evaluable
#: and left its number where the spec put it.
TEAM_REPORTS_BAR: Final[int] = 1

INDEXES: Final[dict[str, str]] = {
    "PyPI": "https://pypi.org/pypi/{name}/json",
    "TestPyPI": "https://test.pypi.org/pypi/{name}/json",
}

#: GitHub's traffic endpoints keep a fortnight, so every count here is over that
#: window and says so rather than implying a total.
TRAFFIC_WINDOW_DAYS: Final[int] = 14


#: One countable act, by a login GitHub may report as ``None`` for a deleted account.
Act = tuple[str | None, str]


class GitHubUnavailableError(RuntimeError):
    """`gh` is missing, unauthenticated, or the repository cannot be read."""


class PermissionDeniedError(RuntimeError):
    """The endpoint exists and this token may not read it.

    Clone traffic needs push rights. A caller without them has learned nothing
    about it, which is not the same as having learned that traffic is zero.
    """


@dataclass(frozen=True)
class Actor:
    """One external login and every countable act it performed.

    ``acts`` is kept rather than a bare count because the verdict has to be
    auditable: a gate that says *three actors* and cannot name them is the
    assertion it replaced.
    """

    login: str
    acts: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"login": self.login, "acts": list(self.acts)}


@dataclass
class Signal:
    """One gate condition, its bar, and whether this caller could see it.

    ``met`` is three-valued for the reason ADR-0118 gave the settings survey:
    ``None`` means *not readable from here*, and collapsing it either way reports
    something nobody measured.
    """

    key: str
    condition: str
    phase: str
    met: bool | None
    observed: str
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "condition": self.condition,
            "phase": self.phase,
            "met": self.met,
            "observed": self.observed,
            "evidence": self.evidence,
        }


@dataclass
class Trigger:
    """One deferred decision's ending condition (spec 06 §3), evaluated rather than recalled.

    ``fired`` is three-valued like :attr:`Signal.met`, and the polarity is the point:
    a gate is a failure until it is *met*, a deferral is healthy until its trigger
    *fires*. A fired trigger fails the report the way ADR-0118's void premise fails
    `check_repo_settings.py` — what it asks for is not a setting but a decision, and
    the trigger leaves this tool in the change that records it.
    """

    key: str
    item: str
    decision: str
    condition: str
    fired: bool | None
    observed: str
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "item": self.item,
            "decision": self.decision,
            "condition": self.condition,
            "fired": self.fired,
            "observed": self.observed,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class CacheReport:
    """The numbers one `measure_cache_ceiling.py` report carries, and who posted it.

    Numbers only. The report is text a stranger wrote into an issue, so nothing it
    says is kept as a string — the evidence line this becomes is composed here, from
    fields that were validated as numbers.
    """

    login: str
    issue: int
    documents: int
    people: int
    cold_p50_s: float
    cold_min_s: float
    seeded_p50_s: float
    seeded_max_s: float
    ceiling_s: float
    cold_builds_per_week: int | None

    @property
    def is_team(self) -> bool:
        return self.people >= TEAM_PEOPLE_BAR

    @property
    def is_pain(self) -> bool:
        """A saving the instrument can tell from its own noise: every seeded sample
        below every cold one, the criterion roadmap 6.30 measured its change by."""
        return self.seeded_max_s < self.cold_min_s

    def describe(self) -> str:
        share = self.ceiling_s / self.cold_p50_s if self.cold_p50_s else 0.0
        weekly = (
            "no cold-build rate given"
            if self.cold_builds_per_week is None
            else f"{self.cold_builds_per_week} cold builds a week, "
            f"{self.ceiling_s * self.cold_builds_per_week / 60:.1f} min a week at the ceiling"
        )
        return (
            f"{self.login} on #{self.issue}: {self.documents} documents, {self.people} "
            f"people; a cold build {self.cold_p50_s:.1f} s, of which a stage cache could "
            f"save at most {self.ceiling_s:.1f} s ({share:.0%}); {weekly}"
        )


# ---------------------------------------------------------------------------
# Asking GitHub
# ---------------------------------------------------------------------------


def gh(*arguments: str) -> object:
    """One `gh api` call, returning parsed JSON, or ``None`` for a 404."""
    result = subprocess.run(  # noqa: S603 - fixed argument vector, never a shell string
        ["gh", "api", *arguments],  # noqa: S607 - `gh` is resolved from PATH by design
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Not Found" in stderr or "404" in stderr:
            return None
        if "403" in stderr or "Resource not accessible" in stderr:
            raise PermissionDeniedError(stderr)
        raise GitHubUnavailableError(stderr or "gh api failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:  # pragma: no cover - gh always emits JSON here
        raise GitHubUnavailableError(f"gh returned unreadable JSON: {error}") from error


def paged(*arguments: str) -> list[Any]:
    """Every page of a list endpoint, flattened.

    `--paginate` alone concatenates one JSON array per page, which is not JSON;
    `--slurp` wraps the pages in an outer array, which is. Getting this wrong is
    silent until the second page exists, so it is written once here.
    """
    pages = gh(*arguments, "-X", "GET", "-f", "per_page=100", "--paginate", "--slurp")
    if not isinstance(pages, list):
        return []
    flattened: list[Any] = []
    for page in pages:
        if isinstance(page, list):
            flattened.extend(page)
    return flattened


def current_slug() -> str:
    """`owner/name` of the repository this checkout points at."""
    result = subprocess.run(  # noqa: S603 - fixed argument vector
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise GitHubUnavailableError(result.stderr.strip() or "could not resolve the repository")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Who counts
# ---------------------------------------------------------------------------


def is_external(login: str | None, owner: str) -> bool:
    """True when this login is somebody other than us and other than a bot.

    Dependabot authored three of this repository's merged pull requests. It is a
    real contributor to the dependency tree and it is not adoption, so the rule is
    written here once rather than remembered at four call sites.
    """
    if not login:
        return False
    if login.casefold() == owner.casefold():
        return False
    return not (login.endswith("[bot]") or login.startswith("app/"))


def tally(acts: Iterable[Act], owner: str) -> list[Actor]:
    """Fold ``(login, act)`` pairs into one deduplicated, sorted actor per login."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for login, act in acts:
        if login is not None and is_external(login, owner):
            grouped[login].append(act)
    return [
        Actor(login=login, acts=tuple(sorted(set(grouped[login]))))
        for login in sorted(grouped, key=str.casefold)
    ]


def issue_and_pr_acts(items: Sequence[dict[str, Any]]) -> list[Act]:
    """Every issue and pull request, by author. `/issues` returns both."""
    acts: list[Act] = []
    for item in items:
        author = (item.get("user") or {}).get("login")
        kind = "pull request" if "pull_request" in item else "issue"
        acts.append((author, f"opened {kind} #{item.get('number')}"))
    return acts


def comment_acts(slug: str, issue_comments: Sequence[dict[str, Any]]) -> list[Act]:
    """Every issue and pull-request review comment, by author.

    The issue comments arrive already fetched, because the remote-cache trigger reads
    the same payloads for reports (:func:`cache_reports`) and asking GitHub twice for
    one list is two chances for the two readings to disagree.
    """
    label = "commented on an issue or pull request"
    acts: list[Act] = [((item.get("user") or {}).get("login"), label) for item in issue_comments]
    for item in paged(f"repos/{slug}/pulls/comments"):
        assert isinstance(item, dict)
        acts.append(((item.get("user") or {}).get("login"), "reviewed a pull request"))
    return acts


def listed(*arguments: str) -> list[dict[str, Any]]:
    """A list endpoint's items, keeping only the objects - GitHub sends nothing else."""
    return [item for item in paged(*arguments) if isinstance(item, dict)]


DISCUSSION_QUERY: Final[str] = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    discussions(first: 100) {
      nodes {
        number
        author { login }
        comments(first: 100) { nodes { author { login } } }
      }
    }
  }
}
"""


def discussion_acts(slug: str) -> list[Act]:
    """Discussions and their comments, by author.

    Discussions are the channel `github-setup.md` opened for questions, so an
    outsider asking one is exactly the low-cost first contact this gate wants to
    be able to see. They exist only in GraphQL.
    """
    owner, _, name = slug.partition("/")
    payload = gh(
        "graphql", "-f", f"query={DISCUSSION_QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"
    )
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("repository"), dict):
        return []
    nodes = data["repository"].get("discussions", {}).get("nodes") or []
    acts: list[Act] = []
    for node in nodes:
        number = node.get("number")
        acts.append(((node.get("author") or {}).get("login"), f"opened discussion #{number}"))
        for comment in (node.get("comments") or {}).get("nodes") or []:
            acts.append(
                ((comment.get("author") or {}).get("login"), f"commented on discussion #{number}")
            )
    return acts


def branch_heads(slug: str) -> dict[str, str]:
    """`branch -> head sha` for one repository."""
    heads: dict[str, str] = {}
    for branch in paged(f"repos/{slug}/branches"):
        if isinstance(branch, dict):
            heads[str(branch.get("name", ""))] = str((branch.get("commit") or {}).get("sha", ""))
    return heads


def external_commits(commits: Iterable[Any], owner: str) -> int:
    """How many of a comparison's commits somebody outside this repository wrote.

    Split out from :func:`fork_acts` because it is the rule that decides the
    gate, and a rule that decides a gate is tested.
    """
    return sum(
        1
        for commit in commits
        if isinstance(commit, dict)
        and is_external((commit.get("author") or {}).get("login"), owner)
    )


def fork_acts(slug: str, owner: str) -> tuple[list[Act], list[str]]:
    """Forks that carry commits *somebody external wrote*, and the ones that do not.

    Two corrections are folded in here, and both were found by running the tool
    against reality rather than by reasoning about it (roadmap 6.12):

    **Every branch is compared, not the default one.** The first draft compared
    `default_branch` only and reported this repository's one real external
    contributor as a bookmark: they had done the work on
    `fix/repo-settings-checks` and left `main` in sync, which is what anybody
    following CONTRIBUTING.md does.

    **Only commits an external account authored are counted.** The second draft
    then reported a second "contributor" three commits ahead - and the three were
    *ours*, from `ci/declared-mode`, an upstream branch that outlived its squash
    merge and was copied wholesale when the fork was taken. A fork reflecting our
    own undeleted branches back at us is the purest form of the mistake this gate
    forbids: closing it by counting this repository.
    """
    upstream = branch_heads(slug)
    name = slug.partition("/")[2]
    acts: list[Act] = []
    bookmarks: list[str] = []
    for fork in paged(f"repos/{slug}/forks"):
        assert isinstance(fork, dict)
        login = str((fork.get("owner") or {}).get("login", ""))
        best_branch, best_ahead = "", 0
        for branch, head in branch_heads(f"{login}/{name}").items():
            if upstream.get(branch) == head:
                continue  # a copy of one of our branches, unchanged
            comparison = gh(f"repos/{slug}/compare/HEAD...{login}:{branch}")
            if not isinstance(comparison, dict):
                continue
            theirs = external_commits(comparison.get("commits", []), owner)
            if theirs > best_ahead:
                best_branch, best_ahead = branch, theirs
        if best_ahead:
            acts.append((login, f"holds a fork {best_ahead} commit(s) ahead on `{best_branch}`"))
        else:
            bookmarks.append(
                f"{login} (no commit of their own, created {fork.get('created_at', '?')})"
            )
    return acts, bookmarks


def recurring_contributors(slug: str, owner: str) -> list[Actor]:
    """External logins with >= :data:`RECURRING_MERGES_BAR` merged pull requests."""
    items = paged(f"repos/{slug}/pulls", "-f", "state=closed")
    merges: dict[str, int] = defaultdict(int)
    for item in items:
        assert isinstance(item, dict)
        if not item.get("merged_at"):
            continue
        login = (item.get("user") or {}).get("login")
        if is_external(login, owner):
            merges[str(login)] += 1
    return [
        Actor(login=login, acts=(f"{count} merged pull requests",))
        for login, count in sorted(merges.items())
        if count >= RECURRING_MERGES_BAR
    ]


# ---------------------------------------------------------------------------
# The number that is ours, and the arithmetic that says so
# ---------------------------------------------------------------------------


def clone_baseline(
    clones: Sequence[dict[str, Any]], runs_per_day: dict[str, int]
) -> tuple[list[str], int, int]:
    """Clone counts on the days this repository's CI did not run.

    Returns the dates, their total clones and their total unique cloners. This is
    the only honest thing the clone series can say: on a day with no workflow run
    there is no `actions/checkout`, so whatever remains was somebody else's.
    """
    quiet_dates: list[str] = []
    total = uniques = 0
    for day in clones:
        date = str(day.get("timestamp", ""))[:10]
        if runs_per_day.get(date, 0) == 0:
            quiet_dates.append(date)
            total += int(day.get("count", 0))
            uniques += int(day.get("uniques", 0))
    return quiet_dates, total, uniques


def runs_per_day(slug: str, since: datetime) -> dict[str, int]:
    """Workflow runs per calendar day, over the traffic window."""
    pages = gh(
        f"repos/{slug}/actions/runs",
        "-X",
        "GET",
        "-f",
        f"created=>={since.date().isoformat()}",
        "-f",
        "per_page=100",
        "--paginate",
        "--slurp",
    )
    counts: dict[str, int] = defaultdict(int)
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        for run in page.get("workflow_runs", []):
            counts[str(run.get("created_at", ""))[:10]] += 1
    return dict(counts)


def traffic_signal(slug: str) -> Signal:
    """Clone traffic, reported only with the CI it is made of."""
    try:
        clones = gh(f"repos/{slug}/traffic/clones")
    except PermissionDeniedError:
        return Signal(
            key="clone-traffic",
            condition="clone traffic, net of this repository's own CI",
            phase="context",
            met=None,
            observed="clone traffic needs push rights on the repository",
            evidence=["re-run as a maintainer to see it"],
        )
    if not isinstance(clones, dict):
        return Signal(
            key="clone-traffic",
            condition="clone traffic, net of this repository's own CI",
            phase="context",
            met=None,
            observed="GitHub returned no clone series",
        )
    since = datetime.now(UTC) - timedelta(days=TRAFFIC_WINDOW_DAYS)
    series = clones.get("clones") or []
    quiet, quiet_clones, quiet_uniques = clone_baseline(series, runs_per_day(slug, since))
    evidence = [
        f"{clones.get('count', 0)} clones from {clones.get('uniques', 0)} unique cloners "
        f"over {TRAFFIC_WINDOW_DAYS} days, CI included",
        (
            f"on the {len(quiet)} day(s) with no workflow run ({', '.join(quiet)}): "
            f"{quiet_clones} clones, {quiet_uniques} unique"
            if quiet
            else "CI ran on every day in the window, so nothing here is attributable"
        ),
    ]
    return Signal(
        key="clone-traffic",
        condition="clone traffic, net of this repository's own CI",
        phase="context",
        met=None,  # never a verdict: it is context, and D-030 excludes it from the bar
        observed="reported, and excluded from every bar (D-030)",
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# The index side
# ---------------------------------------------------------------------------


def index_presence(name: str, *, offline: bool) -> Signal:
    """Whether the distribution exists on an index a stranger can install from.

    This is the precondition roadmap 6.11 built the pipeline for and could not
    complete: publishing is three actions inside the owner's account, and until
    one of them happens `pip install mycelium-os` fails for everybody.
    """
    if offline:
        return Signal(
            key="installable",
            condition=f"`{name}` resolves on an index",
            phase="precondition",
            met=None,
            observed="--no-network: the indexes were not asked",
        )
    found: list[str] = []
    unknown: list[str] = []
    for index, template in INDEXES.items():
        url = template.format(name=name)
        try:
            with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - https literal
                payload = json.loads(response.read())
            version = payload.get("info", {}).get("version", "?")
            found.append(f"{index}: {version}")
        except urllib.error.HTTPError as error:
            if error.code != 404:
                unknown.append(f"{index}: HTTP {error.code}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            unknown.append(f"{index}: {error}")
    if found:
        return Signal(
            key="installable",
            condition=f"`{name}` resolves on an index",
            phase="precondition",
            met=True,
            observed="; ".join(found),
        )
    if unknown and len(unknown) == len(INDEXES):
        return Signal(
            key="installable",
            condition=f"`{name}` resolves on an index",
            phase="precondition",
            met=None,
            observed="no index could be reached",
            evidence=unknown,
        )
    return Signal(
        key="installable",
        condition=f"`{name}` resolves on an index",
        phase="precondition",
        met=False,
        observed=f"404 on {', '.join(INDEXES)}",
        evidence=[
            "the pipeline exists and has never been run: `publish.yml`, workflow_dispatch only",
            "docs/workflow/packaging.md, Turning the publish on: the three owner actions",
        ],
    )


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------


def community_plugins_signal() -> Signal:
    """Phase 4's plugin count, re-cut onto the tier D-029 actually permits.

    Recorded as a signal with no automated reading: a contrib-tier plugin arrives
    as a pull request from somebody else, which the actor tally already counts, and
    an out-of-tree plugin cannot exist before the freeze by D-029. So the honest
    report is the rule, not a number this tool invents.
    """
    return Signal(
        key="community-plugins",
        condition=(
            f">= {COMMUNITY_PLUGINS_BAR} plugin or module in `contrib/` authored outside "
            "the maintainer (D-029: out-of-tree plugins spin out only post-freeze)"
        ),
        phase="4",
        met=None,
        observed="counted by hand against contrib/ and its CODEOWNERS; no external author yet",
        evidence=[
            "`contrib/chats` is the maintainer's, built at roadmap 5.5 to prove the API",
            "five external plugin repositories before 1.0 is a bar D-029 forbids satisfying",
        ],
    )


# ---------------------------------------------------------------------------
# The deferral: spec 06 §3's remote-cache trigger (roadmap 7.1, 7.4)
# ---------------------------------------------------------------------------

_FENCED: Final = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

#: No count a real report carries — documents, people, cold builds a week — comes near
#: this. JSON integers have no bound and Python's have none either, so without one a
#: four-hundred-digit "people" parses cleanly and overflows the first float it meets.
_MAX_COUNT: Final[int] = 10**9

#: The same bound for a duration: 10^7 seconds is four months, and no build this
#: instrument times comes within orders of magnitude of it.
_MAX_SECONDS: Final[float] = 1e7


def _count(value: object) -> int | None:
    """A non-negative JSON integer below :data:`_MAX_COUNT`. `bool` is refused, although
    Python calls it one."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value < _MAX_COUNT else None


def _seconds(value: object) -> float | None:
    """A finite, non-negative JSON number below :data:`_MAX_SECONDS`: `json` admits NaN,
    and an integer may not fit in a float at all."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and 0 <= number < _MAX_SECONDS else None


def read_cache_report(payload: object, *, login: str, issue: int) -> CacheReport | None:
    """One report's numbers, or ``None`` when the block is not a well-formed report.

    Every field the trigger decides on is required and typed; a report missing one is
    not *measured* in the sense the trigger means, however much else it says.
    """
    if not isinstance(payload, dict) or payload.get("schema") != CACHE_REPORT_SCHEMA:
        return None
    cold, seeded = payload.get("cold_s"), payload.get("seeded_s")
    if not isinstance(cold, dict) or not isinstance(seeded, dict):
        return None
    documents, people = _count(payload.get("documents")), _count(payload.get("people"))
    rate = payload.get("cold_builds_per_week")
    per_week = None if rate is None else _count(rate)
    if documents is None or people is None or (rate is not None and per_week is None):
        return None
    cold_p50, cold_min = _seconds(cold.get("p50")), _seconds(cold.get("min"))
    seeded_p50, seeded_max = _seconds(seeded.get("p50")), _seconds(seeded.get("max"))
    ceiling = _seconds(payload.get("ceiling_s"))
    if cold_p50 is None or cold_min is None or seeded_p50 is None or seeded_max is None:
        return None
    # A cache cannot save more than the build it replaces: a report that says so is not
    # a measurement, whatever else is right about it.
    if ceiling is None or ceiling > cold_p50:
        return None
    return CacheReport(
        login=login,
        issue=issue,
        documents=documents,
        people=people,
        cold_p50_s=cold_p50,
        cold_min_s=cold_min,
        seeded_p50_s=seeded_p50,
        seeded_max_s=seeded_max,
        ceiling_s=ceiling,
        cold_builds_per_week=per_week,
    )


def reports_in(body: object, *, login: str, issue: int) -> list[CacheReport]:
    """Every report inside one issue body or comment, from its fenced blocks.

    A block is parsed only if it names the schema, so an issue full of unrelated JSON
    costs nothing; and a block that does not parse - malformed, or nested deeper than
    the parser allows, the shape BUG-0030 took - is skipped, never fatal.
    """
    if not isinstance(body, str) or CACHE_REPORT_SCHEMA not in body:
        return []
    found: list[CacheReport] = []
    for block in _FENCED.findall(body):
        if CACHE_REPORT_SCHEMA not in block:
            continue
        try:
            payload = json.loads(block)
        except (ValueError, RecursionError):
            continue
        report = read_cache_report(payload, login=login, issue=issue)
        if report is not None:
            found.append(report)
    return found


def _issue_number(comment: dict[str, Any]) -> int | None:
    """The issue a comment belongs to, from the tail of its `issue_url`."""
    tail = str(comment.get("issue_url") or "").rstrip("/").rpartition("/")[2]
    return int(tail) if tail.isdigit() else None


def cache_reports(
    issues: Sequence[dict[str, Any]], issue_comments: Sequence[dict[str, Any]], owner: str
) -> list[CacheReport]:
    """Every report an external login posted, in an issue nobody closed as *not planned*.

    Closing the issue as not planned is how the owner withdraws a report - a
    fabricated one, or one its reporter retracts - without a code change: the trigger
    reads GitHub's own record of that decision.
    """
    withdrawn = {item.get("number") for item in issues if item.get("state_reason") == "not_planned"}
    found: list[CacheReport] = []
    for item in issues:
        login = (item.get("user") or {}).get("login")
        number = item.get("number")
        if login is None or not is_external(login, owner):
            continue
        if not isinstance(number, int) or number in withdrawn:
            continue
        found.extend(reports_in(item.get("body"), login=login, issue=number))
    for comment in issue_comments:
        login = (comment.get("user") or {}).get("login")
        number = _issue_number(comment)
        if login is None or not is_external(login, owner):
            continue
        if number is None or number in withdrawn:
            continue
        found.extend(reports_in(comment.get("body"), login=login, issue=number))
    return found


def remote_cache_trigger(reports: Sequence[CacheReport]) -> Trigger:
    """Spec 06 §3's entry trigger for the remote build cache, read off the reports.

    It fires on **one** report that is both a team's and pain - the spec's *>= 1 team
    ... with measured duplicate-build pain*, its terms given readings and its number
    left where the spec put it. How much pain is enough to build a remote cache for is
    not decided here: that is the decision the trigger defers, and it is the owner's.
    """
    qualifying = [report for report in reports if report.is_team and report.is_pain]
    condition = (
        f">= {TEAM_REPORTS_BAR} report from `tools/measure_cache_ceiling.py` by an external "
        f"login, on a corpus >= {TEAM_PEOPLE_BAR} people build, with a saving outside the "
        "measurement's own noise"
    )
    evidence = [report.describe() for report in qualifying]
    for report in reports:
        if report in qualifying:
            continue
        reason = "one person is not a team" if not report.is_team else "the saving is noise"
        evidence.append(f"not counted ({reason}) - {report.describe()}")
    return Trigger(
        key="remote-cache-trigger",
        item="roadmap 7.1",
        decision="remote build cache (spec 06 section 3, Phase 5 entry)",
        condition=condition,
        fired=len(qualifying) >= TEAM_REPORTS_BAR,
        observed=f"{len(qualifying)} qualifying of {len(reports)} report(s)",
        evidence=evidence
        or ["no issue or comment carries a report; docs/workflow/adoption.md says how to post one"],
    )


def collect(
    slug: str, owner: str, *, offline: bool
) -> tuple[list[Signal], list[Trigger], list[Actor], list[str]]:
    issues = listed(f"repos/{slug}/issues", "-f", "state=all")
    issue_comments = listed(f"repos/{slug}/issues/comments")
    acts = issue_and_pr_acts(issues) + comment_acts(slug, issue_comments) + discussion_acts(slug)
    fork_engagement, bookmarks = fork_acts(slug, owner)
    actors = tally(acts + fork_engagement, owner)
    recurring = recurring_contributors(slug, owner)
    triggers = [remote_cache_trigger(cache_reports(issues, issue_comments, owner))]

    signals = [
        index_presence(DISTRIBUTION, offline=offline),
        Signal(
            key="engaged-actors",
            condition=f">= {ENGAGED_ACTORS_BAR} external actors engaged at a cost",
            phase="3",
            met=len(actors) >= ENGAGED_ACTORS_BAR,
            observed=f"{len(actors)} of {ENGAGED_ACTORS_BAR}",
            evidence=[f"{actor.login}: {', '.join(actor.acts)}" for actor in actors]
            or ["no external issue, pull request, comment, discussion or fork with commits"],
        ),
        Signal(
            key="recurring-contributors",
            condition=(
                f">= {RECURRING_CONTRIBUTORS_BAR} external contributors with "
                f">= {RECURRING_MERGES_BAR} merged pull requests each"
            ),
            phase="4",
            met=len(recurring) >= RECURRING_CONTRIBUTORS_BAR,
            observed=f"{len(recurring)} of {RECURRING_CONTRIBUTORS_BAR}",
            evidence=[f"{actor.login}: {', '.join(actor.acts)}" for actor in recurring]
            or ["every merged pull request is the owner's or Dependabot's"],
        ),
        community_plugins_signal(),
        traffic_signal(slug),
    ]
    return signals, triggers, actors, bookmarks


def verdict(signals: Sequence[Signal], triggers: Sequence[Trigger] = ()) -> bool:
    """True when nothing in scope is failing. Unreadable is never a pass.

    A gate fails when it is not met; a deferral fails when its trigger *has* fired,
    because the decision it deferred is then owed (ADR-0118). An unreadable trigger is
    reported as such and decides nothing, which leaves the exit code to the gates.
    """
    gates = all(signal.met is not False for signal in signals)
    return gates and not any(trigger.fired is True for trigger in triggers)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def render(
    slug: str,
    signals: Sequence[Signal],
    bookmarks: Sequence[str],
    triggers: Sequence[Trigger] = (),
) -> None:
    print(f"{slug} against the adoption gates re-cut by D-030 (ADR-0138)\n")
    for signal in signals:
        mark = {True: "met       ", False: "NOT MET   ", None: "UNREADABLE"}[signal.met]
        print(f"  {mark} [phase {signal.phase}] {signal.condition}")
        print(f"             {signal.observed}")
        for line in signal.evidence:
            print(f"               - {line}")
    if bookmarks:
        print("\n  not counted - forks with no commits ahead (a bookmark, not a use):")
        for bookmark in bookmarks:
            print(f"               - {bookmark}")
    if triggers:
        print("\nDeferred decisions (spec 06 section 3) - a fired trigger is a decision owed:\n")
    for trigger in triggers:
        mark = {True: "FIRED     ", False: "holding   ", None: "UNREADABLE"}[trigger.fired]
        print(f"  {mark} [{trigger.item}] {trigger.decision}")
        print(f"             {trigger.condition}")
        print(f"             {trigger.observed}")
        for line in trigger.evidence:
            print(f"               - {line}")
    fired = [trigger for trigger in triggers if trigger.fired is True]
    if fired:
        print(
            f"\n{len(fired)} deferral trigger(s) fired: "
            f"{', '.join(trigger.key for trigger in fired)}. The decision each deferred is "
            "now owed; it is the owner's, and the trigger leaves this tool in the change "
            "that records it (ADR-0118, ADR-0154)."
        )
    failing = [signal for signal in signals if signal.met is False]
    print()
    if failing:
        print(
            f"{len(failing)} gate condition(s) not met: "
            f"{', '.join(signal.key for signal in failing)}. "
            "Every one of them moves by somebody outside this repository doing something, "
            "which no change to this repository can cause - see docs/workflow/adoption.md "
            "for the owner actions that have to precede it."
        )
    else:
        print("No gate condition in scope is failing.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="owner/name (default: this checkout's remote)")
    parser.add_argument("--json", action="store_true", help="emit the signals as JSON")
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="skip the index lookups; they are reported unreadable rather than absent",
    )
    arguments = parser.parse_args(argv)

    try:
        slug = arguments.repo or current_slug()
        repository = gh(f"repos/{slug}")
        if not isinstance(repository, dict):
            raise GitHubUnavailableError(f"could not read repos/{slug}")
        owner = str((repository.get("owner") or {}).get("login", slug.partition("/")[0]))
        signals, triggers, actors, bookmarks = collect(slug, owner, offline=arguments.no_network)
    except PermissionDeniedError as error:
        print(f"[github] {error}")
        print("Reading this repository needs rights this token does not carry.")
        return 2
    except GitHubUnavailableError as error:
        print(f"[github] {error}")
        print("This tool asks GitHub about adoption; it needs `gh`, authenticated.")
        return 2

    if arguments.json:
        print(
            json.dumps(
                {
                    "repository": slug,
                    "owner": owner,
                    "signals": [signal.as_dict() for signal in signals],
                    "triggers": [trigger.as_dict() for trigger in triggers],
                    "engaged_actors": [actor.as_dict() for actor in actors],
                    "uncounted_forks": list(bookmarks),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        render(slug, signals, bookmarks, triggers)

    return 0 if verdict(signals, triggers) else 1


if __name__ == "__main__":
    raise SystemExit(main())
