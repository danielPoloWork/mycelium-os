"""{{ cookiecutter.plugin_id }} satisfies the Parser protocol (spec 05 §4.1)."""

from mycelium.sdk.identity import new_ulid
from mycelium.sdk.protocols import Blob, Parser
from mycelium.sdk.types import KirDocument

from {{ cookiecutter.package_name }} import Plugin


def test_plugin_satisfies_the_parser_protocol() -> None:
    assert isinstance(Plugin(), Parser)


def test_meta_carries_what_a_build_key_and_manifest_need() -> None:
    meta = Plugin.meta
    assert meta.id == "{{ cookiecutter.plugin_id }}"
    assert meta.version
    assert meta.description
    assert meta.supports(int("{{ cookiecutter.mycelium_api_min }}"))


def test_media_types_is_non_empty() -> None:
    """An empty tuple would make this plugin unreachable: the registry picks the
    first pinned parser whose `media_types` names the source's."""
    assert Plugin().media_types


def test_parse_returns_a_kir_document() -> None:
    blob = Blob.of(b"hello", media_type="text/plain", source_uri="file:///x")
    document = Plugin().parse(blob, doc_id=new_ulid())
    assert isinstance(document, KirDocument)
    assert document.source_digest == blob.digest
