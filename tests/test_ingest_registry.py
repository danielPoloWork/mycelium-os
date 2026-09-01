# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Plugin resolution (roadmap 4.1): the pinned list is the policy — its order decides
dispatch, every name in it must resolve, and nothing is ever chosen for being available."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mycelium.ingest import errors, registry
from mycelium.ingest.media import DOCX, HTML, MARKDOWN, PDF
from mycelium.ingest.registry import Registry, probe
from mycelium.sdk.protocols import MYCELIUM_API_VERSION, Blob, Parser, PluginMeta
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, Ulid

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"


class StubParser:
    """A parser in a dozen lines — the check that a plugin author can write one."""

    def __init__(self, plugin_id: str, media_types: tuple[str, ...], **meta: Any) -> None:
        self.meta = PluginMeta(id=plugin_id, version="0", description="stub", **meta)
        self.media_types = media_types

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        return KirDocument(
            doc_id=doc_id,
            source_digest=blob.digest,
            nodes=(
                KirNode(id="n1", kind=NodeKind.PARAGRAPH, ord=0, text=blob.data.decode("utf-8")),
            ),
            warnings=("stubbed",),
        )


@pytest.fixture
def roots(tmp_path: Path) -> Path:
    (tmp_path / "notes.md").write_bytes(b"# Notes\n")
    return tmp_path


def blob_of(data: bytes, media_type: str) -> Blob:
    return Blob.of(data, media_type=media_type, source_uri="file:///stub")


# ---------------------------------------------------------------------------
# The shape of the contract
# ---------------------------------------------------------------------------


def test_a_stub_satisfies_the_parser_protocol() -> None:
    assert isinstance(StubParser("stub", (MARKDOWN,)), Parser)


def test_every_built_in_parser_declares_a_distinct_id() -> None:
    ids = list(registry.BUILTIN_PARSERS)
    assert ids == ["markdown", "docling", "pandoc", "pdf"]
    assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_the_default_parser_set_resolves_with_no_optional_runtime(roots: Path) -> None:
    # `markdown` is the only parser with no engine to install, which is why it is
    # the shipped default: a fresh checkout resolves without asking for anything.
    resolved = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[roots])
    assert [parser.meta.id for parser in resolved.parsers] == ["markdown"]
    assert [connector.meta.id for connector in resolved.connectors] == ["file"]


def test_an_unknown_parser_names_the_built_ins(roots: Path) -> None:
    with pytest.raises(errors.UnknownPluginError, match="unknown parser 'nope'"):
        Registry.resolve(parsers=["nope"], connectors=["file"], roots=[roots])


def test_an_unknown_connector_is_refused(roots: Path) -> None:
    with pytest.raises(errors.UnknownPluginError, match="unknown connector 'http'"):
        Registry.resolve(parsers=["markdown"], connectors=["http"], roots=[roots])


def test_a_repeated_id_makes_the_order_ambiguous_and_is_refused(roots: Path) -> None:
    with pytest.raises(errors.PluginError, match="twice"):
        Registry.resolve(parsers=["markdown", "markdown"], connectors=["file"], roots=[roots])


def test_resolution_refuses_rather_than_falling_through(
    roots: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule that makes a build explainable (spec 05 §4.2).

    With `pandoc` pinned and unavailable, a registry that "did its best" would
    quietly hand DOCX to docling and produce a different corpus from CI's. It
    must refuse instead, and say what to install.
    """

    def unavailable() -> Parser:
        raise errors.PluginUnavailableError("install pandoc 3.x")

    monkeypatch.setattr(
        registry, "BUILTIN_PARSERS", {**registry.BUILTIN_PARSERS, "pandoc": unavailable}
    )
    with pytest.raises(errors.PluginUnavailableError, match="install pandoc"):
        Registry.resolve(parsers=["docling", "pandoc"], connectors=["file"], roots=[roots])


# ---------------------------------------------------------------------------
# Dispatch: the order is the policy
# ---------------------------------------------------------------------------


def test_the_first_parser_declaring_a_type_wins() -> None:
    first = StubParser("first", (DOCX,))
    second = StubParser("second", (DOCX,))
    assert Registry((first, second), ()).parser_for(DOCX) is first
    assert Registry((second, first), ()).parser_for(DOCX) is second


def test_a_type_no_pinned_parser_reads_names_the_pinned_list() -> None:
    pinned = Registry((StubParser("only", (MARKDOWN,)),), ())
    with pytest.raises(errors.UnsupportedMediaTypeError) as caught:
        pinned.parser_for(PDF)
    assert "only" in str(caught.value)
    assert PDF in str(caught.value)


def test_acquisition_warnings_are_folded_into_the_parsed_document() -> None:
    # No adapter can forget to carry them, because no adapter does it.
    pinned = Registry((StubParser("stub", (MARKDOWN,)),), ())
    blob = Blob.of(
        b"text", media_type=MARKDOWN, source_uri="file:///x", warnings=("custody problem",)
    )
    document = pinned.parse(blob, doc_id=DOC_ID)
    assert document.warnings == ("custody problem", "stubbed")


def test_a_warning_is_not_duplicated_when_the_parser_already_carried_it() -> None:
    pinned = Registry((StubParser("stub", (MARKDOWN,)),), ())
    blob = Blob.of(b"text", media_type=MARKDOWN, source_uri="file:///x", warnings=("stubbed",))
    assert pinned.parse(blob, doc_id=DOC_ID).warnings == ("stubbed",)


def test_describe_lists_every_resolved_plugin(roots: Path) -> None:
    resolved = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[roots])
    described = {status.id: status for status in resolved.describe()}
    assert set(described) == {"markdown", "file"}
    assert all(status.available for status in described.values())
    assert "markdown-it" in described["markdown"].detail or "engine" in described["markdown"].detail


# ---------------------------------------------------------------------------
# Third-party plugins take the same path
# ---------------------------------------------------------------------------


class FakeEntryPoint:
    def __init__(self, name: str, value: str, loaded: object) -> None:
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self) -> object:
        return self._loaded


@pytest.fixture
def entry_points(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[FakeEntryPoint]]:
    points: list[FakeEntryPoint] = []
    monkeypatch.setattr(registry, "entry_points", lambda group: list(points))
    yield points


def test_a_third_party_parser_resolves_through_the_entry_point_group(
    roots: Path, entry_points: list[FakeEntryPoint]
) -> None:
    entry_points.append(
        FakeEntryPoint("acme", "mycelium_acme:plugin", lambda: StubParser("acme", (HTML,)))
    )
    resolved = Registry.resolve(parsers=["acme"], connectors=["file"], roots=[roots])
    assert resolved.parser_for(HTML).meta.id == "acme"


def test_a_plugin_may_not_shadow_a_built_in_id(
    roots: Path, entry_points: list[FakeEntryPoint]
) -> None:
    entry_points.append(
        FakeEntryPoint("markdown", "evil:plugin", lambda: StubParser("markdown", (MARKDOWN,)))
    )
    with pytest.raises(errors.PluginError, match="built-in plugin"):
        Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[roots])


def test_two_plugins_claiming_one_id_is_ambiguous(
    roots: Path, entry_points: list[FakeEntryPoint]
) -> None:
    stub = lambda: StubParser("acme", (HTML,))  # noqa: E731
    entry_points.append(FakeEntryPoint("acme", "one:plugin", stub))
    entry_points.append(FakeEntryPoint("acme", "two:plugin", stub))
    with pytest.raises(errors.PluginError, match="more than one plugin"):
        Registry.resolve(parsers=["acme"], connectors=["file"], roots=[roots])


def test_a_plugin_that_is_not_a_parser_is_refused(
    roots: Path, entry_points: list[FakeEntryPoint]
) -> None:
    entry_points.append(FakeEntryPoint("acme", "acme:plugin", object()))
    with pytest.raises(errors.PluginError, match="does not satisfy the Parser protocol"):
        Registry.resolve(parsers=["acme"], connectors=["file"], roots=[roots])


def test_a_plugin_that_cannot_be_imported_is_reported_not_propagated(
    roots: Path, entry_points: list[FakeEntryPoint]
) -> None:
    class Exploding(FakeEntryPoint):
        def load(self) -> object:
            raise ModuleNotFoundError("no module named 'acme'")

    entry_points.append(Exploding("acme", "acme:plugin", None))
    with pytest.raises(errors.PluginUnavailableError, match="could not be loaded"):
        Registry.resolve(parsers=["acme"], connectors=["file"], roots=[roots])


def test_a_plugin_built_for_another_api_generation_is_refused(
    roots: Path, entry_points: list[FakeEntryPoint]
) -> None:
    future = StubParser(
        "acme",
        (HTML,),
        api_min=MYCELIUM_API_VERSION + 1,
        api_max=MYCELIUM_API_VERSION + 2,
    )
    entry_points.append(FakeEntryPoint("acme", "acme:plugin", lambda: future))
    with pytest.raises(errors.PluginError, match="plugin API"):
        Registry.resolve(parsers=["acme"], connectors=["file"], roots=[roots])


# ---------------------------------------------------------------------------
# probe: the same factories, reporting instead of refusing
# ---------------------------------------------------------------------------


def test_probe_reports_an_unknown_parser_rather_than_raising() -> None:
    (status,) = probe(["nope"])
    assert status.available is False
    assert "unknown parser" in status.detail


def test_probe_reports_the_built_in_that_always_works() -> None:
    (status,) = probe(["markdown"])
    assert status.available is True
    assert status.as_dict()["id"] == "markdown"
