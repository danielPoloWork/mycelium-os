# {{ cookiecutter.project_name }}

{{ cookiecutter.description }}

A Mycelium OS {{ cookiecutter.plugin_kind }} plugin, generated from
[`mycelium-os`](https://github.com/danielPoloWork/mycelium-os)'s plugin cookiecutter. See the
[plugin-author guide](https://github.com/danielPoloWork/mycelium-os/blob/main/docs-site/plugin-author-guide.md)
for the contract this implements, and
[`docs/compatibility.md`](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/compatibility.md)
for what Mycelium OS promises not to change under it.

## Install

```bash
pip install -e .
```

Installing registers `{{ cookiecutter.plugin_id }}` in the
{%- if cookiecutter.plugin_kind == "module" %}
`mycelium.modules` entry-point group. Enable it in a repository's `mycelium.toml`:

```toml
[modules]
enabled = ["{{ cookiecutter.plugin_id }}"]
```
{%- else %}
`mycelium.plugins` entry-point group. Pin it in a repository's `mycelium.toml`:

```toml
[ingest]
{% if cookiecutter.plugin_kind == "parser" -%}
parsers = ["{{ cookiecutter.plugin_id }}"]
{%- else -%}
connectors = ["{{ cookiecutter.plugin_id }}"]
{%- endif %}
```
{%- endif %}

Nothing runs until it is named there — installing a plugin does not change what a repository
compiles until its configuration says so.

## Develop

```bash
pip install -e ".[dev]"  # or: uv sync
pytest
mypy --strict src
ruff check src tests
```

`tests/test_plugin.py` checks that `Plugin` satisfies its Protocol and that `Plugin.meta`
carries the fields every build key and manifest entry needs (spec 05 §4.2).

## What to replace

- `src/{{ cookiecutter.package_name }}/plugin.py` — the real implementation. The generated one
  is a minimal, correct skeleton, not a working {{ cookiecutter.plugin_kind }}.
- `Plugin.meta.version` — the *engine's* version this plugin adapts (a parser wraps a library;
  its version is that library's, not this package's own).
- This README's install/usage sections, once there is a real usage to describe.
