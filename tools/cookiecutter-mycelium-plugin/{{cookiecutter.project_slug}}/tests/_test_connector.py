"""{{ cookiecutter.plugin_id }} satisfies the Connector protocol (spec 05 §4.1)."""

from mycelium.sdk.protocols import Connector

from {{ cookiecutter.package_name }} import Plugin


def test_plugin_satisfies_the_connector_protocol() -> None:
    assert isinstance(Plugin(), Connector)


def test_meta_carries_what_a_build_key_and_manifest_need() -> None:
    meta = Plugin.meta
    assert meta.id == "{{ cookiecutter.plugin_id }}"
    assert meta.version
    assert meta.description
    assert meta.supports(int("{{ cookiecutter.mycelium_api_min }}"))


def test_schemes_is_non_empty() -> None:
    """An empty tuple would make this plugin unreachable: resolution picks the
    first pinned connector whose `schemes` names the source URI's scheme."""
    assert Plugin().schemes
