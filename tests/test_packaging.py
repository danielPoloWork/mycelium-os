# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What this project publishes, and what the publish path may not become (roadmap 6.11).

`tools/check_distribution.py` checks the built artifacts — it opens the archives,
renders the metadata and installs the wheel — and costs a minute. This file checks
the *declarations* behind them, costs nothing, and pins the two things a built
artifact cannot show:

- **The sdist allowlist still names what it was narrowed to.** The archive built at
  v0.5.0 carried 14.5 MB across thirty top-level entries, including a machine-local
  Hypothesis cache and whatever untracked work was in the builder's tree. Widening
  the list back is a decision; doing it by accident is what this stops (ADR-0116).
- **The publish path cannot fire by itself, and holds no secret.** A published
  version is immutable and a package name is claimed by its first upload, so
  "publishing is the human checkpoint" has to be a property of the workflow rather
  than a promise in a document.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


@pytest.fixture(scope="module")
def pyproject() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        loaded: dict[str, Any] = tomllib.load(handle)
    return loaded


@pytest.fixture(scope="module")
def publish() -> dict[str, Any]:
    loaded = yaml.safe_load((WORKFLOWS / "publish.yml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def triggers(workflow: dict[str, Any]) -> set[str]:
    """The events a workflow fires on.

    `on:` is read by PyYAML as the boolean `True` — YAML 1.1's Norway problem, the
    same one ADR-0006 records for frontmatter — so both spellings are accepted here
    rather than silently returning nothing.
    """
    raw = workflow.get("on", workflow.get(True))
    if isinstance(raw, str):
        return {raw}
    return set(raw)


# ---------------------------------------------------------------------------
# What ships
# ---------------------------------------------------------------------------


def test_the_sdist_ships_the_package_and_not_the_repository(pyproject: dict[str, Any]) -> None:
    """An allowlist, and the entries it must not regain.

    Each name below was in the v0.5.0 sdist under the `exclude = ["contrib"]`
    denylist that preceded it. Two were defects rather than bloat: `.hypothesis` is
    a per-machine cache, so the artifact was not reproducible, and `docs/analysis`
    was uncommitted work, so a publish would have released it permanently.
    """
    sdist = pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert "exclude" not in sdist, (
        "the sdist is defined by an allowlist; an exclude list would make it "
        "'the working directory minus what somebody remembered' again (ADR-0116)"
    )
    assert set(sdist["include"]) == {
        "/src/mycelium",
        "/pyproject.toml",
        "/README.md",
        "/LICENSE",
        "/CHANGELOG.md",
    }


def test_the_wheel_packages_only_the_import_package(pyproject: dict[str, Any]) -> None:
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/mycelium"]


# ---------------------------------------------------------------------------
# What an index will show
# ---------------------------------------------------------------------------


def test_the_index_page_can_reach_the_docs_and_the_changelog(pyproject: dict[str, Any]) -> None:
    """`docs/workflow/packaging.md` has promised "the links a registry expects
    (repo, docs, changelog)" since M1, and the metadata carried two of them."""
    urls = pyproject["project"]["urls"]
    assert {"Homepage", "Documentation", "Changelog", "Source", "Issues"} <= set(urls)
    assert all(url.startswith("https://") for url in urls.values())


def test_the_advertised_python_versions_are_the_tested_ones(pyproject: dict[str, Any]) -> None:
    """A classifier is a claim about support, and CI is where support is proven.

    One fact in two files is how they drift, so the claim is compared against the
    build matrix rather than maintained beside it.
    """
    classifiers = pyproject["project"]["classifiers"]
    advertised = {
        line.rsplit(" :: ", 1)[-1]
        for line in classifiers
        if line.startswith("Programming Language :: Python :: ")
        and line[-1].isdigit()
        and "." in line
    }
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    tested = {
        entry["toolchain"].removeprefix("python-")
        for entry in workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
    }
    assert advertised == tested, (
        f"the package advertises Python {sorted(advertised)} and CI tests {sorted(tested)}"
    )
    floor = pyproject["project"]["requires-python"].removeprefix(">=")
    assert min(advertised, key=lambda v: tuple(map(int, v.split(".")))) == floor


def test_the_licence_is_stated_once_in_the_current_spelling(pyproject: dict[str, Any]) -> None:
    """`license = "Apache-2.0"` is a PEP 639 SPDX expression and becomes
    `License-Expression` in the metadata. PEP 639 deprecates the classifier form, so
    carrying both would state one fact twice, in two spellings, one of them obsolete."""
    assert pyproject["project"]["license"] == "Apache-2.0"
    assert not [
        line for line in pyproject["project"]["classifiers"] if line.startswith("License ::")
    ]


def test_the_package_says_what_it_is(pyproject: dict[str, Any]) -> None:
    """Keywords and a development status are what a reader searching an index matches
    on — and reaching that reader is the whole of 6.12."""
    project = pyproject["project"]
    assert project["keywords"]
    assert "mcp" in project["keywords"]
    status = [line for line in project["classifiers"] if line.startswith("Development Status ::")]
    assert len(status) == 1
    assert "Typing :: Typed" in project["classifiers"]


# ---------------------------------------------------------------------------
# What the publish path may not become
# ---------------------------------------------------------------------------


def test_publishing_cannot_happen_as_a_side_effect(publish: dict[str, Any]) -> None:
    """The safety property, made structural.

    `release.yml` fires on a tag push and drafts a GitHub Release; nothing that fires
    on a push may publish. A tag is pushed by an agent (AGENTS.md §11) and a publish
    is the maintainer's, so the two must not share a trigger.
    """
    assert triggers(publish) == {"workflow_dispatch"}


def test_the_publish_default_is_the_index_that_can_be_thrown_away(
    publish: dict[str, Any],
) -> None:
    """TestPyPI is the rehearsal: a real upload over a real Trusted Publisher, on an
    index whose contents nobody depends on. The default must be the harmless one."""
    dispatch = publish.get("on", publish.get(True))["workflow_dispatch"]
    index = dispatch["inputs"]["index"]
    assert index["default"] == "testpypi"
    assert set(index["options"]) == {"testpypi", "pypi"}


def test_the_publish_job_is_gated_by_an_environment(publish: dict[str, Any]) -> None:
    """The environment is where GitHub enforces an approval, and where the index
    scopes the Trusted Publisher. Losing it would make the approval a convention."""
    job = publish["jobs"]["publish"]
    assert job["environment"]["name"] == "${{ inputs.index }}"


def test_the_publish_job_holds_no_credential(publish: dict[str, Any]) -> None:
    """Trusted Publishing mints a short-lived token per run, so there is no API token
    to leak, rotate or misplace. A password or a `secrets.*_TOKEN` appearing here would
    be a step back to the thing it replaced (threat model B2)."""
    job = publish["jobs"]["publish"]
    assert job["permissions"] == {"id-token": "write", "contents": "read"}
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "password:" not in text
    assert "PYPI_TOKEN" not in text and "PYPI_API_TOKEN" not in text


def test_the_publish_action_is_pinned_to_a_commit(publish: dict[str, Any]) -> None:
    """Threat boundary B2: third-party action code runs with this job's OIDC identity,
    so the version that runs is the version that was reviewed."""
    steps = publish["jobs"]["publish"]["steps"]
    action = next(step["uses"] for step in steps if str(step.get("uses", "")).startswith("pypa/"))
    _, _, reference = action.partition("@")
    assert len(reference) == 40 and all(c in "0123456789abcdef" for c in reference), (
        f"{action} is not pinned to a full commit SHA"
    )


def test_the_publish_job_checks_the_distribution_before_uploading(publish: dict[str, Any]) -> None:
    """The last moment an artifact can be refused. An index cannot un-publish."""
    steps = publish["jobs"]["publish"]["steps"]
    commands = " ".join(str(step.get("run", "")) for step in steps)
    assert "tools/check_distribution.py" in commands
    names = [str(step.get("name", "")) for step in steps]
    assert names.index("Check the distribution is what it says it is") < names.index("Publish")
