# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What the command line is allowed to import (roadmap 6.36, ADR-0151).

Every invocation of `mycelium` — including `--version` and `--help` — pays for
whatever `mycelium.cli.app` pulls in at module scope. Before this item that was
**481 modules and ~1.9 s**, because the CLI is the front door to every subsystem
and reached them all directly.

The guard here is a *property*, not a timing: a wall-clock assertion would be
flaky on a shared runner and would say nothing about why it regressed. What is
asserted instead is which modules `sys.modules` holds after the import, which is
exactly the fact that makes the CLI slow and is stable on every machine.

The failure this catches is a one-line edit: someone adds
`from mycelium.store import SqliteStore` to the top of `cli/app.py` because a new
command needs it, and every `mycelium --version` silently pays for sqlite,
pydantic and the record contracts again.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = (
    "pydantic",
    "mycelium.sdk.types",
    "mycelium.sdk.protocols",
    "mycelium.build",
    "mycelium.config",
    "mycelium.store",
    "mycelium.ingest",
    "mycelium.embedding",
    "mycelium.eval",
    "mycelium.export",
    "mycelium.graph",
    "mycelium.retrieval",
    "mycelium.synthesis",
    "mycelium.verification",
    "mycelium.watch",
    "mycelium.mcp",
    "mycelium.cli.doctor",
)
"""Subsystems no CLI invocation may import merely to parse its arguments.

Each is here because a command *body* uses it and a local import is enough. The
list is the decision, restated where a reviewer of a future import will see it.
"""


def loaded_after(statement: str) -> set[str]:
    """The module names `sys.modules` holds after running `statement` fresh."""
    code = f"import sys; {statement}; print('\\n'.join(sorted(sys.modules)))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT / "src",
    )
    assert result.returncode == 0, result.stderr
    return set(result.stdout.split())


@pytest.fixture(scope="module")
def cli_modules() -> set[str]:
    return loaded_after("import mycelium.cli.app")


@pytest.mark.parametrize("forbidden", FORBIDDEN)
def test_the_cli_does_not_import_a_subsystem_to_parse_arguments(
    cli_modules: set[str], forbidden: str
) -> None:
    assert forbidden not in cli_modules, (
        f"`import mycelium.cli.app` pulled in {forbidden!r}. Every `mycelium --version` "
        "now pays for it. Move the import into the command body that needs it."
    )


def test_the_cli_imports_what_typer_genuinely_needs(cli_modules: set[str]) -> None:
    """The two modules that must stay, so the guard above cannot be satisfied by
    breaking the command tree instead of by deferring an import."""
    assert "typer" in cli_modules
    assert "mycelium.defaults" in cli_modules
    assert "mycelium.sdk.enums" in cli_modules


def test_the_modules_typer_reads_stay_dependency_free() -> None:
    """`mycelium.defaults` and `mycelium.sdk.enums` exist to be cheap.

    Typer evaluates a command's annotations and default values while building its
    tree, so anything these two import lands on every invocation's path — which
    is the defect the split was made to remove, reintroduced one import later.
    """
    for module in ("mycelium.defaults", "mycelium.sdk.enums"):
        loaded = loaded_after(f"import {module}")
        assert not [name for name in loaded if name.startswith("pydantic")], module
        # `mycelium` and `mycelium.__about__` come with the package itself: its
        # `__init__` is a lazy facade holding the version and nothing else
        # (ADR-0140), which is why importing any submodule costs 7 ms.
        allowed = {module, "mycelium.sdk", "mycelium.__about__"}
        reached = {n for n in loaded if n.startswith("mycelium.") and n not in allowed}
        assert reached == set(), f"{module} reached {sorted(reached)}"


def test_the_registry_does_not_load_the_contracts_to_find_no_module() -> None:
    """`main()` asks `mycelium.modules` what is installed on every invocation.

    Discovery is entry-point metadata; validating a module against the `Module`
    protocol is not, and only happens once one is actually installed.
    """
    loaded = loaded_after("import mycelium.modules")
    assert "mycelium.sdk.protocols" not in loaded
    assert not [name for name in loaded if name.startswith("pydantic")]


def test_the_re_exports_are_the_same_objects() -> None:
    """Moving a definition may not change what an existing import returns."""
    from mycelium.build.snapshots import DEFAULT_CACHE_MAX_AGE_DAYS, DEFAULT_KEEP
    from mycelium.defaults import DEFAULT_CACHE_MAX_AGE_DAYS as CACHE_AGE
    from mycelium.defaults import DEFAULT_EXPORT_DIRNAME as EXPORT_DIR
    from mycelium.defaults import DEFAULT_KEEP as KEEP
    from mycelium.defaults import MAX_DEPTH as DEPTH
    from mycelium.defaults import STORE_DIRNAME as DIRNAME
    from mycelium.export import DEFAULT_EXPORT_DIRNAME
    from mycelium.graph import MAX_DEPTH
    from mycelium.sdk.enums import EdgeType as EnumEdgeType
    from mycelium.sdk.types import EdgeType
    from mycelium.store import STORE_DIRNAME

    assert (DEFAULT_KEEP, DEFAULT_CACHE_MAX_AGE_DAYS) == (KEEP, CACHE_AGE)
    assert (MAX_DEPTH, DEFAULT_EXPORT_DIRNAME, STORE_DIRNAME) == (DEPTH, EXPORT_DIR, DIRNAME)
    assert EdgeType is EnumEdgeType  # one class, two documented spellings
