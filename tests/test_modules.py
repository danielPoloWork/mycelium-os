# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Module discovery, activation, and configuration (roadmap 5.5, ADR-0077).

The core half of D-023's extension points: what the *engine* promises a module,
tested without reference to any particular module wherever that is possible. The
`chats` module is installed in this environment as a dev dependency, so it
doubles as the one real implementation — its own suite lives beside it in
`contrib/chats/tests/`.

The claims under test:

**Resolution is pinned** (spec 05 §4.2): a name nothing provides is a
`ConfigError` naming what to install, never a silent skip.

**A module may own its `[<id>]` section**, and the core carries it without
interpreting it — the API gap doc 08 §10's sixth gate authorised fixing.

**A module may not shadow the core's own sections**, because that would let an
installed package change what a query returns.

**Mounting is explicit and reports its failures.** Mounting at import time
created a cycle and swallowed the evidence; both are now impossible.
"""

from pathlib import Path

import pytest
import typer

from mycelium.config import ConfigError, MyceliumConfig, load_config
from mycelium.modules import (
    MODULE_ENTRY_POINT_GROUP,
    ModuleError,
    installed_ids,
    load_module,
    mount,
    require_enabled,
    statuses,
)
from mycelium.sdk.protocols import MYCELIUM_API_VERSION, Module, PluginMeta

INSTALLED = "chats"
"""The one module installed in this environment. Named once, so a second module
arriving does not scatter edits through this file."""


def write(root: Path, body: str) -> Path:
    (root / "mycelium.toml").write_text(body, encoding="utf-8", newline="\n")
    return root


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


class _Fake:
    """A module that satisfies the protocol without being installed."""

    meta = PluginMeta(id="fake", version="1", description="A test double.")

    def commands(self) -> typer.Typer:
        return typer.Typer(name="fake")


def test_the_protocol_is_satisfied_structurally() -> None:
    """A module needs a `meta` and a `commands()`, and nothing else."""
    assert isinstance(_Fake(), Module)
    assert not isinstance(object(), Module)


def test_the_protocol_requires_no_import_of_typer_to_satisfy() -> None:
    """`runtime_checkable` looks at attribute presence, so the annotation costs
    a module nothing (spec 05 §4.1.1 names Typer; the SDK only type-checks it)."""

    class Minimal:
        meta = PluginMeta(id="minimal", version="1", description="x")

        def commands(self) -> object:
            return None

    assert isinstance(Minimal(), Module)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_the_entry_point_group_is_the_module_group_not_the_plugin_one() -> None:
    """D-027's two levels get two groups: a parser is asked what it can read, a
    module is asked nothing until an operator names it."""
    from mycelium.ingest import ENTRY_POINT_GROUP as PLUGIN_GROUP

    assert MODULE_ENTRY_POINT_GROUP == "mycelium.modules"
    assert MODULE_ENTRY_POINT_GROUP != PLUGIN_GROUP


def test_the_installed_module_is_discovered_without_being_imported() -> None:
    """Reading metadata rather than importing is what lets configuration
    validate a name for free."""
    assert INSTALLED in installed_ids()
    assert installed_ids() == tuple(sorted(installed_ids()))


def test_loading_an_unknown_module_names_the_group_and_what_is_installed() -> None:
    with pytest.raises(ModuleError) as caught:
        load_module("nonesuch")
    message = str(caught.value)

    assert "nonesuch" in message
    assert MODULE_ENTRY_POINT_GROUP in message
    assert INSTALLED in message


def test_a_loaded_module_declares_its_api_generation() -> None:
    module = load_module(INSTALLED)

    assert module.meta.id == INSTALLED
    assert module.meta.supports(MYCELIUM_API_VERSION)
    assert isinstance(module, Module)


def test_statuses_report_rather_than_raise() -> None:
    """`doctor` needs a record that can carry a failure without being one."""
    reported = {status.id: status for status in statuses(enabled=(INSTALLED,))}

    assert reported[INSTALLED].available
    assert reported[INSTALLED].enabled
    assert not statuses(enabled=())[0].enabled
    assert "id" in reported[INSTALLED].as_dict()


# ---------------------------------------------------------------------------
# Activation through configuration
# ---------------------------------------------------------------------------


def test_a_module_is_off_until_the_configuration_names_it(tmp_path: Path) -> None:
    """Installing must not change what a repository contains (D-025)."""
    config = load_config(write(tmp_path, '[project]\nname = "x"\n'))
    assert config.modules.enabled == ()


def test_enabling_an_installed_module_is_accepted(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, f'[modules]\nenabled = ["{INSTALLED}"]\n'))
    assert config.modules.enabled == (INSTALLED,)


def test_enabling_an_uninstalled_module_is_refused_with_the_remedy(tmp_path: Path) -> None:
    """Pinned resolution (spec 05 §4.2): the error says a module is a package."""
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, '[modules]\nenabled = ["nonesuch"]\n'))
    message = str(caught.value)

    assert "nonesuch" in message
    assert "no installed module provides" in message
    assert "not a setting" in message


def test_enabling_one_module_twice_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="twice"):
        load_config(write(tmp_path, f'[modules]\nenabled = ["{INSTALLED}", "{INSTALLED}"]\n'))


def test_require_enabled_refuses_with_the_toml_to_paste() -> None:
    require_enabled(INSTALLED, (INSTALLED,))  # no raise
    with pytest.raises(ModuleError) as caught:
        require_enabled(INSTALLED, ())

    message = str(caught.value)
    assert "[modules]" in message
    assert f'enabled = ["{INSTALLED}"]' in message


# ---------------------------------------------------------------------------
# A module's own configuration section
# ---------------------------------------------------------------------------


def test_a_module_may_own_the_section_named_after_it(tmp_path: Path) -> None:
    """The API gap this item fixed: the loader refused every section spec 05 §2
    does not print, so a module could not have a setting at all (ADR-0077)."""
    config = load_config(
        write(
            tmp_path,
            f'[modules]\nenabled = ["{INSTALLED}"]\n\n[{INSTALLED}]\ntimezone = "UTC"\n',
        )
    )
    assert config.module_settings(INSTALLED) == {"timezone": "UTC"}


def test_the_core_does_not_interpret_a_modules_section(tmp_path: Path) -> None:
    """The core knows the table exists and nothing about what is in it — so an
    unknown key here is the *module's* error to raise, not the loader's."""
    config = load_config(
        write(tmp_path, f"[{INSTALLED}]\nsomething_the_core_never_heard_of = 41\n")
    )
    assert config.module_settings(INSTALLED) == {"something_the_core_never_heard_of": 41}


def test_a_section_for_an_uninstalled_module_is_still_an_unknown_section(tmp_path: Path) -> None:
    """Otherwise a typo would be silently accepted as somebody's module."""
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, "[nonesuch]\nkey = 1\n"))

    assert "nonesuch" in str(caught.value)
    assert "unknown section" in str(caught.value)


def test_an_unknown_section_still_lists_the_core_sections_and_the_modules(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, "[retreival]\nk = 10\n"))
    message = str(caught.value)

    assert "retrieval" in message  # the correct spelling is offered
    assert f"installed modules own: {INSTALLED}" in message


def test_module_settings_of_a_module_with_no_section_is_empty(tmp_path: Path) -> None:
    """A module must read an empty mapping as its defaults, like a missing file."""
    config = load_config(write(tmp_path, '[project]\nname = "x"\n'))
    assert config.module_settings(INSTALLED) == {}
    assert MyceliumConfig().module_settings(INSTALLED) == {}


def test_a_modules_section_participates_in_the_config_digest(tmp_path: Path) -> None:
    """A build recorded under a config that carried a module's settings must not
    silently match one that did not — the rule ADR-0014 set for every section."""
    plain = load_config(write(tmp_path, '[project]\nname = "x"\n'))
    configured = load_config(
        write(tmp_path, f'[project]\nname = "x"\n\n[{INSTALLED}]\ntimezone = "UTC"\n')
    )
    assert plain.digest() != configured.digest()


# ---------------------------------------------------------------------------
# Mounting (D-023 mechanism 3)
# ---------------------------------------------------------------------------


def test_mounting_adds_one_group_per_installed_module() -> None:
    app = typer.Typer()
    mounted, problems = mount(app)

    assert problems == ()
    assert INSTALLED in mounted
    assert {group.name for group in app.registered_groups} == set(installed_ids())


def test_mounting_twice_adds_nothing() -> None:
    """Idempotent, so a caller unsure whether `main()` already ran may call it."""
    app = typer.Typer()
    mount(app)
    again, problems = mount(app)

    assert again == ()
    assert problems == ()
    assert len(app.registered_groups) == len(installed_ids())


def test_the_cli_mounts_installed_modules_from_main_not_at_import() -> None:
    """The cycle this replaced: a module's CLI imports the core's output helpers,
    so mounting during `app.py`'s import re-entered a half-imported module and
    lost the command silently (roadmap 5.5)."""
    source = (Path(__file__).parent.parent / "src" / "mycelium" / "cli" / "app.py").read_text(
        encoding="utf-8"
    )
    body = source.split("def main() -> None:", 1)

    assert len(body) == 2
    assert "mount_modules(app)" in body[1], "main() mounts"
    assert "mount_modules(app)" not in body[0], "and nothing at import does"


def test_a_module_that_cannot_be_loaded_is_reported_rather_than_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Swallowing this is what turned an import cycle into a mystery."""
    import mycelium.modules as modules

    def broken(name: str) -> Module:
        msg = f"module {name!r} exploded on import"
        raise ModuleError(msg)

    monkeypatch.setattr(modules, "load_module", broken)
    app = typer.Typer()
    mounted, problems = modules.mount(app)

    assert mounted == ()
    assert len(problems) == len(installed_ids())
    assert "exploded on import" in problems[0]
    assert "installed but unusable" in problems[0]


def test_a_broken_module_does_not_stop_the_rest_of_the_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A third-party wheel must not make `mycelium build` unusable."""
    import mycelium.modules as modules

    monkeypatch.setattr(
        modules, "load_module", lambda name: (_ for _ in ()).throw(ModuleError("no"))
    )
    app = typer.Typer()

    @app.command()
    def core() -> None: ...

    mounted, problems = modules.mount(app)

    assert mounted == () and problems
    assert [command.callback.__name__ for command in app.registered_commands] == ["core"]
    assert app.registered_groups == []
