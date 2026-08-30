# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The JSONL interchange bundle (roadmap 3.6, spec 03 §9, D-006, ADR-0020).

A bundle is a claim made to another tool, so the tests are about whether the
claim can be trusted rather than whether files appear:

**It contains the snapshot it names** — refused outright when the store and
``CURRENT`` disagree about which snapshot that is.

**Its bytes are a function of that snapshot** — the same snapshot exported twice,
into different directories, is byte-identical. That is what lets a consumer
digest, cache, and diff a bundle.

**Every line is a record the SDK published** — round-tripped back through the
record models, not merely parsed as JSON, because "one JSONL line = one record"
(spec 03 §9) is the whole interchange contract.
"""

import json
import shutil
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.export import (
    DEFAULT_EXPORT_DIRNAME,
    MANIFEST_FILENAME,
    MARKDOWN_DIRNAME,
    RECORDS_DIRNAME,
    ExportError,
    export_bundle,
)
from mycelium.sdk.types import Chunk, Document, Edge, SnapshotManifest
from mycelium.store import SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

CORPUS = {
    "knowledge/architecture.md": (
        "---\ntitle: Architecture\ntags: [arch]\n---\n\n"
        "# Architecture\n\nThe bus routes messages. See [[api]].\n\n"
        "## Retries\n\nExponential backoff.\n"
    ),
    "knowledge/api.md": "# API\n\nEndpoints are versioned. Back to [[architecture]].\n",
    "knowledge/guide.md": "# Guide\n\nDay to day operation.\n",
}


def repo(tmp_path: Path, files: dict[str, str] | None = None, name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return root


def built(tmp_path: Path, name: str = "repo") -> Path:
    root = repo(tmp_path, name=name)
    build(root)
    return root


def read_jsonl(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


# ---------------------------------------------------------------------------
# The bundle's shape (spec 03 §9)
# ---------------------------------------------------------------------------


def test_the_bundle_has_the_layout_the_spec_draws(tmp_path: Path) -> None:
    root = built(tmp_path)

    result = export_bundle(root)

    assert result.bundle == root / DEFAULT_EXPORT_DIRNAME / result.snapshot_id
    assert (result.bundle / MANIFEST_FILENAME).is_file()
    records = result.bundle / RECORDS_DIRNAME
    assert sorted(item.name for item in records.iterdir()) == [
        "chunks.jsonl",
        "documents.jsonl",
        "edges.jsonl",
        "symbols.jsonl",
    ]
    # `entities.jsonl` is "if present", and no entity stage exists (roadmap 5.4),
    # so its absence is the signal rather than an omission.
    assert not (records / "entities.jsonl").exists()
    # `markdown/` only on request.
    assert not (result.bundle / MARKDOWN_DIRNAME).exists()


def test_the_manifest_is_copied_verbatim(tmp_path: Path) -> None:
    """A snapshot manifest is immutable; re-serialising it would be a weaker promise."""
    root = built(tmp_path)
    result = export_bundle(root)

    source = root / ".mycelium" / "snapshots" / f"{result.snapshot_id}.json"
    assert (result.bundle / MANIFEST_FILENAME).read_bytes() == source.read_bytes()
    # And it still validates as the record it claims to be.
    manifest = SnapshotManifest.model_validate_json(
        (result.bundle / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest.snapshot_id == result.snapshot_id


def test_every_line_round_trips_through_its_record_model(tmp_path: Path) -> None:
    """ "One JSONL line = one record" is the interchange contract, so parse it as one."""
    root = built(tmp_path)
    result = export_bundle(root)
    records = result.bundle / RECORDS_DIRNAME

    documents = [Document.model_validate(item) for item in read_jsonl(records / "documents.jsonl")]
    chunks = [Chunk.model_validate(item) for item in read_jsonl(records / "chunks.jsonl")]
    edges = [Edge.model_validate(item) for item in read_jsonl(records / "edges.jsonl")]

    assert len(documents) == result.counts["documents"] == 3
    assert chunks and len(chunks) == result.counts["chunks"]
    assert edges and len(edges) == result.counts["edges"]
    # The alias survives serialisation: `Edge.from_` is `from` on the wire.
    assert all("from" in item for item in read_jsonl(records / "edges.jsonl"))


def test_the_bundle_agrees_with_the_manifest_it_carries(tmp_path: Path) -> None:
    root = built(tmp_path)
    result = export_bundle(root)

    manifest = SnapshotManifest.model_validate_json(
        (result.bundle / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert result.counts["documents"] == manifest.counts.documents
    assert result.counts["chunks"] == manifest.counts.chunks
    assert result.counts["edges"] == manifest.counts.edges


def test_records_are_written_in_a_declared_order(tmp_path: Path) -> None:
    """Documents by path and chunks by anchor — the order the manifest folds by."""
    root = built(tmp_path)
    records = export_bundle(root).bundle / RECORDS_DIRNAME

    paths = [str(item["path"]) for item in read_jsonl(records / "documents.jsonl")]
    anchors = [str(item["anchor"]) for item in read_jsonl(records / "chunks.jsonl")]
    assert paths == sorted(paths)
    assert anchors == sorted(anchors)


# ---------------------------------------------------------------------------
# Determinism: the bytes are a function of the snapshot
# ---------------------------------------------------------------------------


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        item.relative_to(root).as_posix(): item.read_bytes()
        for item in sorted(root.rglob("*"))
        if item.is_file()
    }


def test_exporting_the_same_snapshot_twice_is_byte_identical(tmp_path: Path) -> None:
    root = built(tmp_path)

    first = export_bundle(root, out=tmp_path / "one")
    second = export_bundle(root, out=tmp_path / "two")

    assert first.snapshot_id == second.snapshot_id
    assert tree_bytes(first.bundle) == tree_bytes(second.bundle)


def test_the_same_sources_export_the_same_records_elsewhere(tmp_path: Path) -> None:
    """The compiler is deterministic (G6); the bundle must not undo that.

    The sources are copied *after* the first build, so the pinned `mycelium_id`s
    and the file mtimes travel with them — the two inputs that are deliberately
    not content (ADR-0009, ADR-0012). What remains is the compiler's output, and
    the bundle must reproduce it byte for byte in a different directory.

    Snapshot ids and manifests legitimately differ, carrying a fresh ULID and a
    wall clock, so this compares the record files alone.
    """
    here = built(tmp_path, name="here")
    there = tmp_path / "there"
    for source in sorted(here.rglob("*.md")):
        if ".mycelium" in source.parts:
            continue
        target = there / source.relative_to(here)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)  # copy2: mtime is an input
    build(there)

    one = export_bundle(here, out=tmp_path / "a").bundle / RECORDS_DIRNAME
    two = export_bundle(there, out=tmp_path / "b").bundle / RECORDS_DIRNAME

    assert tree_bytes(one) == tree_bytes(two)


def test_lines_are_lf_terminated_and_canonical(tmp_path: Path) -> None:
    """Byte-stability needs both: platform newlines and key order would break it."""
    root = built(tmp_path)
    records = export_bundle(root).bundle / RECORDS_DIRNAME

    raw = (records / "documents.jsonl").read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    for line in raw.decode("utf-8").splitlines():
        parsed = json.loads(line)
        assert line == json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_an_empty_stage_writes_an_empty_file_not_a_missing_one(tmp_path: Path) -> None:
    root = built(tmp_path)
    records = export_bundle(root).bundle / RECORDS_DIRNAME
    symbols = records / "symbols.jsonl"

    assert symbols.is_file()
    assert symbols.read_bytes() == b""


def test_re_exporting_clears_a_stale_markdown_tree(tmp_path: Path) -> None:
    """A snapshot is immutable, so its records rewrite identically — but a
    `markdown/` left by an earlier run would survive and misrepresent this one."""
    root = built(tmp_path)
    first = export_bundle(root, with_markdown=True)
    assert (first.bundle / MARKDOWN_DIRNAME).is_dir()

    second = export_bundle(root)

    assert second.bundle == first.bundle
    assert not (second.bundle / MARKDOWN_DIRNAME).exists()


# ---------------------------------------------------------------------------
# --with-markdown: the sources that were compiled, or none at all
# ---------------------------------------------------------------------------


def test_with_markdown_copies_the_compiled_sources(tmp_path: Path) -> None:
    root = built(tmp_path)

    result = export_bundle(root, with_markdown=True)

    markdown = result.bundle / MARKDOWN_DIRNAME
    assert result.markdown_files == 3
    copied = sorted(item.relative_to(markdown).as_posix() for item in markdown.rglob("*.md"))
    assert copied == sorted(CORPUS)
    # Verbatim, including the `mycelium_id` the build pinned into the source.
    original = (root / "knowledge/api.md").read_bytes()
    assert (markdown / "knowledge/api.md").read_bytes() == original


def test_with_markdown_refuses_sources_that_drifted_from_the_snapshot(tmp_path: Path) -> None:
    """Records from snapshot A beside the working tree's B is a bundle that lies."""
    root = built(tmp_path)
    target = root / "knowledge/guide.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nEdited after the build.\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(ExportError) as caught:
        export_bundle(root, with_markdown=True)

    message = str(caught.value)
    assert "knowledge/guide.md" in message
    assert "mycelium build" in message  # names the fix
    assert "--with-markdown" in message  # and the alternative


def test_with_markdown_refuses_when_a_source_is_gone(tmp_path: Path) -> None:
    root = built(tmp_path)
    (root / "knowledge/guide.md").unlink()

    with pytest.raises(ExportError, match="knowledge/guide.md"):
        export_bundle(root, with_markdown=True)


def test_drift_does_not_stop_a_records_only_export(tmp_path: Path) -> None:
    """The records come from the snapshot, so the working tree cannot spoil them."""
    root = built(tmp_path)
    (root / "knowledge/guide.md").unlink()

    result = export_bundle(root)

    assert result.counts["documents"] == 3  # the snapshot still holds three


# ---------------------------------------------------------------------------
# A bundle names one snapshot, and contains that snapshot
# ---------------------------------------------------------------------------


def test_export_before_any_build_says_what_to_run(tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="mycelium build"):
        export_bundle(repo(tmp_path))


def test_export_refuses_the_commit_to_swap_window(tmp_path: Path) -> None:
    """ADR-0009's window: a bundle assembled here would mix two snapshots."""
    root = built(tmp_path)
    with SqliteStore.open(root) as store, store.transaction():
        store.set_meta(META_CURRENT_SNAPSHOT, "01ARZ3NDEKTSV4RRFFQ69G5FAV")

    with pytest.raises(ExportError) as caught:
        export_bundle(root)

    assert "interrupted between commit and publish" in str(caught.value)
    assert "mycelium build" in str(caught.value)


def test_export_refuses_when_the_manifest_is_missing(tmp_path: Path) -> None:
    root = built(tmp_path)
    snapshot = (root / ".mycelium" / "CURRENT").read_text(encoding="utf-8").strip()
    (root / ".mycelium" / "snapshots" / f"{snapshot}.json").unlink()

    with pytest.raises(ExportError, match="manifest is missing"):
        export_bundle(root)


def test_two_snapshots_land_side_by_side(tmp_path: Path) -> None:
    """The bundle directory is keyed by snapshot, so exports never collide."""
    root = built(tmp_path)
    first = export_bundle(root)

    (root / "knowledge/extra.md").write_text("# Extra\n\nMore.\n", encoding="utf-8", newline="\n")
    build(root)
    second = export_bundle(root)

    assert first.bundle != second.bundle
    assert first.bundle.is_dir() and second.bundle.is_dir()
    assert second.counts["documents"] == first.counts["documents"] + 1
