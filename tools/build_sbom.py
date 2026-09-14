#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Build the SBOM of what this project ships, and check that it describes that.

    python tools/build_sbom.py [--extras all] [--out DIR] [--keep]

Spec 06 §4 asks for "signed artifacts + SBOM from 1.0". An SBOM answers one
question for whoever installs this package — *what code am I actually running, at
which versions, under which licences* — and it is only worth attaching if it
answers that about **the artifact** rather than about the tree it was built in.
That distinction is the whole design here (roadmap 6.6, ADR-0117).

**Why a clean environment rather than this repository's own.** Pointing a
generator at `.venv` is the obvious move and produces a confident, wrong answer:
`uv sync --all-extras --dev` installs 162 distributions, of which four are the
runtime closure. An SBOM built there would list pytest, ruff, mypy, hatch and the
whole delivery toolchain as things a consumer of `mycelium-os` is running. So the
wheel is installed into an empty environment and the SBOM is taken of *that*, and
:func:`check_sbom` fails if a development tool appears in the result — the
property the clean environment exists to buy, asserted rather than assumed.

**What it covers.** By default the wheel's own dependencies: the four packages a
plain `pip install mycelium-os` brings. `--extras all` installs every optional
extra as well — embeddings, ingest, synthesis, symbols, watch — which is the
maximal closure this artifact can pull and what a release attaches, because a
consumer who enables an extra is entitled to the same answer. The default is the
cheap one so CI can run this on every push rather than once per release.

**What an SBOM is not.** It describes *one resolution*, taken at the moment it was
generated. `pydantic>=2.11` admits many versions and a consumer installing next
month gets a different one; this document says what the closure was when the
artifact was built, which is what the format is for and the limit of what it can
claim.

Output is CycloneDX 1.6 JSON, written reproducibly — no timestamps, no random
serial — so two runs over the same resolution produce identical bytes and a diff
between two releases is the dependency change.

**The generator is never installed into this project's environment**, and that is
not tidiness. It was first written as a `sbom` dependency group, on the reasoning
that 18 marginal packages for a once-per-release tool were worth keeping out of
`dev` but fine to declare — and syncing that group **changed what the compiler
produces**: `cyclonedx-bom` pulls `chardet`, BeautifulSoup binds
`bs4.dammit.chardet_module` to it if it is importable, and five HTML documents in
the vendored ingested corpus projected differently. `tools/build_ingested_corpus.py
--check` caught it. So the generator runs in an environment of its own, through
``uv tool run``, and cannot be seen by anything this project imports (ADR-0117).

The cost of that isolation is named rather than hidden: the generator's version is
resolved at run time within :data:`GENERATOR`'s range instead of being pinned by
`uv.lock`, and the first run on a machine fetches it. Acceptable because the
output is a release artifact validated against the CycloneDX schema, not a golden
whose bytes a gate compares.

Exit codes: 0 if the SBOM was written and describes the artifact, 1 otherwise.
"""

import argparse
import json
import os
import shutil
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from check_distribution import find_uv, run  # noqa: E402

from mycelium.__about__ import __version__  # noqa: E402

DIST_NAME = "mycelium_os"
PROJECT_NAME = "mycelium-os"
SPEC_VERSION = "1.6"

GENERATOR = "cyclonedx-bom>=7,<8"
"""What produces the document, run in its own environment and never installed here.

A bounded range rather than an exact pin: the library validates its own output
against the published CycloneDX schema, so a newer 7.x writing a better document is
an improvement. The major bound is where a format change would be, and crossing it
is a decision rather than a resolution.
"""

DEV_TOOLS = (
    # A development tool appearing in the SBOM means it was taken of the wrong
    # environment — the defect this tool is shaped to prevent. Named individually
    # so the failure says which one, and chosen as the ones that could only come
    # from this repository's own `.venv`.
    "pytest",
    "ruff",
    "mypy",
    "hatch",
    "hypothesis",
    "twine",
    "mkdocs",
    "cyclonedx-bom",
    "cyclonedx-python-lib",
)


def fail(check: str, message: str) -> bool:
    print(f"[{check}] {message}")
    return False


def runtime_dependencies() -> set[str]:
    """The distribution names `[project.dependencies]` declares, normalised.

    Read from `pyproject.toml` rather than restated, for the reason
    `tools/check_distribution.py` reads the sdist allowlist: a check that keeps
    its own copy of the contract passes while the two disagree.
    """
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    names = set()
    for requirement in config["project"]["dependencies"]:
        name = requirement.split(";")[0].split("[")[0]
        for operator in (">=", "==", "<=", "~=", "!=", ">", "<"):
            name = name.split(operator)[0]
        names.add(normalise(name.strip()))
    return names


def normalise(name: str) -> str:
    """PEP 503 normalisation, so `PyYAML`, `pyyaml` and `py_yaml` compare equal."""
    return "".join("-" if character in "-_." else character for character in name.lower())


def extras() -> list[str]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    return sorted(config["project"].get("optional-dependencies", {}))


# ---------------------------------------------------------------------------
# Generating
# ---------------------------------------------------------------------------


def generator_command(uv: str) -> list[str]:
    """The generator, in an environment of its own.

    ``uv tool run`` resolves and caches :data:`GENERATOR` outside this project, so
    nothing it depends on becomes importable by anything this project runs. That is
    the whole point — see the module docstring for the HTML projections that moved
    when it was a dependency group instead.
    """
    return [uv, "tool", "run", "--from", GENERATOR, "cyclonedx-py"]


def build_wheel(uv: str, out: Path) -> Path | None:
    result = run([uv, "build", "--wheel", "--out-dir", str(out)], cwd=ROOT)
    if result.returncode != 0:
        print(result.stderr.strip())
        print("[build] `uv build --wheel` failed")
        return None
    wheels = sorted(out.glob("*.whl"))
    if len(wheels) != 1:
        print(f"[build] expected one wheel, got {[p.name for p in wheels]}")
        return None
    return wheels[0]


def install_into_clean_environment(uv: str, wheel: Path, venv: Path, *, with_extras: bool) -> bool:
    """A new environment holding the wheel and its dependencies, and nothing else."""
    result = run([uv, "venv", str(venv), "--python", "3.12"])
    if result.returncode != 0:
        return fail("environment", f"could not create a clean environment: {result.stderr.strip()}")

    target = str(wheel)
    if with_extras:
        # `uv pip install "<wheel>[a,b]"` is the documented spelling for extras on a
        # local artifact, and it is the artifact's *own* extras that are wanted here
        # rather than a re-resolution from the project.
        target = f"{wheel}[{','.join(extras())}]"

    env = {**os.environ, "VIRTUAL_ENV": str(venv)}
    env.pop("PYTHONPATH", None)
    result = run([uv, "pip", "install", target], env=env)
    if result.returncode != 0:
        return fail("environment", f"installing the wheel failed: {result.stderr.strip()}")
    return True


def generate(uv: str, venv: Path, destination: Path) -> bool:
    """Run the generator over `venv`, validating against the CycloneDX schema."""
    command = [
        *generator_command(uv),
        "environment",
        str(venv),
        # The root component is this project, described from its own PEP 621
        # metadata — name, licence expression, URLs — rather than inferred from
        # whichever distribution the walker met first.
        "--pyproject",
        str(ROOT / "pyproject.toml"),
        "--mc-type",
        "application",
        "--sv",
        SPEC_VERSION,
        "--of",
        "JSON",
        # No timestamp, no random serial number: two runs over one resolution must
        # produce identical bytes, or a diff between releases is unreadable.
        "--output-reproducible",
        # On by default; named because it is the point. The library validates what
        # it wrote against the published CycloneDX schema, which is the reason to
        # use it rather than to assemble the JSON here (ADR-0117).
        "--validate",
        "-o",
        str(destination),
    ]
    result = run(command)
    if result.returncode != 0:
        print((result.stderr or result.stdout).strip())
        return fail("generate", "the SBOM generator failed or refused to validate its output")
    return stamp_version(destination)


def stamp_version(path: Path) -> bool:
    """Give the root component the version and PURL the generator cannot know.

    `version` is `dynamic` in `pyproject.toml` — hatch reads it from
    `__about__.py` — and the generator reads PEP 621 metadata statically, so the
    root component comes back **unversioned**. An SBOM that does not say which
    release of `mycelium-os` it describes fails the same test this tool applies to
    every other component, and it would be the one exemption nobody asked for.

    Rewritten with sorted keys and a trailing newline, the way every other JSON
    artifact this repository commits or attaches is written, so a diff between two
    releases reads as the dependency change rather than as key churn.
    """
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return fail("generate", f"the generator wrote unreadable JSON: {error}")

    component = document.get("metadata", {}).get("component")
    if not isinstance(component, dict):
        return fail("generate", "the generated SBOM declares no root component")
    component["version"] = __version__
    component["purl"] = f"pkg:pypi/{PROJECT_NAME}@{__version__}"

    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return True


# ---------------------------------------------------------------------------
# Checking what was generated
# ---------------------------------------------------------------------------


def check_sbom(path: Path, *, with_extras: bool) -> bool:
    """Assert the document describes the artifact, not the tree it was built in."""
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return fail("sbom", f"the generated SBOM is not readable JSON: {error}")

    ok = True
    if document.get("bomFormat") != "CycloneDX":
        ok = fail("sbom", f"bomFormat is {document.get('bomFormat')!r}, expected 'CycloneDX'")
    if document.get("specVersion") != SPEC_VERSION:
        ok = fail(
            "sbom", f"specVersion is {document.get('specVersion')!r}, expected {SPEC_VERSION}"
        )

    root = document.get("metadata", {}).get("component", {})
    if normalise(str(root.get("name", ""))) != normalise(PROJECT_NAME):
        ok = fail("sbom", f"the root component is {root.get('name')!r}, expected {PROJECT_NAME!r}")
    if root.get("version") != __version__:
        ok = fail(
            "sbom",
            f"the root component says version {root.get('version')!r}, and this tree is "
            f"{__version__} - an SBOM that cannot name its own release describes nothing",
        )

    components = document.get("components", [])
    present = {normalise(str(component.get("name", ""))) for component in components}

    missing = sorted(runtime_dependencies() - present)
    if missing:
        ok = fail(
            "sbom",
            f"names no component for {missing}, which `[project.dependencies]` declares - "
            "the SBOM does not describe what the wheel installs",
        )

    intruders = sorted(name for name in DEV_TOOLS if normalise(name) in present)
    if intruders:
        ok = fail(
            "sbom",
            f"carries {intruders}, which no consumer of this package installs. The SBOM was "
            "taken of a development environment rather than of the artifact (ADR-0117)",
        )

    unversioned = sorted(
        str(component.get("name"))
        for component in components
        if not str(component.get("version", "")).strip()
    )
    if unversioned:
        ok = fail("sbom", f"{unversioned} carry no version; an SBOM without versions says nothing")

    unlicensed = sorted(
        str(component.get("name")) for component in components if not component.get("licenses")
    )

    print(
        f"  sbom: {len(components)} components, "
        f"{'all extras' if with_extras else 'default install'}, "
        f"{path.stat().st_size / 1024:.0f} KB"
    )
    if unlicensed:
        # Reported, never fatal. A missing licence is a fact about that package's
        # own metadata, not a defect in this document, and failing a release over
        # somebody else's packaging is how a gate teaches people to skip it.
        print(f"  note: {len(unlicensed)} component(s) declare no licence: {unlicensed[:5]}")
    return ok


# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extras",
        choices=["none", "all"],
        default="none",
        help="which optional dependencies the SBOM covers (default: none, the plain install)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="directory to write the SBOM into (default: build/sbom/)",
    )
    parser.add_argument(
        "--wheel",
        type=Path,
        help=(
            "describe this already-built wheel instead of building one. A release "
            "passes the artifact it is about to sign, so the SBOM and the signature "
            "are statements about the same bytes"
        ),
    )
    parser.add_argument("--keep", action="store_true", help="leave the scratch environment behind")
    arguments = parser.parse_args(argv)

    uv = find_uv()
    if uv is None:
        print(
            "[build] `uv` is not on PATH. It builds the wheel, creates the clean "
            f"environment, and runs {GENERATOR} in an environment of its own"
        )
        return 1

    scratch = ROOT / "build" / "sbom-build"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    destination = arguments.out or (ROOT / "build" / "sbom")
    destination.mkdir(parents=True, exist_ok=True)
    with_extras = arguments.extras == "all"
    suffix = ".all-extras" if with_extras else ""
    out = destination / f"{DIST_NAME}-{__version__}{suffix}.cdx.json"

    print(f"building the SBOM of {PROJECT_NAME} {__version__} ({arguments.extras} extras)")
    if arguments.wheel is not None:
        wheel = arguments.wheel
        if not wheel.is_file():
            print(f"[build] {display(wheel)} is not a file")
            return 1
        if __version__ not in wheel.name:
            print(
                f"[build] {wheel.name} does not carry version {__version__}; the SBOM would "
                "describe a different release than this tree"
            )
            return 1
        print(f"  describing {wheel.name}")
    else:
        built = build_wheel(uv, scratch / "dist")
        if built is None:
            return 1
        wheel = built

    venv = scratch / "venv"
    ok = install_into_clean_environment(uv, wheel, venv, with_extras=with_extras)
    if ok:
        python = venv / ("Scripts" if os.name == "nt" else "bin")
        python = python / ("python.exe" if os.name == "nt" else "python")
        ok = generate(uv, python.parent.parent, out)
    if ok:
        ok = check_sbom(out, with_extras=with_extras)

    if not arguments.keep:
        shutil.rmtree(scratch, ignore_errors=True)

    if ok:
        print(f"\nSBOM written to {display(out)}")
    else:
        print("\nThe SBOM does not describe this artifact.")
    return 0 if ok else 1


def display(path: Path) -> str:
    """Repository-relative where it can be, absolute where it cannot.

    `--out` is how a release workflow puts the SBOM beside the artifacts it is
    attaching, which is routinely outside this tree; `relative_to` raises there,
    and a tool must not fail on the last line after doing its work.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
