# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The JSONL interchange bundle — ``mycelium export`` (spec 03 §9, D-006).

D-006 fixes JSONL as the *interchange* format and nothing else: not the query
engine (that is SQLite, D-005), not the system of record (that is Git and the
Markdown, F-4), and not something committed by default. This module is the whole
of that surface — one directory per snapshot, one JSONL line per record, exactly
the records :mod:`mycelium.sdk.types` publishes.

Three properties make a bundle worth handing to another tool, and each of them is
a refusal rather than a feature:

**A bundle names one snapshot, and contains that snapshot.** Export refuses when
the store's own pointer and ``CURRENT`` disagree — the window ADR-0009 documented
and ``doctor`` reports — because a directory stamped ``<snapshot-id>`` holding
some other build's rows is precisely the quiet inconsistency this project spends
its effort avoiding everywhere else.

**Its bytes are a function of its snapshot.** Records are written in a declared
order, canonically serialised, LF-terminated. Exporting the same snapshot twice
produces byte-identical files, so a bundle can be digested, cached, diffed, and
compared across machines — the property gate G6 gives the compiler, applied to
its output format.

**``--with-markdown`` copies the sources that were compiled, or none at all.**
Each file's digest is checked against the ``content_digest`` its record carries;
drift fails the export and names the files. Shipping snapshot A's records beside
the working tree's B would make the bundle internally false, and the fix — one
``mycelium build`` — is cheaper than the confusion.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from mycelium.build.publish import manifest_path, read_current
from mycelium.sdk.identity import canonical_json, digest_text
from mycelium.sdk.types import Chunk, Document, Edge, Record
from mycelium.store import STORE_DIRNAME, SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

__all__ = [
    "DEFAULT_EXPORT_DIRNAME",
    "MANIFEST_FILENAME",
    "MARKDOWN_DIRNAME",
    "RECORDS_DIRNAME",
    "ExportError",
    "ExportResult",
    "export_bundle",
]

DEFAULT_EXPORT_DIRNAME: Final = "export"
"""Where bundles land under the repository root, per spec 03 §9's own tree.

``mycelium init`` gitignores it: D-006 says bundles are not committed by default,
and a directory the tool writes into the repository *is* committed by default
unless something says otherwise.
"""

RECORDS_DIRNAME: Final = "records"
MANIFEST_FILENAME: Final = "manifest.json"
MARKDOWN_DIRNAME: Final = "markdown"


class ExportError(RuntimeError):
    """The bundle cannot be written, and says exactly why."""


@dataclass(frozen=True, slots=True)
class ExportResult:
    """What one export wrote."""

    snapshot_id: str
    bundle: Path
    counts: dict[str, int]
    markdown_files: int

    def as_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "bundle": str(self.bundle),
            "records": dict(sorted(self.counts.items())),
            "markdown_files": self.markdown_files,
        }


def _write_records(path: Path, records: list[Record]) -> int:
    """Write one JSONL file: canonical JSON, one record per line, LF endings.

    ``model_dump(mode="json")`` first, so what lands on disk is the record's
    published JSON shape — aliases included, which is how ``Edge.from_`` becomes
    ``from`` — and ``canonical_json`` after, so key order and number spelling are
    fixed rather than incidental.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [canonical_json(record.model_dump(mode="json")) for record in records]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")
    return len(lines)


def _copy_markdown(root: Path, bundle: Path, documents: list[Document]) -> int:
    """Copy tier-2 sources into the bundle, or refuse if the tree has drifted.

    Every digest is recomputed from the file rather than trusted, because the
    case the check exists for is exactly the one where the file changed after the
    build that recorded it.
    """
    drifted: list[str] = []
    missing: list[str] = []
    planned: list[tuple[Path, Path]] = []

    for document in documents:
        source = root / Path(document.path)
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError:
            missing.append(document.path)
            continue
        if digest_text(raw) != document.content_digest:
            drifted.append(document.path)
            continue
        planned.append((source, bundle / MARKDOWN_DIRNAME / Path(document.path)))

    if missing or drifted:
        problems = []
        if drifted:
            problems.append(f"changed since the build: {', '.join(sorted(drifted)[:5])}")
        if missing:
            problems.append(f"no longer readable: {', '.join(sorted(missing)[:5])}")
        msg = (
            "refusing to export markdown that is not the snapshot's own source ("
            + "; ".join(problems)
            + "). Run `mycelium build` and export again, or drop --with-markdown."
        )
        raise ExportError(msg)

    for source, target in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return len(planned)


def _published(root: Path) -> tuple[str, Path]:
    """The snapshot this repository serves, and its manifest file."""
    mycelium_dir = root / STORE_DIRNAME
    snapshot_id = read_current(mycelium_dir)
    if snapshot_id is None:
        msg = f"no published snapshot at {root}; run `mycelium build` first"
        raise ExportError(msg)
    source = manifest_path(mycelium_dir, snapshot_id)
    if not source.is_file():
        msg = (
            f"CURRENT names {snapshot_id} but its manifest is missing; run `mycelium build` "
            "(or `mycelium doctor` to see what else is damaged)"
        )
        raise ExportError(msg)
    return snapshot_id, source


def _read_records(root: Path, snapshot_id: str) -> tuple[list[Document], list[Chunk], list[Edge]]:
    """Every record the bundle carries, in the order it will be written.

    Documents by path and chunks by anchor, matching how the snapshot manifest
    folds its own corpus digests (ADR-0015), so a reader comparing the two is
    comparing like with like. Edges come ordered from the store.
    """
    with SqliteStore.open(root, read_only=True) as store:
        pointer = store.get_meta(META_CURRENT_SNAPSHOT)
        if pointer != snapshot_id:
            # The ADR-0009 window. A bundle is a claim about one snapshot, so it
            # must not be assembled while the store and the pointer disagree
            # about which snapshot that is.
            msg = (
                f"the store is at {pointer} but CURRENT names {snapshot_id}: a build was "
                "interrupted between commit and publish, so this bundle would mix two "
                "snapshots. Run `mycelium build` to heal it first"
            )
            raise ExportError(msg)

        documents = sorted(
            (
                document
                for doc_id in store.document_ids()
                if (document := store.get_document(doc_id)) is not None
            ),
            key=lambda item: item.path,
        )
        chunks = sorted(
            (chunk for document in documents for chunk in store.chunks_of(document.doc_id)),
            key=lambda item: item.anchor,
        )
        edges = list(store.all_edges())
    return documents, chunks, edges


def export_bundle(
    root: Path, *, out: Path | None = None, with_markdown: bool = False
) -> ExportResult:
    """Write the published snapshot as a JSONL bundle (spec 03 §9).

    `out` defaults to ``<root>/export``; the bundle itself is always
    ``<out>/<snapshot-id>/``, so exporting two snapshots never has one overwrite
    the other, and exporting the same snapshot twice is idempotent.

    Raises :class:`ExportError` when nothing is published, when the store and
    ``CURRENT`` disagree about which snapshot that is, or when `with_markdown`
    meets sources that no longer match the records.
    """
    snapshot_id, source_manifest = _published(root)
    documents, chunks, edges = _read_records(root, snapshot_id)

    bundle = (out or root / DEFAULT_EXPORT_DIRNAME) / snapshot_id
    if bundle.exists():
        # A snapshot is immutable, so re-exporting one rewrites identical bytes —
        # but a stale `markdown/` from an earlier `--with-markdown` run would
        # survive alongside them and quietly misrepresent this export.
        shutil.rmtree(bundle)
    records = bundle / RECORDS_DIRNAME
    records.mkdir(parents=True, exist_ok=True)

    # Copied rather than re-serialised: the manifest is immutable and already
    # deterministic, and "verbatim" (spec 03 §9) is a stronger promise than
    # "re-emitted faithfully".
    shutil.copyfile(source_manifest, bundle / MANIFEST_FILENAME)

    counts = {
        "documents": _write_records(records / "documents.jsonl", list(documents)),
        "chunks": _write_records(records / "chunks.jsonl", list(chunks)),
        # The symbol stage arrives at roadmap 5.1. The file is written empty
        # rather than omitted, because `symbols` is part of the declared layout:
        # a consumer that must distinguish "absent because unsupported" from
        # "absent because empty" has been handed a puzzle instead of a bundle.
        "symbols": _write_records(records / "symbols.jsonl", []),
        "edges": _write_records(records / "edges.jsonl", list(edges)),
    }
    # `entities.jsonl` is "if present" in spec 03 §9, and entity extraction is
    # optional and off by default (5.4) — so its absence is the honest signal
    # that no entity stage ran, rather than an omission.

    markdown_files = _copy_markdown(root, bundle, documents) if with_markdown else 0
    return ExportResult(
        snapshot_id=snapshot_id,
        bundle=bundle,
        counts=counts,
        markdown_files=markdown_files,
    )
