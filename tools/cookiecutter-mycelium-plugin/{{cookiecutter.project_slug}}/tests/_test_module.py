"""{{ cookiecutter.plugin_id }} satisfies the Module protocol (spec 05 §4.3)."""

import typer.testing
from mycelium.sdk.protocols import Module

from {{ cookiecutter.package_name }} import Plugin


def test_plugin_satisfies_the_module_protocol() -> None:
    assert isinstance(Plugin(), Module)


def test_meta_carries_what_a_build_key_and_manifest_need() -> None:
    meta = Plugin.meta
    assert meta.id == "{{ cookiecutter.plugin_id }}"
    assert meta.version
    assert meta.description
    assert meta.supports(int("{{ cookiecutter.mycelium_api_min }}"))


def test_commands_mounts_a_typer_app() -> None:
    # Typer collapses a single-command app to run directly, with no subcommand
    # name — add a second `@app.command()` in `plugin.py` and this call needs
    # `["status"]` again to reach it by name.
    runner = typer.testing.CliRunner()
    result = runner.invoke(Plugin().commands(), [])
    assert result.exit_code == 0
    assert "{{ cookiecutter.plugin_id }}" in result.stdout
