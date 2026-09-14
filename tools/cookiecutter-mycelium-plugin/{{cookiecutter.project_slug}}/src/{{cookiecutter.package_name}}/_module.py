"""A Module plugin: a packaged activatable capability (D-025), not an engine
extension (spec 05 §4.3).

A module contributes surfaces; the core's job is to discover it, refuse it
clearly when it cannot be resolved, and mount what it offers — it is never
called inside a pipeline the way a Parser or Connector is. It is resolved
through the `mycelium.modules` entry-point group (distinct from
`mycelium.plugins`) and does nothing in a repository until an operator names it
in `[modules] enabled`.

One contribution is required — a CLI sub-app mounted at
`mycelium {{ cookiecutter.plugin_id }} …` — because a module built on no
consumer's needs is a guess (the same refusal `mycelium.modules` makes for the
extension mechanisms nothing here has used yet: pipeline stages, lifecycle
hooks, MCP tools). Add `stages()`, `hooks()` or `tools()` as optional methods
only when something in this plugin actually needs one.

A module needs more than the plugin API — the SDK, plus configuration,
activation, ingestion's custody doctrine, the token estimate, the CLI's output
conventions (`mycelium.modules.MODULE_SURFACE`). Import only from a component
that constant names; everything else in the core is private to a module,
whatever its spelling, and `docs/compatibility.md` says which of that surface is
frozen and which is still free to move.
"""

import typer
from mycelium.sdk.protocols import PluginMeta

app = typer.Typer(help="{{ cookiecutter.description }}")


@app.command()
def status() -> None:
    """A first command — replace it with what {{ cookiecutter.project_name }} does."""
    typer.echo("{{ cookiecutter.plugin_id }} is installed")


class Plugin:
    """{{ cookiecutter.description }}"""

    meta = PluginMeta(
        id="{{ cookiecutter.plugin_id }}",
        version="{{ cookiecutter.version }}",
        description="{{ cookiecutter.description }}",
        api_min=int("{{ cookiecutter.mycelium_api_min }}"),
        api_max=int("{{ cookiecutter.mycelium_api_max }}"),
    )

    def commands(self) -> typer.Typer:
        """The sub-app mounted at `mycelium {{ cookiecutter.plugin_id }} …`.

        Every command in it is responsible for refusing to act on a repository
        that has not enabled this module — see
        `mycelium.modules.require_enabled`.
        """
        return app
