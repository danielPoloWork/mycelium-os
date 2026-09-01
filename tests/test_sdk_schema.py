# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""JSON Schema export (roadmap 2.2): every record exports a self-describing
2020-12 schema with deterministic bytes, faithful aliases, and closed shapes."""

import json
from pathlib import Path

from mycelium.sdk.schema import (
    JSON_SCHEMA_DIALECT,
    RECORD_MODELS,
    dump_json_schema,
    export_json_schemas,
    record_json_schema,
    record_schema_version,
)
from mycelium.sdk.types import Document, Edge

EXPECTED_FILES = {
    "document.v0.schema.json",
    "kir.v0.schema.json",
    "chunk.v0.schema.json",
    "symbol.v0.schema.json",
    "edge.v0.schema.json",
    "entity.v0.schema.json",
    "manifest.v0.schema.json",
    "custody.v0.schema.json",
    "fidelity.v0.schema.json",
    "eval-case.v0.schema.json",
    "eval-run.v0.schema.json",
}


def test_export_writes_one_schema_per_record(tmp_path: Path) -> None:
    written = export_json_schemas(tmp_path / "schemas")
    assert {p.name for p in written} == EXPECTED_FILES
    assert all(p.exists() for p in written)


def test_every_schema_is_self_describing_2020_12(tmp_path: Path) -> None:
    for path in export_json_schemas(tmp_path):
        schema = json.loads(path.read_text(encoding="utf-8"))
        name = path.name.split(".")[0]
        assert schema["$schema"] == JSON_SCHEMA_DIALECT
        assert schema["$id"] == record_schema_version(RECORD_MODELS[name])
        # extra="forbid" must surface to non-Python consumers as a closed shape.
        assert schema["additionalProperties"] is False


def test_schema_version_tags_match_record_names() -> None:
    for name, model in RECORD_MODELS.items():
        version = record_schema_version(model)
        assert version == f"mycelium/{name}/v0"
        assert version.rsplit("/", 1)[-1] == "v0"


def test_document_schema_pins_required_contract_fields() -> None:
    schema = record_json_schema(Document)
    required = set(schema["required"])
    assert {
        "doc_id",
        "path",
        "title",
        "content_digest",
        "trust_class",
        "verification_status",
        "provenance",
        "stats",
        "created_at",
        "updated_at",
    } <= required
    # The controlled vocabularies export as named $defs with exact values.
    assert schema["$defs"]["TrustClass"]["enum"] == [
        "authored",
        "curated",
        "ingested",
        "external",
    ]


def test_edge_schema_uses_the_json_field_name() -> None:
    schema = record_json_schema(Edge)
    assert "from" in schema["properties"]
    assert "from_" not in schema["properties"]
    assert "from" in schema["required"]


def test_export_is_byte_deterministic(tmp_path: Path) -> None:
    first = export_json_schemas(tmp_path / "a")
    second = export_json_schemas(tmp_path / "b")
    for one, two in zip(first, second, strict=True):
        assert one.read_bytes() == two.read_bytes()


def test_dumped_bytes_are_lf_only_with_final_newline(tmp_path: Path) -> None:
    for path in export_json_schemas(tmp_path):
        data = path.read_bytes()
        assert b"\r" not in data  # byte-identity must hold across platforms (G6)
        assert data.endswith(b"\n")


def test_dump_matches_written_file(tmp_path: Path) -> None:
    (path,) = [p for p in export_json_schemas(tmp_path) if p.name.startswith("edge")]
    assert path.read_text(encoding="utf-8") == dump_json_schema(Edge)
