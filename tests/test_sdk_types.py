# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Record contracts v0 (roadmap 2.2): the spec's own examples validate, the
controlled vocabularies are exact, and every record round-trips JSON losslessly."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mycelium.sdk.types import (
    Chunk,
    ChunkKind,
    Document,
    Edge,
    EdgeStatus,
    EdgeType,
    Entity,
    KirDocument,
    KirNode,
    NodeKind,
    ProvenanceOrigin,
    SnapshotManifest,
    SourceTrust,
    Symbol,
    TrustClass,
    VerificationStatus,
)

# Spec examples truncate digests/ULIDs with an ellipsis; the contracts require
# full-length values, so the fixtures below expand them.
ULID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
ULID_2 = "01J1ZF8Q4R6XKQ3F0V9T8B2M7N"
DIGEST = "sha256:" + "6f2a" * 16
DIGEST_2 = "sha256:" + "9c41" * 16

# spec 03 §3 — the document record example, verbatim shape.
SPEC_DOCUMENT = {
    "schema_version": "mycelium/document/v0",
    "doc_id": ULID,
    "path": "knowledge/architecture.md",
    "title": "Architecture",
    "namespace": "default",
    "collection": "core-docs",
    "tags": ["architecture", "event-bus"],
    "content_digest": DIGEST,
    "trust_class": "authored",
    "curated": False,
    "verification_status": "verified",
    "verification": None,
    "provenance": {
        "origin": "authored",
        "source_uri": None,
        "source_digest": None,
        "source_trust": None,
        "connector": None,
        "connector_version": None,
        "synthesizer": None,
        "ingested_at": None,
    },
    "fidelity_report": None,
    "secret_flags": [],
    "stats": {"tokens": 4180, "headings": 12, "chunks": 9, "links_out": 14},
    "created_at": "2026-07-31T10:00:00Z",
    "updated_at": "2026-07-31T10:00:00Z",
}

# spec 03 §4 — the KIR example: heading, paragraph, and the opaque escape hatch.
SPEC_KIR = {
    "schema_version": "mycelium/kir/v0",
    "doc_id": ULID,
    "source_digest": DIGEST_2,
    "nodes": [
        {
            "id": "n1",
            "kind": "heading",
            "level": 2,
            "text": "Event Bus",
            "parent": None,
            "ord": 4,
            "src": {"page": 3, "bbox": [72, 140, 520, 160]},
        },
        {"id": "n2", "kind": "paragraph", "text": "…", "parent": "n1", "ord": 5},
        {
            "id": "n3",
            "kind": "opaque",
            "media_type": "application/x-drawing",
            "blob": "sha256:" + "aa10" * 16,
            "parent": "n1",
            "ord": 6,
            "note": "vector drawing not representable; preserved as blob",
        },
    ],
    "warnings": ["table on page 7 has merged cells; represented row-major"],
}

# spec 03 §5 — the chunk record example.
SPEC_CHUNK = {
    "schema_version": "mycelium/chunk/v0",
    "anchor": "architecture.md#event-bus/0",
    "doc_id": ULID,
    "chunk_digest": "sha256:" + "b7e3" * 16,
    "heading_path": ["Architecture", "Event Bus"],
    "kir_nodes": ["n1", "n2"],
    "text": "…verbatim normalized text…",
    "tokens": 412,
    "lines": [88, 141],
    "kind": "prose",
    "namespace": "default",
}

# spec 03 §6 — symbol and edge examples.
SPEC_SYMBOL = {
    "schema_version": "mycelium/symbol/v0",
    "symbol": "sym:python:mycelium.compiler.BuildKey",
    "kind": "class",
    "defined_in": "src/mycelium/compiler.py#L84",
    "doc_refs": ["architecture.md#build-keys/0"],
    "namespace": "default",
}
SPEC_EDGE = {
    "schema_version": "mycelium/edge/v0",
    "from": "doc:architecture.md",
    "to": "doc:agents.md",
    "type": "links_to",
    "status": "authored",
    "provenance": {"kind": "markdown_link", "anchor": "architecture.md#event-bus/1"},
    "weight": 1.0,
    "namespace": "default",
}

# spec 03 §7 — the snapshot manifest example.
SPEC_MANIFEST = {
    "schema_version": "mycelium/manifest/v0",
    "snapshot_id": ULID_2,
    "parent_id": ULID,
    "created_at": "2026-07-31T10:04:12Z",
    "config_digest": "sha256:" + "11ab" * 16,
    "toolchain": {"mycelium": "0.1.0", "python": "3.12.4"},
    "schema_versions": {"document": "v0", "chunk": "v0", "kir": "v0", "edge": "v0"},
    "embedding": {
        "model_id": "bge-small-en-v1.5",
        "dim": 384,
        "deterministic": False,
        "provider": "local-onnx",
    },
    "counts": {
        "documents": 412,
        "chunks": 3877,
        "symbols": 951,
        "edges": 2210,
        "vectors": 3877,
        "quarantined": 1,
    },
    "artifact_digests": {"documents": DIGEST, "chunks": DIGEST_2, "edges": DIGEST},
    "degraded": [],
    "warnings": ["1 document quarantined: sources/legacy.pdf (parser_crash)"],
    "timings_ms": {"total": 8412, "parse": 3100, "embed": 4100, "index": 900},
}


# ---------------------------------------------------------------------------
# The spec's own examples validate and round-trip losslessly.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (Document, SPEC_DOCUMENT),
        (KirDocument, SPEC_KIR),
        (Chunk, SPEC_CHUNK),
        (Symbol, SPEC_SYMBOL),
        (Edge, SPEC_EDGE),
        (SnapshotManifest, SPEC_MANIFEST),
    ],
    ids=["document", "kir", "chunk", "symbol", "edge", "manifest"],
)
def test_spec_examples_validate_and_round_trip(model: type, payload: dict) -> None:
    record = model.model_validate(payload)
    assert model.model_validate_json(record.model_dump_json()) == record


def test_document_semantics() -> None:
    doc = Document.model_validate(SPEC_DOCUMENT)
    assert doc.trust_class is TrustClass.AUTHORED
    assert doc.verification_status is VerificationStatus.VERIFIED
    assert doc.provenance.origin is ProvenanceOrigin.AUTHORED
    assert doc.created_at == datetime(2026, 7, 31, 10, 0, tzinfo=UTC)
    # JSON serialization keeps the spec's Z-suffixed RFC 3339 form.
    assert json.loads(doc.model_dump_json())["created_at"] == "2026-07-31T10:00:00Z"


def test_entity_record_carries_conventions() -> None:
    entity = Entity(
        entity_id=ULID,
        slug="event-bus",
        name="Event Bus",
        aliases=("bus",),
        kind="component",
        status=EdgeStatus.EXTRACTED,
        doc_refs=("architecture.md#event-bus/0",),
    )
    dumped = json.loads(entity.model_dump_json())
    assert dumped["schema_version"] == "mycelium/entity/v0"
    assert dumped["namespace"] == "default"


# ---------------------------------------------------------------------------
# Controlled vocabularies are exact (spec 03 §§3-6).
# ---------------------------------------------------------------------------


def test_vocabularies_are_exact() -> None:
    assert {t.value for t in TrustClass} == {"authored", "curated", "ingested", "external"}
    assert {v.value for v in VerificationStatus} == {"verified", "candidate", "evidence"}
    assert {s.value for s in SourceTrust} == {"high", "medium", "low", "unknown"}
    assert {o.value for o in ProvenanceOrigin} == {"authored", "ingested", "synthesized"}
    assert {k.value for k in ChunkKind} == {"prose", "table", "code"}
    assert {s.value for s in EdgeStatus} == {"authored", "extracted"}
    # D-014: exactly eight edge types; extending the vocabulary requires an RFC.
    assert {e.value for e in EdgeType} == {
        "links_to",
        "defines",
        "references",
        "part_of",
        "supersedes",
        "derived_from",
        "cites",
        "mentions",
    }
    # spec 03 §4: the twenty KIR node kinds.
    assert {k.value for k in NodeKind} == {
        "document",
        "section",
        "heading",
        "paragraph",
        "list",
        "list_item",
        "table",
        "table_row",
        "table_cell",
        "code_block",
        "equation",
        "image",
        "link",
        "wikilink",
        "embed",
        "callout",
        "tag_ref",
        "footnote",
        "quote",
        "opaque",
    }


# ---------------------------------------------------------------------------
# KIR per-kind field legality (spec 03 §4; ADR-0006)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "heading", "level": 2, "text": "H"},
        {"kind": "code_block", "lang": "python", "text": "x = 1"},
        {"kind": "list", "variant": "ordered"},
        {"kind": "table_row", "variant": "header"},
        {"kind": "callout", "variant": "note", "title": "Careful"},
        {"kind": "link", "target": "https://x", "title": "T", "text": "label"},
        {"kind": "image", "target": "pic.png", "text": "alt"},
        {"kind": "wikilink", "target": "api#Retries", "text": "the retry docs"},
        {"kind": "embed", "target": "diagram"},
        {"kind": "opaque", "media_type": "application/x-drawing", "note": "preserved"},
        {"kind": "paragraph", "text": "plain"},
    ],
)
def test_kir_nodes_accept_the_fields_their_kind_declares(fields: dict) -> None:
    KirNode.model_validate({"id": "n1", "ord": 0, **fields})


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"kind": "paragraph", "level": 2}, "level"),
        ({"kind": "paragraph", "target": "x"}, "target"),
        ({"kind": "heading", "level": 1, "lang": "python"}, "lang"),
        ({"kind": "code_block", "target": "x"}, "target"),
        ({"kind": "wikilink", "target": "a", "title": "t"}, "title"),
        ({"kind": "list", "media_type": "text/plain"}, "media_type"),
        ({"kind": "table", "variant": "header"}, "variant"),
    ],
)
def test_kir_nodes_reject_fields_their_kind_does_not_declare(fields: dict, expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        KirNode.model_validate({"id": "n1", "ord": 0, **fields})


def test_heading_requires_a_level() -> None:
    with pytest.raises(ValidationError, match="requires a level"):
        KirNode.model_validate({"id": "n1", "ord": 0, "kind": "heading", "text": "H"})


def test_src_locator_line_span_must_be_ordered() -> None:
    node = KirNode.model_validate(
        {"id": "n1", "ord": 0, "kind": "paragraph", "src": {"lines": [3, 9]}}
    )
    assert node.src is not None and node.src.lines == (3, 9)
    with pytest.raises(ValidationError, match="lines start"):
        KirNode.model_validate(
            {"id": "n1", "ord": 0, "kind": "paragraph", "src": {"lines": [9, 3]}}
        )


# ---------------------------------------------------------------------------
# Contract enforcement: immutability, closed shape, identity formats, time.
# ---------------------------------------------------------------------------


def test_records_are_frozen() -> None:
    doc = Document.model_validate(SPEC_DOCUMENT)
    with pytest.raises(ValidationError):
        doc.title = "Renamed"  # type: ignore[misc]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="surprise"):
        Chunk.model_validate({**SPEC_CHUNK, "surprise": 1})


@pytest.mark.parametrize(
    "mutation",
    [
        {"doc_id": "not-a-ulid"},
        {"doc_id": ULID.lower()},  # Crockford base32 is uppercase
        {"content_digest": "sha256:abc123"},  # truncated digest
        {"content_digest": "md5:" + "0" * 64},
        {"trust_class": "banana"},
        {"created_at": "2026-07-31T10:00:00"},  # naive timestamp
    ],
)
def test_document_field_contracts_reject(mutation: dict) -> None:
    with pytest.raises(ValidationError):
        Document.model_validate({**SPEC_DOCUMENT, **mutation})


def test_aware_non_utc_timestamps_normalize_to_utc() -> None:
    doc = Document.model_validate({**SPEC_DOCUMENT, "created_at": "2026-07-31T12:00:00+02:00"})
    assert doc.created_at == datetime(2026, 7, 31, 10, 0, tzinfo=UTC)
    assert doc.created_at.tzinfo is UTC
    assert json.loads(doc.model_dump_json())["created_at"] == "2026-07-31T10:00:00Z"


def test_aware_datetime_objects_also_normalize() -> None:
    cet = timezone(timedelta(hours=2))
    doc = Document.model_validate(
        {**SPEC_DOCUMENT, "created_at": datetime(2026, 7, 31, 12, 0, tzinfo=cet)}
    )
    assert doc.created_at == datetime(2026, 7, 31, 10, 0, tzinfo=UTC)


def test_chunk_anchor_shape_is_validated() -> None:
    for bad in ("no-separator/0", "doc.md#section", "doc.md#section/01", "doc.md#a#b/0"):
        with pytest.raises(ValidationError):
            Chunk.model_validate({**SPEC_CHUNK, "anchor": bad})


def test_chunk_line_span_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="lines start"):
        Chunk.model_validate({**SPEC_CHUNK, "lines": [141, 88]})


def test_edge_validates_and_serializes_by_alias() -> None:
    by_alias = Edge.model_validate(SPEC_EDGE)
    by_name = Edge(
        from_="doc:architecture.md",
        to="doc:agents.md",
        type=EdgeType.LINKS_TO,
        status=EdgeStatus.AUTHORED,
        provenance=by_alias.provenance,
    )
    assert by_alias == by_name
    assert json.loads(by_alias.model_dump_json())["from"] == "doc:architecture.md"
    assert by_alias.model_dump()["from"] == "doc:architecture.md"


def test_edge_weight_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        Edge.model_validate({**SPEC_EDGE, "weight": -0.1})


def test_manifest_without_vectors_is_representable() -> None:
    degraded = SnapshotManifest.model_validate(
        {**SPEC_MANIFEST, "embedding": None, "degraded": ["vectors"]}
    )
    assert degraded.embedding is None
    assert degraded.degraded == ("vectors",)


# ---------------------------------------------------------------------------
# Property: chunk records survive a JSON round-trip for arbitrary content.
# ---------------------------------------------------------------------------


@given(
    text=st.text(max_size=200),
    tokens=st.integers(min_value=0, max_value=100_000),
    start=st.integers(min_value=0, max_value=5_000),
    span=st.integers(min_value=0, max_value=500),
    kind=st.sampled_from(list(ChunkKind)),
    heading_path=st.lists(st.text(min_size=1, max_size=20), max_size=4),
)
def test_chunk_json_round_trip_property(
    text: str, tokens: int, start: int, span: int, kind: ChunkKind, heading_path: list[str]
) -> None:
    chunk = Chunk(
        anchor="architecture.md#event-bus/0",
        doc_id=ULID,
        chunk_digest=DIGEST,
        heading_path=tuple(heading_path),
        kir_nodes=("n1",),
        text=text,
        tokens=tokens,
        lines=(start, start + span),
        kind=kind,
    )
    assert Chunk.model_validate_json(chunk.model_dump_json()) == chunk
