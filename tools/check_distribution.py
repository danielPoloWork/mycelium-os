#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Check that what a publish would upload is what this project means to ship.

    python tools/check_distribution.py [--skip-install] [--keep]

A published version is **immutable**: a mistake is fixed forward with a new
version, never by overwriting, and an artifact that reached an index cannot be
recalled. So everything checkable about a distribution has to be checked before
the upload rather than after it — and until roadmap 6.11 nothing was. CI ran
``hatch build`` on every cell, proved the tag compiled, and threw the result
away; no test opened the archive, and no test ever installed it.

Four things are checked here, in the order a defect is cheapest to find:

1. **The sdist carries exactly what it declares.** `[tool.hatch.build.targets.sdist]`
   names an allowlist; this asserts the archive's top level matches it. The
   allowlist exists because the denylist it replaced shipped a 1,248-file
   Hypothesis cache, the vendored delivery factory, 2.7 MB of judged corpora and
   — the defect that decided it — whatever untracked work happened to be in the
   builder's tree (ADR-0116).
2. **The wheel carries the package and nothing else**, with its PEP 561 marker.
3. **The metadata is publishable**: `twine check --strict` renders the long
   description the way an index will, and fails on metadata an index would
   reject. A README that renders on GitHub and breaks on PyPI is the classic
   first-publish failure, and it is only visible from the built artifact.
4. **The wheel installs and works.** A clean virtual environment, the wheel and
   nothing else, then `mycelium --version`, `init`, `build` and `search` against
   a throwaway repository. This is the check the README's install line has been
   making on the project's behalf since M1: that a reader who installs the
   package can reach a cited answer. Default install, so no extras, no model and
   no network — the lexical path the tutorial actually walks.

Exit code 0 if every check passes, 1 otherwise. `--skip-install` stops after the
first three (they need no network and take about ten seconds); `--keep` leaves
the build directory behind for inspection.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.__about__ import __version__  # noqa: E402

DIST_NAME = "mycelium_os"

FORBIDDEN = (
    # Each of these was in the v0.5.0 sdist and is the reason the allowlist
    # exists. Named individually so a failure says which mistake came back.
    (".hypothesis", "a machine-local Hypothesis example database"),
    (".eados-core", "the vendored delivery factory, which is not the product"),
    (".claude", "a host's command tree"),
    (".claudeignore", "an untracked local harness file"),
    ("docs/analysis", "uncommitted working notes"),
    ("eval", "the judged corpora, including documentation this project did not write"),
    ("orchestrator", "the EADOS manifest"),
    ("contrib", "a second distribution, which must never ride inside this one"),
    (".git", "repository and CI plumbing"),
    ("uv.lock", "a development lockfile"),
)


def fail(check: str, message: str) -> bool:
    print(f"[{check}] {message}")
    return False


def run(
    command: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argument vectors, never a shell string
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def find_uv() -> str | None:
    """Locate `uv`, which builds and creates the clean environment.

    `shutil.which` first; then the two places its own installer puts it. A
    developer whose `uv` is on the Windows PATH but not the shell's still gets
    the full check rather than a skip they have to notice.
    """
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin"):
        for name in ("uv.exe", "uv"):
            path = candidate / name
            if path.is_file():
                return str(path)
    return None


def declared_allowlist() -> set[str]:
    """The sdist's declared top-level entries, read from `pyproject.toml`.

    Read rather than restated: the allowlist is the contract, and a check that
    kept its own copy would pass while the two disagreed.
    """
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    include = config["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    return {entry.strip("/").split("/")[0] for entry in include}


# ---------------------------------------------------------------------------
# 1. The sdist
# ---------------------------------------------------------------------------


def check_sdist(path: Path) -> bool:
    ok = True
    with tarfile.open(path) as archive:
        names = archive.getnames()
        files = [member for member in archive.getmembers() if member.isfile()]

    roots = {name.split("/")[0] for name in names}
    if len(roots) != 1:
        return fail("sdist", f"expected one top-level directory, found {sorted(roots)}")
    prefix = roots.pop()
    if prefix != f"{DIST_NAME}-{__version__}":
        ok = fail("sdist", f"root is {prefix!r}, expected {DIST_NAME}-{__version__}")

    inner = {name[len(prefix) + 1 :].split("/")[0] for name in names if "/" in name}
    inner.discard("")
    # Written by the build backend rather than declared: `PKG-INFO` is the sdist's
    # metadata, and hatchling always ships the root `.gitignore` so that unpacking
    # and re-building an sdist reproduces the same exclusions.
    allowed = declared_allowlist() | {"PKG-INFO", ".gitignore"}
    unexpected = sorted(inner - allowed)
    if unexpected:
        ok = fail(
            "sdist",
            f"carries {unexpected}, which the allowlist does not name. Either add it to "
            "`[tool.hatch.build.targets.sdist] include` on purpose, or find out why it is "
            "in the archive - an sdist is a defined artifact, not a snapshot of a tree",
        )

    # Matched on whole path segments: `.git` must not catch `.gitignore`, which the
    # backend ships on purpose.
    carried = {name[len(prefix) + 1 :] for name in names if "/" in name}
    for entry, why in FORBIDDEN:
        if any(name == entry or name.startswith(f"{entry}/") for name in carried):
            ok = fail("sdist", f"carries {entry!r} - {why} (ADR-0116)")

    total = sum(member.size for member in files)
    print(
        f"  sdist: {len(files)} files, {total / 1e6:.2f} MB uncompressed, top level {sorted(inner)}"
    )
    if total > 5_000_000:
        ok = fail(
            "sdist",
            f"is {total / 1e6:.1f} MB uncompressed; it holds the package, not the repository",
        )
    return ok


# ---------------------------------------------------------------------------
# 2. The wheel
# ---------------------------------------------------------------------------


def check_wheel(path: Path) -> bool:
    ok = True
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()

    tops = {name.split("/")[0] for name in names}
    expected = {"mycelium", f"{DIST_NAME}-{__version__}.dist-info"}
    if tops != expected:
        ok = fail("wheel", f"top-level entries are {sorted(tops)}, expected {sorted(expected)}")

    if "mycelium/py.typed" not in names:
        ok = fail(
            "wheel",
            "has no `mycelium/py.typed`; consumers type-check the package as `Any` (ADR-0071)",
        )
    for suffix in (".pyc", ".pyo"):
        stale = [name for name in names if name.endswith(suffix)]
        if stale:
            ok = fail("wheel", f"carries {len(stale)} {suffix} files")
    if any("__pycache__" in name for name in names):
        ok = fail("wheel", "carries __pycache__ directories")

    print(f"  wheel: {len(names)} entries, top level {sorted(tops)}")
    return ok


# ---------------------------------------------------------------------------
# 3. The metadata an index will render
# ---------------------------------------------------------------------------


def check_metadata(python: str, artifacts: Sequence[Path]) -> bool:
    result = run([python, "-m", "twine", "check", "--strict", *[str(a) for a in artifacts]])
    if result.returncode != 0:
        print(result.stdout.strip() or result.stderr.strip())
        return fail(
            "metadata",
            "`twine check --strict` refused the distributions; an index would reject or "
            "mis-render them",
        )
    print("  metadata: twine check --strict passed")
    return True


# ---------------------------------------------------------------------------
# 4. The wheel installs, and the installed package works
# ---------------------------------------------------------------------------

DOCUMENT = """# Retry Policy

Failed deliveries retry with exponential backoff, up to five attempts.

## Limits

The ceiling is five attempts per webhook.
"""


def check_install(uv: str, wheel: Path, scratch: Path) -> bool:
    """A clean environment, the wheel, and the walk the tutorial promises."""
    venv = scratch / "venv"
    result = run([uv, "venv", str(venv), "--python", "3.12"])
    if result.returncode != 0:
        return fail("install", f"could not create a clean environment: {result.stderr.strip()}")

    env = {**os.environ, "VIRTUAL_ENV": str(venv)}
    env.pop("PYTHONPATH", None)
    result = run([uv, "pip", "install", str(wheel)], env=env)
    if result.returncode != 0:
        return fail("install", f"`uv pip install` of the wheel failed: {result.stderr.strip()}")

    binaries = venv / ("Scripts" if os.name == "nt" else "bin")
    mycelium = binaries / ("mycelium.exe" if os.name == "nt" else "mycelium")
    if not mycelium.is_file():
        return fail("install", "the wheel installed no `mycelium` console script")

    result = run([str(mycelium), "--version"])
    if result.returncode != 0 or __version__ not in result.stdout:
        return fail(
            "install",
            f"`mycelium --version` said {result.stdout.strip()!r}, expected {__version__}",
        )

    repo = scratch / "repo"
    repo.mkdir()
    if run([str(mycelium), "init", str(repo)]).returncode != 0:
        result = run([str(mycelium), "init"], cwd=repo)
        if result.returncode != 0:
            return fail("install", f"`mycelium init` failed: {result.stderr.strip()}")

    verified = repo / "knowledge" / "verified"
    verified.mkdir(parents=True, exist_ok=True)
    (verified / "retries.md").write_text(DOCUMENT, encoding="utf-8")

    result = run([str(mycelium), "build", str(repo)])
    if result.returncode != 0:
        return fail(
            "install", f"`mycelium build` failed: {(result.stderr or result.stdout).strip()}"
        )

    result = run([str(mycelium), "search", "exponential backoff", "--path", str(repo), "--json"])
    if result.returncode != 0:
        result = run([str(mycelium), "search", "exponential backoff", "--json"], cwd=repo)
    if result.returncode != 0:
        return fail(
            "install", f"`mycelium search` failed: {(result.stderr or result.stdout).strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return fail(
            "install", f"`mycelium search --json` did not emit JSON: {result.stdout[:200]!r}"
        )
    results = payload.get("results") or []
    if not results:
        return fail(
            "install", "a default install found nothing; the lexical path is what a reader gets"
        )
    uri = str(results[0].get("uri", ""))
    if not uri.startswith("mycelium://"):
        return fail("install", f"the first result carries no citation URI: {uri!r}")

    print(f"  install: clean venv -> `pip install` -> cited answer ({uri})")
    return True


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="stop after the archive and metadata checks (no clean environment, no network)",
    )
    parser.add_argument("--keep", action="store_true", help="leave the build directory in place")
    arguments = parser.parse_args()

    uv = find_uv()
    if uv is None:
        print("[build] `uv` is not on PATH; it builds the distributions and the clean environment")
        return 1

    scratch = ROOT / "build" / "distribution-check"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    out = scratch / "dist"

    print(f"building {DIST_NAME} {__version__}")
    result = run([uv, "build", "--out-dir", str(out)], cwd=ROOT)
    if result.returncode != 0:
        print(result.stderr.strip())
        print("[build] `uv build` failed")
        return 1

    sdists = sorted(out.glob("*.tar.gz"))
    wheels = sorted(out.glob("*.whl"))
    if len(sdists) != 1 or len(wheels) != 1:
        print(f"[build] expected one sdist and one wheel, got {[p.name for p in out.iterdir()]}")
        return 1
    sdist, wheel = sdists[0], wheels[0]

    ok = check_sdist(sdist)
    ok = check_wheel(wheel) and ok
    ok = check_metadata(sys.executable, (sdist, wheel)) and ok
    if not arguments.skip_install:
        ok = check_install(uv, wheel, scratch) and ok
    else:
        print("  install: skipped (--skip-install)")

    if not arguments.keep:
        shutil.rmtree(scratch, ignore_errors=True)

    print(
        "\nThe distribution is what it says it is."
        if ok
        else "\nThe distribution is NOT publishable."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
