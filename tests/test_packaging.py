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

import hashlib
import json
import re
import tomllib
import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.boundary("B2")
"""The threat-model boundary these tests hold (docs/security/threat-model.md §4)."""

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


@pytest.fixture(scope="module")
def release() -> dict[str, Any]:
    loaded = yaml.safe_load((WORKFLOWS / "release.yml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="module")
def labels() -> list[dict[str, Any]]:
    loaded = yaml.safe_load((ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    return loaded


def triggers(workflow: dict[str, Any]) -> set[str]:
    """The events a workflow fires on.

    `on:` is read by PyYAML as the boolean `True` — YAML 1.1's Norway problem, the
    same one ADR-0006 records for frontmatter — so both spellings are accepted here
    rather than silently returning nothing.
    """
    raw = workflow.get("on", workflow.get(True))  # type: ignore[call-overload]
    if isinstance(raw, str):
        return {raw}
    assert raw is not None, "the workflow declares no trigger at all"
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
    # `on:` is YAML 1.1's boolean `True`; both spellings are read, as above.
    triggers = publish.get("on", publish.get(True))  # type: ignore[call-overload]
    assert triggers is not None, "the workflow declares no trigger at all"
    dispatch = triggers["workflow_dispatch"]
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


# ---------------------------------------------------------------------------
# What a consumer can verify about a release (roadmap 6.6, ADR-0117)
# ---------------------------------------------------------------------------


def release_steps(release: dict[str, Any]) -> list[dict[str, Any]]:
    steps = release["jobs"]["draft-release"]["steps"]
    assert isinstance(steps, list)
    return steps


def test_the_release_attests_what_it_built(release: dict[str, Any]) -> None:
    """Spec 06 §4's "signed artifacts", made structural.

    Two attestations, because they answer different questions: provenance says these
    bytes came from this workflow at this commit, and the SBOM attestation binds the
    dependency list to the wheel's digest so a friendlier SBOM cannot be swapped in.
    """
    uses = [str(step.get("uses", "")) for step in release_steps(release)]
    assert any(action.startswith("actions/attest-build-provenance@") for action in uses)
    assert any(action.startswith("actions/attest-sbom@") for action in uses)


def test_the_release_can_sign_and_still_holds_no_key(release: dict[str, Any]) -> None:
    """Sigstore's keyless flow: an OIDC identity minted per run, nothing stored.

    `id-token` and `attestations` are what signing needs; a signing key in repository
    secrets would be a thing to leak, rotate and misplace, and threat boundary B2
    would have to cover it (the same property publishing has, ADR-0116).
    """
    assert release["permissions"] == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    for forbidden in ("private-key", "GPG_", "COSIGN_", "SIGNING_KEY"):
        assert forbidden not in text, f"release.yml mentions {forbidden}"


def test_every_release_action_is_pinned_to_a_commit(release: dict[str, Any]) -> None:
    """Threat boundary B2, applied to the two actions that now hold `attestations:
    write`: third-party code runs with this job's signing identity, so the version
    that runs is the version that was reviewed."""
    for action in [str(step.get("uses", "")) for step in release_steps(release)]:
        if not action or action.startswith("actions/checkout") or "/" not in action:
            continue
        if action.startswith(("actions/setup-", "astral-sh/")):
            continue  # tag-pinned by the factory's own decision (threat model B2)
        _, _, reference = action.partition("@")
        assert len(reference) == 40 and all(c in "0123456789abcdef" for c in reference), (
            f"{action} is not pinned to a full commit SHA"
        )


def test_the_release_builds_the_sbom_from_the_wheel_it_ships(release: dict[str, Any]) -> None:
    """The SBOM, the provenance and the upload must describe the same bytes.

    `--wheel` is what makes that true: without it the generator builds its own wheel,
    and the SBOM would describe a second set of bytes however identical they ought to
    be. `--extras all` because a consumer who enables an extra is entitled to the
    same answer as one who does not.
    """
    commands = " ".join(str(step.get("run", "")) for step in release_steps(release))
    assert "tools/build_sbom.py" in commands
    assert "--wheel" in commands and "--extras all" in commands


def test_the_release_attaches_the_sbom_beside_the_archives(release: dict[str, Any]) -> None:
    """An attestation lives in GitHub's store and needs a CLI to read. Someone deciding
    whether to install this should be able to read the dependency list without one."""
    draft = next(
        step
        for step in release_steps(release)
        if str(step.get("uses", "")).startswith("softprops/action-gh-release@")
    )
    files = str(draft["with"]["files"])
    assert "dist/*" in files
    assert ".cdx.json" in files


SERIAL_STEP = "Give the SBOM the serial number actions/attest requires"
UUID5_URN = re.compile(
    r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _serial_step(release: dict[str, Any]) -> dict[str, Any]:
    return next(step for step in release_steps(release) if step.get("name") == SERIAL_STEP)


def _stamp(
    release: dict[str, Any],
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    wheel: bytes,
    serial: str | None = None,
) -> dict[str, Any]:
    """Run the workflow step's own code against a fixture, and read back what it wrote."""
    (root / "dist").mkdir(parents=True, exist_ok=True)
    (root / "sbom").mkdir(parents=True, exist_ok=True)
    (root / "dist" / "mycelium_os-0.6.0-py3-none-any.whl").write_bytes(wheel)
    document: dict[str, Any] = {"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1}
    if serial is not None:
        document["serialNumber"] = serial
    sbom = root / "sbom" / "mycelium_os-0.6.0.all-extras.cdx.json"
    sbom.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setenv("EXPECTED_VERSION", "0.6.0")
    exec(compile(str(_serial_step(release)["run"]), SERIAL_STEP, "exec"), {"__name__": "__main__"})
    loaded = json.loads(sbom.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_the_sbom_gets_its_serial_between_being_built_and_being_attested(
    release: dict[str, Any],
) -> None:
    """BUG-0033: v0.6.0's first release run failed at the SBOM attestation.

    The step has to sit after the generator and before `actions/attest-sbom`, and it has
    to be a workflow step rather than a change to `tools/build_sbom.py`: a re-draft of an
    existing tag runs this file from the default branch against the tag's tree
    (BUG-0006), so only the workflow reaches a tag cut before the fix.
    """
    steps = release_steps(release)
    names = [str(step.get("name", "")) for step in steps]
    built = next(i for i, s in enumerate(steps) if "tools/build_sbom.py" in str(s.get("run", "")))
    attested = next(
        i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/attest-sbom@")
    )
    assert built < names.index(SERIAL_STEP) < attested
    assert _serial_step(release)["shell"] == "python"


def test_the_stamped_sbom_is_one_actions_attest_recognises(
    release: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`actions/attest`'s `checkIsCycloneDX` wants `bomFormat`, `serialNumber` and
    `specVersion` all present; the CycloneDX schema makes the middle one optional, and
    `--output-reproducible` omits it, which is the whole defect."""
    stamped = _stamp(release, tmp_path, monkeypatch, wheel=b"wheel bytes")
    assert stamped["bomFormat"] and stamped["specVersion"] and stamped["serialNumber"]
    assert UUID5_URN.match(stamped["serialNumber"]), stamped["serialNumber"]


def test_the_serial_names_the_wheel_and_survives_a_rerun(
    release: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproducibility is why `--output-reproducible` is on: two runs over one wheel must
    still write identical bytes, so the serial is derived rather than random - and derived
    from the wheel's digest, so a different artifact cannot share it."""
    first = _stamp(release, tmp_path / "a", monkeypatch, wheel=b"wheel bytes")
    again = _stamp(release, tmp_path / "b", monkeypatch, wheel=b"wheel bytes")
    other = _stamp(release, tmp_path / "c", monkeypatch, wheel=b"different bytes")
    assert first["serialNumber"] == again["serialNumber"]
    assert first["serialNumber"] != other["serialNumber"]
    digest = hashlib.sha256(b"wheel bytes").hexdigest()
    name = f"pkg:pypi/mycelium-os@0.6.0?checksum=sha256:{digest}"
    assert first["serialNumber"] == uuid.uuid5(uuid.NAMESPACE_URL, name).urn


def test_an_sbom_that_already_carries_a_serial_is_left_alone(
    release: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the generator ever starts writing one, the workflow must not overwrite it."""
    existing = "urn:uuid:3e671687-395b-41f5-a30f-a58921a69b79"
    stamped = _stamp(release, tmp_path, monkeypatch, wheel=b"wheel bytes", serial=existing)
    assert stamped["serialNumber"] == existing


def test_the_sbom_generator_is_not_a_dependency_of_this_project(
    pyproject: dict[str, Any],
) -> None:
    """The generator runs in an environment of its own and is declared in none of ours.

    This began as a `sbom` dependency group, on the reasoning that 18 marginal packages
    for a once-per-release tool were worth keeping out of `dev` but fine to declare.
    Syncing that group **changed what the compiler produces**: `cyclonedx-bom` pulls
    `chardet`, `bs4.dammit` binds to it whenever it is importable, and seven HTML
    documents in the vendored ingested corpus projected differently —
    `tools/build_ingested_corpus.py --check` is what caught it. (Five, as first
    counted at 6.6; seven when the incident was replayed at 6.15, because the count
    moves with the detector's version — BUG-0032. The HTML lane no longer asks a
    detector at all, ADR-0134, and this rule is not about encodings.)

    So the rule is stronger than "not in `dev`": a tool that is not part of this
    product must not be resolvable alongside it at all, because what is importable is
    an input to the compiler whether or not anything imports it on purpose (ADR-0117).
    """
    project = pyproject["project"]
    declared = [
        *project["dependencies"],
        *(entry for extra in project["optional-dependencies"].values() for entry in extra),
        *(entry for group in pyproject["dependency-groups"].values() for entry in group),
    ]
    assert not [entry for entry in declared if "cyclonedx" in entry]
    assert "sbom" not in pyproject["dependency-groups"]
    # And no workflow installs it. Read from the parsed `run:` steps rather than from
    # the file's text: both workflows carry a comment saying why the sync is absent,
    # and a check that cannot tell an instruction from an explanation of its absence
    # would forbid documenting the decision.
    for name in ("ci.yml", "release.yml"):
        workflow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
        for job, definition in workflow["jobs"].items():
            for step in definition.get("steps", []):
                assert "--group sbom" not in str(step.get("run", "")), (
                    f"{name}'s {job!r} job installs the generator into the project"
                )


# ---------------------------------------------------------------------------
# The contribution ladder's rungs (roadmap 6.6)
# ---------------------------------------------------------------------------


def test_the_ladder_labels_are_declared_where_the_manifest_is(labels: list[dict[str, Any]]) -> None:
    """Both existed on GitHub as stock labels and neither was declared here, so the
    manifest that calls itself canonical was not. `tools/check_repo_settings.py` is
    what compares the two; this pins that they are declared at all."""
    declared = {str(item["name"]) for item in labels}
    assert {"good first issue", "help wanted"} <= declared
    reserved = next(item for item in labels if item["name"] == "good first issue")
    assert "Reserved" in str(reserved["description"])


def test_the_reservation_rule_binds_the_agent_contract() -> None:
    """The label is a promise, and AGENTS.md is where a promise to a contributor
    becomes a rule an agent is held to. Without it the invitation is withdrawn before
    anyone can accept it — 43 items closed in five days at Milestone 5."""
    contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "good first issue" in contract
    assert "does not take" in contract or "will not take" in contract


def test_codeowners_names_the_paths_that_carry_a_contract() -> None:
    """One maintainer owns everything, so these lines resolve to the same person and
    are not thereby redundant: CODEOWNERS is where a reviewer finds out which paths
    carry a compatibility event rather than an implementation detail."""
    owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    for path in ("/src/mycelium/sdk/", "/tests/fixtures/contracts/", "/docs/compatibility.md"):
        assert path in owners, f"CODEOWNERS does not name {path}"
    assert "/.github/workflows/" in owners
