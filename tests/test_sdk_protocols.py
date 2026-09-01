# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The plugin contracts (roadmap 4.1): a blob carries custody, plugin identity is what a
manifest records, and the API generation is checked rather than hoped for."""

import pytest

from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import (
    MYCELIUM_API_VERSION,
    Blob,
    Connector,
    Parser,
    PluginMeta,
)
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, Ulid

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"


class MinimalParser:
    meta = PluginMeta(id="minimal", version="0", description="minimal")
    media_types = ("text/plain",)

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        return KirDocument(
            doc_id=doc_id,
            source_digest=blob.digest,
            nodes=(KirNode(id="n1", kind=NodeKind.PARAGRAPH, ord=0, text="x"),),
        )


class MinimalConnector:
    meta = PluginMeta(id="minimal", version="0", description="minimal")
    schemes = ("stub",)

    def acquire(self, source: str) -> Blob:
        return Blob.of(b"", media_type="text/plain", source_uri=source)


# ---------------------------------------------------------------------------
# Blob
# ---------------------------------------------------------------------------


def test_a_blob_digests_its_bytes_verbatim() -> None:
    data = b"\r\n mixed \xe2\x80\x94 endings \r\n"
    blob = Blob.of(data, media_type="text/plain", source_uri="file:///x")
    # Verbatim, not normalised: the CAS stores the acquired original, and a
    # citation into an ingested document must point at those exact bytes.
    assert blob.digest == digest_bytes(data)
    assert blob.size == len(data)


def test_a_blob_is_immutable() -> None:
    blob = Blob.of(b"x", media_type="text/plain", source_uri="file:///x")
    with pytest.raises(AttributeError):
        blob.media_type = "text/html"  # type: ignore[misc]


def test_acquisition_warnings_default_to_none_at_all() -> None:
    assert Blob.of(b"x", media_type="text/plain", source_uri="file:///x").warnings == ()


# ---------------------------------------------------------------------------
# PluginMeta
# ---------------------------------------------------------------------------


def test_a_plugin_defaults_to_supporting_this_api_generation() -> None:
    assert PluginMeta(id="p", version="1", description="d").supports(MYCELIUM_API_VERSION)


def test_a_plugin_can_declare_a_range_that_excludes_this_build() -> None:
    older = PluginMeta(id="p", version="1", description="d", api_min=0, api_max=0)
    newer = PluginMeta(
        id="p",
        version="1",
        description="d",
        api_min=MYCELIUM_API_VERSION + 1,
        api_max=MYCELIUM_API_VERSION + 2,
    )
    assert not older.supports(MYCELIUM_API_VERSION)
    assert not newer.supports(MYCELIUM_API_VERSION)


def test_a_plugin_is_deterministic_unless_it_says_otherwise() -> None:
    # The same declaration the embedder makes (ADR-0017): gate G6 excludes what
    # cannot promise reproducibility, so silence must mean the safe answer.
    assert PluginMeta(id="p", version="1", description="d").deterministic is True
    assert not PluginMeta(id="p", version="1", description="d", deterministic=False).deterministic


def test_plugin_identity_is_immutable() -> None:
    meta = PluginMeta(id="p", version="1", description="d")
    with pytest.raises(AttributeError):
        meta.version = "2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# The Protocols themselves
# ---------------------------------------------------------------------------


def test_a_minimal_class_satisfies_each_protocol() -> None:
    # The check that the contracts describe ingestion rather than describing the
    # engines that happened to arrive with them: both are satisfiable in a dozen
    # lines, which is what a plugin author has to be able to do.
    assert isinstance(MinimalParser(), Parser)
    assert isinstance(MinimalConnector(), Connector)


def test_something_without_the_members_is_not_a_parser() -> None:
    assert not isinstance(object(), Parser)
    assert not isinstance(MinimalConnector(), Parser)
