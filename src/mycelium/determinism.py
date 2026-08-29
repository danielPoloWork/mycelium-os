# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The determinism observation used by gate G6 (spec 04 §7, D-008).

G6 is the compiler's byte-identical-rebuild check. Making it a *gate* rather than a
unit test needs two things the assertion alone does not give: a statement of what
"identical" covers, and an artifact a human can review when it legitimately changes.

**What is claimed.** The compiler's *outputs* are a pure function of its inputs:
artifact digests, counts, and every chunk and document record. Three manifest
fields are deliberately excluded because they are not outputs of compilation —
``snapshot_id`` is a fresh ULID by design, ``created_at`` is the wall clock, and
``timings_ms`` is a measurement of the machine. A gate that demanded those be
equal would be asserting something false and would have to be suppressed, which
is how gates become decoration.

**What counts as an input.** File mtime is one: it becomes ``created_at`` and
``updated_at`` on every document record (ADR-0009). A fresh checkout has fresh
mtimes, so the observation is taken against pinned timestamps — otherwise the
golden would encode the moment the repository was cloned rather than the content
it holds.

This module is shared by the gate and by the re-bless tool, so a golden file can
never be produced by different code than the code that checks it.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from mycelium.build import build
from mycelium.sdk.types import SnapshotManifest
from mycelium.store import SqliteStore

__all__ = [
    "PINNED_MTIME",
    "DeterminismObservation",
    "observe_build",
    "read_golden",
    "write_golden",
]

PINNED_MTIME: Final = 1_767_225_600.0
"""2026-01-01T00:00:00Z — a fixed mtime, so the observation records content, not checkout time."""

_VOLATILE_MANIFEST_FIELDS: Final = ("snapshot_id", "created_at", "timings_ms", "parent_id")
"""Manifest fields that legitimately differ between two correct builds."""


@dataclass(frozen=True, slots=True)
class DeterminismObservation:
    """Everything the gate compares, in a form a reviewer can read in a diff."""

    artifact_digests: dict[str, str]
    counts: dict[str, int]
    config_digest: str
    schema_versions: dict[str, str]
    warnings: tuple[str, ...]
    documents: tuple[dict[str, Any], ...]
    chunks: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_digests": self.artifact_digests,
            "counts": self.counts,
            "config_digest": self.config_digest,
            "schema_versions": self.schema_versions,
            "warnings": list(self.warnings),
            "documents": list(self.documents),
            "chunks": list(self.chunks),
        }


def pin_mtimes(root: Path, *, mtime: float = PINNED_MTIME) -> None:
    """Give every source file the same timestamp, so mtime stops being a variable."""
    for path in sorted(root.rglob("*.md")):
        os.utime(path, (mtime, mtime))


def observe_build(root: Path, *, pin: bool = True) -> DeterminismObservation:
    """Build `root` and record what determinism claims about the result."""
    if pin:
        pin_mtimes(root)
    result = build(root)
    return _observe(root, result.manifest)


def _observe(root: Path, manifest: SnapshotManifest) -> DeterminismObservation:
    with SqliteStore.open(root, read_only=True) as store:
        documents = []
        chunks = []
        for doc_id in store.document_ids():
            document = store.get_document(doc_id)
            if document is None:  # pragma: no cover - ids come from the store itself
                continue
            documents.append(
                {
                    "path": document.path,
                    "title": document.title,
                    "content_digest": document.content_digest,
                    "trust_class": document.trust_class.value,
                    "verification_status": document.verification_status.value,
                    "tags": list(document.tags),
                    "stats": document.stats.model_dump(),
                    # Recorded because `artifact_digests["documents"]` covers them:
                    # without these the golden could fail on a timestamp and show
                    # nothing but an unexplained digest mismatch.
                    "created_at": document.created_at.isoformat().replace("+00:00", "Z"),
                    "updated_at": document.updated_at.isoformat().replace("+00:00", "Z"),
                }
            )
            for chunk in store.chunks_of(doc_id):
                chunks.append(
                    {
                        "anchor": chunk.anchor,
                        "chunk_digest": chunk.chunk_digest,
                        "heading_path": list(chunk.heading_path),
                        "kind": chunk.kind.value,
                        "tokens": chunk.tokens,
                        "lines": list(chunk.lines),
                    }
                )

    return DeterminismObservation(
        artifact_digests=dict(manifest.artifact_digests),
        counts=manifest.counts.model_dump(),
        config_digest=manifest.config_digest,
        schema_versions=dict(manifest.schema_versions),
        warnings=manifest.warnings,
        documents=tuple(sorted(documents, key=lambda item: str(item["path"]))),
        chunks=tuple(sorted(chunks, key=lambda item: str(item["anchor"]))),
    )


def write_golden(path: Path, observation: DeterminismObservation) -> None:
    """Write a golden file: sorted keys, LF, trailing newline — reviewable in a diff."""
    text = json.dumps(observation.as_dict(), indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_golden(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
