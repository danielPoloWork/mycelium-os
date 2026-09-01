# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""JSON Schema 2020-12 export of the v0 record contracts (spec 03 intro).

Records export as self-contained JSON Schema documents so non-Python consumers
get machine-readable contracts without Mycelium OS becoming polyglot (D-003).
The build orchestrator (roadmap 2.7) writes them into ``schemas/`` at build
time; this module owns the generation.

Output bytes are deterministic — sorted keys, two-space indent, LF line
endings, trailing newline — the same doctrine the build artifacts obey (G6):
two exports of the same contracts are byte-identical on every platform.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from mycelium.sdk.types import (
    Chunk,
    CustodyRecord,
    Document,
    Edge,
    Entity,
    EvalCase,
    EvalRunManifest,
    KirDocument,
    Record,
    SnapshotManifest,
    Symbol,
)

__all__ = [
    "JSON_SCHEMA_DIALECT",
    "RECORD_MODELS",
    "SNAPSHOT_ARTIFACT_CLASSES",
    "dump_json_schema",
    "export_json_schemas",
    "record_json_schema",
    "record_schema_version",
]

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

RECORD_MODELS: Mapping[str, type[Record]] = {
    "document": Document,
    "kir": KirDocument,
    "chunk": Chunk,
    "symbol": Symbol,
    "edge": Edge,
    "entity": Entity,
    "manifest": SnapshotManifest,
    "custody": CustodyRecord,
    "eval-case": EvalCase,
    "eval-run": EvalRunManifest,
}
"""Exported record models, keyed by the names the snapshot manifest's
``schema_versions`` map uses (spec 03 §7)."""


SNAPSHOT_ARTIFACT_CLASSES: Final = ("document", "chunk", "kir", "edge")
"""The artifact classes a snapshot manifest reports versions for (spec 03 §7).

Narrower than :data:`RECORD_MODELS` on purpose: a manifest describes what *this
snapshot published*, not every contract the project exports. `symbol` and `entity`
join it when their stages exist (roadmap 5.1, 5.4); evaluation records never do —
an eval run is not a snapshot artifact, and neither is a custody record, which
outlives every snapshot that ever referenced it (ADR-0033).
"""


def record_schema_version(model: type[Record]) -> str:
    """Return a record model's pinned version tag, e.g. ``mycelium/document/v0``."""
    default = model.model_fields["schema_version"].default
    if not isinstance(default, str):  # pragma: no cover - every record pins a Literal
        msg = f"{model.__name__} does not pin a schema_version default"
        raise TypeError(msg)
    return default


def record_json_schema(model: type[Record]) -> dict[str, Any]:
    """Build the self-describing JSON Schema 2020-12 document for one record.

    ``$schema`` states the dialect; ``$id`` is the record's ``schema_version``
    tag, so the identifier consumers see in schema files is the same string
    every record instance carries (D-016).
    """
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": record_schema_version(model),
        **model.model_json_schema(),
    }


def dump_json_schema(model: type[Record]) -> str:
    """Serialize one record schema deterministically (sorted keys, LF, final newline)."""
    document = record_json_schema(model)
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_json_schemas(dest: Path) -> list[Path]:
    """Write every record schema into ``dest`` as ``<name>.<version>.schema.json``.

    Creates ``dest`` if needed and returns the written paths in export order.
    """
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in RECORD_MODELS.items():
        version = record_schema_version(model).rsplit("/", 1)[-1]
        path = dest / f"{name}.{version}.schema.json"
        path.write_text(dump_json_schema(model), encoding="utf-8", newline="\n")
        written.append(path)
    return written
