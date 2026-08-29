# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Build orchestrator v0 (roadmap 2.7): one writer at a time, identity pinned once,
per-document failures quarantined, and a publish that is atomic — an interrupted build
leaves ``CURRENT`` and the store exactly as they were."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.__about__ import __version__
from mycelium.build import (
    BuildLock,
    BuildLockedError,
    build,
    read_current,
    read_manifest,
)
from mycelium.build.lock import LOCK_FILENAME
from mycelium.build.publish import atomic_write_text, swap_current, write_manifest
from mycelium.markdown import parse_frontmatter
from mycelium.sdk.types import (
    SnapshotCounts,
    SnapshotManifest,
    Toolchain,
    VerificationStatus,
)
from mycelium.store import SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

DOC = """---
title: Architecture
tags: [arch]
---

# Architecture

The event bus routes messages. See [[api]] and [docs](https://example.invalid).

## Retries

Exponential backoff.
"""


def repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return tmp_path


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*.md"))
        if ".mycelium" not in path.parts
    }


# ---------------------------------------------------------------------------
# The single-writer lock (spec 02 §7)
# ---------------------------------------------------------------------------


def test_lock_acquire_writes_holder_identity_and_release_removes(tmp_path: Path) -> None:
    with BuildLock.acquire(tmp_path) as lock:
        holder = lock.read_holder()
        assert holder is not None
        assert holder.pid == os.getpid()
        assert holder.host
        assert (tmp_path / LOCK_FILENAME).exists()
    assert not (tmp_path / LOCK_FILENAME).exists()


def test_a_live_lock_refuses_a_second_writer(tmp_path: Path) -> None:
    with BuildLock.acquire(tmp_path), pytest.raises(BuildLockedError, match=f"pid {os.getpid()}"):
        BuildLock.acquire(tmp_path)


def test_a_stale_lock_is_taken_over(tmp_path: Path) -> None:
    abandoned = BuildLock.acquire(tmp_path)  # never released: a dead build
    ancient = datetime.now(tz=UTC).timestamp() - 3600
    os.utime(abandoned.path, (ancient, ancient))
    with BuildLock.acquire(tmp_path, stale_after_s=600) as taken:
        assert taken.read_holder() is not None
    assert not (tmp_path / LOCK_FILENAME).exists()


def test_a_recent_heartbeat_prevents_takeover(tmp_path: Path) -> None:
    with BuildLock.acquire(tmp_path) as lock:
        lock.heartbeat()
        with pytest.raises(BuildLockedError, match="heartbeat"):
            BuildLock.acquire(tmp_path, stale_after_s=600)


def test_heartbeat_refreshes_mtime_and_requires_ownership(tmp_path: Path) -> None:
    with BuildLock.acquire(tmp_path) as lock:
        old = datetime.now(tz=UTC).timestamp() - 120
        os.utime(lock.path, (old, old))
        lock.heartbeat()
        assert lock.path.stat().st_mtime > old + 60
    stranger = BuildLock(tmp_path / LOCK_FILENAME)
    with pytest.raises(BuildLockedError, match="does not hold"):
        stranger.heartbeat()


def test_unreadable_lock_content_still_yields_to_mtime(tmp_path: Path) -> None:
    lock_file = tmp_path / LOCK_FILENAME
    tmp_path.mkdir(exist_ok=True)
    lock_file.write_text("not json at all")
    ancient = datetime.now(tz=UTC).timestamp() - 3600
    os.utime(lock_file, (ancient, ancient))
    with BuildLock.acquire(tmp_path, stale_after_s=600):
        pass  # takeover by staleness; the garbage content only loses diagnostics


def test_release_is_idempotent(tmp_path: Path) -> None:
    lock = BuildLock.acquire(tmp_path)
    lock.release()
    lock.release()


# ---------------------------------------------------------------------------
# Publication mechanics
# ---------------------------------------------------------------------------


def test_atomic_write_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "CURRENT"
    atomic_write_text(target, "01J1ZC8Q4R6XKQ3F0V9T8B2M7N\n")
    assert target.read_text(encoding="utf-8").strip() == "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
    assert list(tmp_path.glob("*.tmp")) == []


def test_current_round_trip_and_absence(tmp_path: Path) -> None:
    assert read_current(tmp_path) is None
    swap_current(tmp_path, "01J1ZC8Q4R6XKQ3F0V9T8B2M7N")
    assert read_current(tmp_path) == "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"


def _manifest(snapshot_id: str) -> SnapshotManifest:
    return SnapshotManifest(
        snapshot_id=snapshot_id,
        created_at=datetime(2026, 8, 30, 10, 0, tzinfo=UTC),
        config_digest="sha256:" + "11ab" * 16,
        toolchain=Toolchain(mycelium=__version__, python="3.12.0"),
        schema_versions={"document": "v0"},
        counts=SnapshotCounts(documents=1, chunks=1, symbols=0, edges=0, vectors=0, quarantined=0),
        artifact_digests={"documents": "sha256:" + "6f2a" * 16},
        timings_ms={"total": 1},
    )


def test_manifests_are_immutable_and_deterministic(tmp_path: Path) -> None:
    manifest = _manifest("01J1ZC8Q4R6XKQ3F0V9T8B2M7N")
    first = write_manifest(tmp_path, manifest)
    with pytest.raises(FileExistsError, match="immutable"):
        write_manifest(tmp_path, manifest)
    other = write_manifest(tmp_path, _manifest("01J1ZF8Q4R6XKQ3F0V9T8B2M7N"))
    # Same fields (modulo id) serialize to the same bytes: sorted keys, LF, final newline.
    assert first.read_bytes().replace(b"01J1ZC8Q4R6XKQ3F0V9T8B2M7N", b"X") == (
        other.read_bytes().replace(b"01J1ZF8Q4R6XKQ3F0V9T8B2M7N", b"X")
    )
    assert b"\r" not in first.read_bytes()
    assert read_manifest(tmp_path, manifest.snapshot_id) == manifest


# ---------------------------------------------------------------------------
# The build, end to end
# ---------------------------------------------------------------------------


def test_build_compiles_publishes_and_is_queryable(tmp_path: Path) -> None:
    root = repo(tmp_path, {"knowledge/verified/architecture.md": DOC})
    result = build(root)
    manifest = result.manifest

    assert manifest.counts.documents == 1
    assert manifest.counts.chunks >= 2
    assert manifest.counts.quarantined == 0
    assert manifest.parent_id is None
    assert manifest.embedding is None
    assert manifest.toolchain.mycelium == __version__
    assert set(manifest.artifact_digests) == {"documents", "chunks", "edges"}
    assert manifest.schema_versions["document"] == "v0"
    assert len(manifest.schema_versions) == 7

    mycelium_dir = root / ".mycelium"
    assert read_current(mycelium_dir) == manifest.snapshot_id
    assert read_manifest(mycelium_dir, manifest.snapshot_id) == manifest
    assert not (mycelium_dir / LOCK_FILENAME).exists()  # released

    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_meta(META_CURRENT_SNAPSHOT) == manifest.snapshot_id
        (hit,) = store.search_chunks("exponential backoff")
        assert hit.title == "Architecture"
        document = store.get_document_by_path("knowledge/verified/architecture.md")
        assert document is not None
        assert document.stats.headings == 2
        assert document.stats.links_out == 2  # one wikilink + one markdown link
        assert document.tags == ("arch",)


def test_verification_status_is_folder_derived(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/verified/a.md": "# A\n\ntext\n",
            "knowledge/candidate/b.md": "# B\n\ntext\n",
            "knowledge/evidence/c.md": "# C\n\ntext\n",
            "knowledge/notes.md": "# N\n\ntext\n",  # outside the scheme: authored default
        },
    )
    build(root)
    with SqliteStore.open(root, read_only=True) as store:
        statuses = {
            path: store.get_document_by_path(path).verification_status  # type: ignore[union-attr]
            for path in (
                "knowledge/verified/a.md",
                "knowledge/candidate/b.md",
                "knowledge/evidence/c.md",
                "knowledge/notes.md",
            )
        }
    assert statuses == {
        "knowledge/verified/a.md": VerificationStatus.VERIFIED,
        "knowledge/candidate/b.md": VerificationStatus.CANDIDATE,
        "knowledge/evidence/c.md": VerificationStatus.EVIDENCE,
        "knowledge/notes.md": VerificationStatus.VERIFIED,
    }


def test_discovery_without_knowledge_scans_root_but_never_dot_dirs(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "README.md": "# Readme\n\ntext\n",
            "docs/guide.md": "# Guide\n\ntext\n",
            ".hidden/skipped.md": "# Skipped\n\ntext\n",
        },
    )
    manifest = build(root).manifest
    assert manifest.counts.documents == 2
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_document_by_path(".hidden/skipped.md") is None


def test_empty_repository_still_publishes(tmp_path: Path) -> None:
    manifest = build(tmp_path).manifest
    assert manifest.counts.documents == 0
    assert read_current(tmp_path / ".mycelium") == manifest.snapshot_id


# ---------------------------------------------------------------------------
# Identity pinning: the build's only tier-2 write
# ---------------------------------------------------------------------------


def test_pinning_inserts_into_existing_frontmatter(tmp_path: Path) -> None:
    root = repo(tmp_path, {"knowledge/a.md": "---\ntitle: A\n---\n\n# A\n\ntext\n"})
    result = build(root)
    assert [p.name for p in result.pinned] == ["a.md"]
    text = (root / "knowledge/a.md").read_text(encoding="utf-8")
    assert text.splitlines()[1].startswith("mycelium_id: ")
    assert "title: A" in text  # the rest of the block is untouched
    parsed = parse_frontmatter(text)
    assert parsed.frontmatter.mycelium_id is not None
    assert parsed.frontmatter.title == "A"


def test_pinning_creates_a_block_when_none_exists(tmp_path: Path) -> None:
    root = repo(tmp_path, {"knowledge/a.md": "# Bare\n\ntext\n"})
    build(root)
    text = (root / "knowledge/a.md").read_text(encoding="utf-8")
    parsed = parse_frontmatter(text)
    assert parsed.frontmatter.mycelium_id is not None
    assert "# Bare" in parsed.body


def test_pinning_preserves_crlf_and_bom(tmp_path: Path) -> None:
    crlf = tmp_path / "knowledge" / "crlf.md"
    crlf.parent.mkdir(parents=True)
    crlf.write_bytes(b"---\r\ntitle: X\r\n---\r\n\r\n# X\r\n\r\ntext\r\n")
    bom = tmp_path / "knowledge" / "bom.md"
    bom.write_bytes(b"\xef\xbb\xbf# Bom\n\ntext\n")

    build(tmp_path)

    crlf_bytes = crlf.read_bytes()
    assert b"\r\nmycelium_id: " in crlf_bytes or crlf_bytes.splitlines()[1].startswith(
        b"mycelium_id: "
    )
    assert crlf_bytes.count(b"\r\n") >= 6  # still a CRLF file
    assert bom.read_bytes().startswith(b"\xef\xbb\xbf---")  # BOM kept, block after it


def test_second_build_pins_nothing_and_changes_no_bytes(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/verified/a.md": DOC,
            "knowledge/b.md": "# Bare\n\ntext\n",
        },
    )
    first = build(root)
    assert len(first.pinned) == 2
    snapshot = tree_bytes(root)
    second = build(root)
    assert second.pinned == ()
    assert tree_bytes(root) == snapshot
    # The determinism seed for gate G6 (wired into CI at 2.10):
    assert second.manifest.artifact_digests == first.manifest.artifact_digests
    assert second.manifest.counts == first.manifest.counts
    assert second.manifest.parent_id == first.manifest.snapshot_id


def test_duplicate_pinned_ids_quarantine_the_second_document(tmp_path: Path) -> None:
    doc_id = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
    root = repo(
        tmp_path,
        {
            "knowledge/a.md": f"---\nmycelium_id: {doc_id}\n---\n# A\n",
            "knowledge/b.md": f"---\nmycelium_id: {doc_id}\n---\n# B\n",
        },
    )
    manifest = build(root).manifest
    assert manifest.counts.documents == 1
    assert manifest.counts.quarantined == 1
    (warning,) = manifest.warnings
    assert "duplicate mycelium_id" in warning
    assert "knowledge/b.md" in warning
    assert "knowledge/a.md" in warning


# ---------------------------------------------------------------------------
# Failure taxonomy: quarantine per document, never a torn publish
# ---------------------------------------------------------------------------


def test_an_unreadable_document_is_quarantined_not_fatal(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/good.md": "# Good\n\ntext\n",
            "knowledge/bad.md": '---\ntitle: "unterminated\n---\nbody\n',
        },
    )
    manifest = build(root).manifest
    assert manifest.counts.documents == 1
    assert manifest.counts.quarantined == 1
    assert any("quarantined: knowledge/bad.md" in warning for warning in manifest.warnings)


def test_an_interrupted_build_leaves_current_and_store_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path, {"knowledge/a.md": "# A\n\noriginal text\n"})
    first = build(root)

    (root / "knowledge" / "b.md").write_text("# B\n\nnew text\n", encoding="utf-8")
    import mycelium.build.orchestrator as orchestrator_module

    def explode(*args: object, **kwargs: object) -> object:
        msg = "disk full"
        raise OSError(msg)

    with monkeypatch.context() as patched:
        patched.setattr(orchestrator_module, "write_manifest", explode)
        with pytest.raises(OSError, match="disk full"):
            build(root)

    mycelium_dir = root / ".mycelium"
    assert read_current(mycelium_dir) == first.manifest.snapshot_id
    assert not (mycelium_dir / LOCK_FILENAME).exists()  # the lock is not leaked
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_meta(META_CURRENT_SNAPSHOT) == first.manifest.snapshot_id
        assert store.counts()["documents"] == 1  # the transaction rolled back whole
        assert store.search_chunks("new") == ()

    # And the failure is recoverable: the next build simply succeeds.
    healed = build(root)
    assert healed.manifest.counts.documents == 2
    assert read_current(mycelium_dir) == healed.manifest.snapshot_id


def test_build_refuses_to_run_while_another_writer_is_live(tmp_path: Path) -> None:
    repo(tmp_path, {"knowledge/a.md": "# A\n\ntext\n"})
    with BuildLock.acquire(tmp_path / ".mycelium"), pytest.raises(BuildLockedError):
        build(tmp_path)


def test_journal_records_the_build_lifecycle(tmp_path: Path) -> None:
    root = repo(tmp_path, {"knowledge/a.md": "# A\n\ntext\n"})
    result = build(root)
    lines = [
        json.loads(line)
        for line in (root / ".mycelium" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    events = [line["event"] for line in lines]
    assert events == ["build.started", "build.published"]
    published = lines[-1]
    assert published["snapshot_id"] == result.manifest.snapshot_id
    assert published["documents"] == 1
