# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The plugin cookiecutter (roadmap 6.2): what it generates is checked the way this
repository checks its own code — rendered, then linted and type-checked with `ruff`
and `mypy --strict`, then run.

`Synthesizer` is deliberately not one of the offered kinds: `mycelium.synthesis`
resolves exactly one built-in and has no entry-point path for a third party
(`mycelium.synthesis.build_synthesizer`), so a cookiecutter that generated one would
produce a class nothing in the product loads — see the plugin-author guide.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from cookiecutter.exceptions import FailedHookException
from cookiecutter.main import cookiecutter

from mycelium.sdk.protocols import Connector, Module, Parser

TEMPLATE = Path(__file__).parent.parent / "tools" / "cookiecutter-mycelium-plugin"

KINDS = {
    "parser": Parser,
    "connector": Connector,
    "module": Module,
}


def render(
    tmp_path: Path, *, plugin_kind: str, plugin_id: str = "test-thing", **extra: str
) -> Path:
    """Render the template with `no_input`, and return the generated project root."""
    cookiecutter(
        str(TEMPLATE),
        no_input=True,
        output_dir=str(tmp_path),
        extra_context={"plugin_kind": plugin_kind, "plugin_id": plugin_id, **extra},
    )
    (project,) = tmp_path.iterdir()
    return project


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


# ---------------------------------------------------------------------------
# The naming rule (spec 05 §4.4, D-026) refuses before a line of code exists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plugin_id",
    [
        "too-many-words-here",  # rule 1: one or two words
        "Search",  # rule 1: lowercase only
        "search",  # rule 3: reserved core concept
        "graph",
        "build",
        "my-llm",  # rule 2: technology suffix
        "chat-ai",
        "helper-gpt",
    ],
)
def test_a_naming_rule_violation_is_refused_before_generation(
    tmp_path: Path, plugin_id: str
) -> None:
    with pytest.raises(FailedHookException):
        render(tmp_path, plugin_kind="parser", plugin_id=plugin_id)
    assert not any(tmp_path.iterdir()), "a refused id must leave nothing behind"


@pytest.mark.parametrize("plugin_id", ["wiki", "chats", "pdf-tables", "s3"])
def test_a_lawful_id_is_accepted(tmp_path: Path, plugin_id: str) -> None:
    project = render(tmp_path, plugin_kind="parser", plugin_id=plugin_id)
    assert project.exists()


# ---------------------------------------------------------------------------
# One implementation per kind, and nothing left over from the other two
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_only_the_chosen_kinds_files_survive(tmp_path: Path, kind: str) -> None:
    project = render(tmp_path, plugin_kind=kind)
    src = project / "src" / "mycelium_test_thing"
    tests = project / "tests"

    assert (src / "plugin.py").is_file()
    assert (tests / "test_plugin.py").is_file()
    for other in KINDS:
        if other != kind:
            assert not (src / f"_{other}.py").exists()
            assert not (tests / f"_test_{other}.py").exists()
            assert not (src / f"{other}.py").exists()


def test_the_license_is_rendered_not_copied_verbatim(tmp_path: Path) -> None:
    project = render(tmp_path, plugin_kind="parser")
    text = (project / "LICENSE").read_text(encoding="utf-8")
    assert "{{ cookiecutter" not in text
    assert "Copyright 2026 Your Name" in text
    assert "Apache License" in text


# ---------------------------------------------------------------------------
# What the rendered project produces is real, checked Python
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_rendered_plugin_is_ruff_clean(tmp_path: Path, kind: str) -> None:
    project = render(tmp_path, plugin_kind=kind)
    checked = _run(sys.executable, "-m", "ruff", "check", "src", "tests", cwd=project)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    formatted = _run(sys.executable, "-m", "ruff", "format", "--check", "src", "tests", cwd=project)
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_rendered_plugin_is_mypy_strict_clean(tmp_path: Path, kind: str) -> None:
    project = render(tmp_path, plugin_kind=kind)
    # `--config-file` points at the *rendered* project's own pyproject.toml, not
    # this repository's: mypy otherwise walks up from the target path and would
    # find this repository's config instead, whose `[tool.mypy] exclude` for this
    # very template computes a path relative to a drive the rendered project may
    # not be on (Windows, tmp_path on a different drive than the checkout).
    checked = _run(
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(project / "pyproject.toml"),
        "--strict",
        "src",
        cwd=project,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize(("kind", "protocol"), sorted(KINDS.items()))
def test_the_rendered_plugin_satisfies_its_protocol(
    tmp_path: Path, kind: str, protocol: type
) -> None:
    """The check a plugin author's own generated test also makes — run again
    directly, so this suite does not merely trust that the template's test
    file says what it claims to."""
    project = render(tmp_path, plugin_kind=kind)
    package_dir = project / "src" / "mycelium_test_thing"
    sys.path.insert(0, str(project / "src"))
    try:
        module = __import__("mycelium_test_thing", fromlist=["Plugin"])
        loaded = module.Plugin()
        assert isinstance(loaded, protocol)
        # `protocol` is a variable, so the narrowing lands on `object`; the
        # assertions below are about the instance this line just proved conforms.
        plugin: Any = loaded
        assert plugin.meta.id == "test-thing"
        assert plugin.meta.description
        assert plugin.meta.supports(0)
    finally:
        sys.path.remove(str(project / "src"))
        for name in list(sys.modules):
            if name == "mycelium_test_thing" or name.startswith("mycelium_test_thing."):
                del sys.modules[name]
    assert package_dir.is_dir()


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_rendered_plugins_own_tests_pass(tmp_path: Path, kind: str) -> None:
    """Not installed — `pip install -e .` would need a registry mycelium-os is not
    on yet (roadmap 6.11) — so `src/` is put on `PYTHONPATH` the way an editable
    install would put it on `sys.path`, and this repository's own venv already
    provides `mycelium` itself."""
    project = render(tmp_path, plugin_kind=kind)
    env = {**os.environ, "PYTHONPATH": str(project / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# The generated pyproject.toml wires the entry point the kind actually needs
# ---------------------------------------------------------------------------


def test_a_parser_registers_under_the_plugins_group(tmp_path: Path) -> None:
    project = render(tmp_path, plugin_kind="parser")
    text = (project / "pyproject.toml").read_text(encoding="utf-8")
    assert '[project.entry-points."mycelium.plugins"]' in text
    assert "mycelium.modules" not in text


def test_a_module_registers_under_the_modules_group(tmp_path: Path) -> None:
    project = render(tmp_path, plugin_kind="module")
    text = (project / "pyproject.toml").read_text(encoding="utf-8")
    assert '[project.entry-points."mycelium.modules"]' in text
    assert '"mycelium.plugins"' not in text
