# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Snapshot lifecycle: list, rollback, garbage collection (roadmap 3.2, ADR-0016).

The claim under test is that a snapshot is a *restorable* thing, not a name: after
``rollback``, the store serves exactly the corpus the target snapshot's manifest
describes — same documents, same chunks, same search results — without recompiling,
and the next incremental build reasons from the restored state rather than from the
build that was rolled back.

Garbage collection is tested from the other side: what it keeps must stay usable
(every retained snapshot still rolls back afterwards), and what it drops must be
genuinely unreachable.
"""

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.build.cas import CAS_DIRNAME, cas_get, cas_path, cas_put
from mycelium.build.lock import BuildLock, BuildLockedError
from mycelium.build.publish import SNAPSHOTS_DIRNAME, manifest_path, read_current, read_manifest
from mycelium.build.snapshots import (
    SnapshotError,
    collect_garbage,
    decode_snapshot_state,
    encode_snapshot_state,
    list_snapshots,
    rollback,
)
from mycelium.cli.doctor import diagnose, worst_status
from mycelium.sdk.identity import digest_json
from mycelium.store import DocState, SnapshotState, SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

_IDS = {
    "architecture": "01ARZ3NDEKTSV4RRFFQ69G5FB1",
    "api": "01ARZ3NDEKTSV4RRFFQ69G5FB2",
    "guide": "01ARZ3NDEKTSV4RRFFQ69G5FB3",
}

CORPUS = {
    "knowledge/architecture.md": (
        f"---\nmycelium_id: {_IDS['architecture']}\n---\n\n"
        "# Architecture\n\nThe event bus routes messages between agents.\n"
    ),
    "knowledge/api.md": (
        f"---\nmycelium_id: {_IDS['api']}\n---\n\n# API\n\nEndpoints are versioned.\n"
    ),
    "knowledge/guide.md": (
        f"---\nmycelium_id: {_IDS['guide']}\n---\n\n# Guide\n\nDay to day operation.\n"
    ),
}


def repo(tmp_path: Path, files: dict[str, str] | None = None, name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return root


def edit(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def corpus_of(root: Path) -> dict[str, tuple[str, ...]]:
    """What the store currently serves: each document's path -> its chunk anchors."""
    with SqliteStore.open(root, read_only=True) as store:
        return {
            document.path: tuple(chunk.anchor for chunk in store.chunks_of(doc_id))
            for doc_id in store.document_ids()
            if (document := store.get_document(doc_id)) is not None
        }


def journal_events(root: Path) -> list[dict[str, object]]:
    lines = (root / ".mycelium" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def blob_count(root: Path) -> int:
    cas = root / ".mycelium" / CAS_DIRNAME
    return sum(1 for path in cas.rglob("*") if path.is_file()) if cas.is_dir() else 0


# ---------------------------------------------------------------------------
# mycelium snapshots
# ---------------------------------------------------------------------------


def test_listing_is_newest_first_and_marks_current(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root).manifest
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nMore prose.\n")
    second = build(root).manifest

    listed = list_snapshots(root)
    assert [item.snapshot_id for item in listed] == [second.snapshot_id, first.snapshot_id]
    assert [item.is_current for item in listed] == [True, False]
    assert listed[0].parent_id == first.snapshot_id
    assert listed[1].parent_id is None
    assert all(item.restorable for item in listed)
    assert listed[0].documents == 3


def test_listing_an_unbuilt_repository_is_empty_not_an_error(tmp_path: Path) -> None:
    assert list_snapshots(repo(tmp_path)) == ()


def test_a_damaged_manifest_does_not_hide_the_others(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root).manifest
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nMore.\n")
    second = build(root).manifest
    manifest_path(root / ".mycelium", first.snapshot_id).write_text("{ truncated", encoding="utf-8")

    listed = list_snapshots(root)
    assert [item.snapshot_id for item in listed] == [second.snapshot_id]


# ---------------------------------------------------------------------------
# mycelium rollback
# ---------------------------------------------------------------------------


def test_rollback_restores_the_corpus_without_recompiling(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root).manifest
    before = corpus_of(root)

    edit(root, "knowledge/guide.md", f"---\nmycelium_id: {_IDS['guide']}\n---\n\n# Guide\n\nV2.\n")
    (root / "knowledge/api.md").unlink()
    edit(root, "knowledge/new.md", "# New\n\nAdded after the first snapshot.\n")
    second = build(root).manifest
    assert corpus_of(root) != before

    result = rollback(root, first.snapshot_id)

    assert result.snapshot_id == first.snapshot_id
    assert result.previous_id == second.snapshot_id
    assert result.documents == 3
    assert corpus_of(root) == before
    assert read_current(root / ".mycelium") == first.snapshot_id
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_meta(META_CURRENT_SNAPSHOT) == first.snapshot_id
        assert store.counts()["chunks"] == first.counts.chunks
        # The restored corpus is searchable, not merely present: the lexical
        # index was rebuilt with the rows. One distinctive term per side —
        # FTS terms are OR-joined (BUG-0005), so a whole phrase would match
        # any surviving document that shares a common word with it.
        assert store.search_chunks("bus")
        assert not store.search_chunks("Added")


def test_rollback_makes_the_store_reproduce_the_manifest_it_names(tmp_path: Path) -> None:
    """The strongest form of the claim: rebuild the *manifest* from the restored
    store and require the published artifact digests, byte for byte."""
    root = repo(tmp_path)
    target = build(root).manifest
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)

    rollback(root, target.snapshot_id)

    with SqliteStore.open(root, read_only=True) as store:
        states = store.doc_states()

    assert (
        digest_json([state.document_digest for state in states])
        == (target.artifact_digests["documents"])
    )
    assert (
        digest_json([state.chunks_digest for state in states])
        == (target.artifact_digests["chunks"])
    )


def test_the_build_after_a_rollback_is_incremental_from_the_restored_state(
    tmp_path: Path,
) -> None:
    """Rollback restores `doc_state`, so the next build diffs against what is
    actually in the store — recompiling the documents that drifted and no others."""
    root = repo(tmp_path)
    first = build(root).manifest
    edit(root, "knowledge/guide.md", f"---\nmycelium_id: {_IDS['guide']}\n---\n\n# Guide\n\nV2.\n")
    build(root)

    rollback(root, first.snapshot_id)

    result = build(root)  # guide.md on disk is still V2; the store holds V1
    assert result.stats.rebuilt == 1
    assert result.stats.reused == 2
    assert result.stats.parse_hits == 1  # V2 was parsed before: the cache still has it
    assert result.manifest.parent_id == first.snapshot_id  # lineage records the rollback


def test_rolling_back_to_current_is_a_lawful_repair(tmp_path: Path) -> None:
    """Restoring what is already served is a no-op for readers — and the repair
    for a store whose rows were damaged while its pointer stayed valid."""
    root = repo(tmp_path)
    manifest = build(root).manifest
    before = corpus_of(root)

    with SqliteStore.open(root) as store, store.transaction():
        store.delete_document(_IDS["api"])
    assert corpus_of(root) != before

    rollback(root, manifest.snapshot_id)
    assert corpus_of(root) == before


def test_rollback_refuses_an_unknown_snapshot(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    with pytest.raises(SnapshotError, match="unknown snapshot"):
        rollback(root, "01ARZ3NDEKTSV4RRFFQ69G5FZZ")


def test_rollback_refuses_when_an_artifact_is_missing(tmp_path: Path) -> None:
    """A collected or hand-deleted artifact must produce a named refusal, never a
    partial restore."""
    root = repo(tmp_path)
    first = build(root).manifest
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        state = store.get_snapshot_state(first.snapshot_id)
    assert state is not None
    blob = cas_get(root / ".mycelium", state.state_blob)
    assert blob is not None
    victim = next(item for item in decode_snapshot_state(blob) if item.path.endswith("api.md"))
    cas_path(root / ".mycelium", victim.document_digest).unlink()

    served = corpus_of(root)
    with pytest.raises(SnapshotError, match="api.md"):
        rollback(root, first.snapshot_id)
    # Refused before anything was touched: the store still serves what it did.
    assert corpus_of(root) == served


def test_rollback_refuses_state_that_does_not_reproduce_its_manifest(tmp_path: Path) -> None:
    """The integrity gate: recorded state is trusted only when it folds back to
    the digests the manifest published."""
    root = repo(tmp_path)
    manifest = build(root).manifest
    with SqliteStore.open(root, read_only=True) as store:
        state = store.get_snapshot_state(manifest.snapshot_id)
        states = store.doc_states()
    assert state is not None

    # Forge a state blob that drops a document, and point the snapshot at it.
    forged = cas_put(root / ".mycelium", encode_snapshot_state(states[:-1]))
    with SqliteStore.open(root) as store, store.transaction():
        store.put_snapshot_state(
            SnapshotState(
                snapshot_id=manifest.snapshot_id,
                state_blob=forged,
                created_at=state.created_at,
            )
        )

    with pytest.raises(SnapshotError, match="does not reproduce its manifest"):
        rollback(root, manifest.snapshot_id)


def test_rollback_is_journaled(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root).manifest
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)
    rollback(root, first.snapshot_id)

    published = [item for item in journal_events(root) if item["event"] == "rollback.published"]
    assert published and published[-1]["snapshot_id"] == first.snapshot_id


# ---------------------------------------------------------------------------
# The snapshot Memento
# ---------------------------------------------------------------------------


def test_snapshot_state_round_trips_and_is_stable(tmp_path: Path) -> None:
    states = (
        DocState(
            doc_id=_IDS["api"],
            path="knowledge/api.md",
            source_digest="sha256:aa",
            source_mtime="2026-01-01T00:00:00+00:00",
            env_digest="sha256:bb",
            document_digest="sha256:cc",
            chunks_digest="sha256:dd",
            warnings=("careful",),
        ),
    )
    text = encode_snapshot_state(states)
    assert decode_snapshot_state(text) == states
    assert encode_snapshot_state(decode_snapshot_state(text)) == text


def test_an_unchanged_corpus_re_addresses_the_same_state_blob(tmp_path: Path) -> None:
    """Content addressing means a no-op build writes no new state — the property
    that keeps snapshot history cheap when a watch loop rebuilds often."""
    root = repo(tmp_path)
    first = build(root).manifest
    blobs = blob_count(root)
    second = build(root).manifest

    with SqliteStore.open(root, read_only=True) as store:
        one = store.get_snapshot_state(first.snapshot_id)
        two = store.get_snapshot_state(second.snapshot_id)
    assert one is not None and two is not None
    assert one.state_blob == two.state_blob
    assert blob_count(root) == blobs


def test_a_cleared_cache_publishes_a_snapshot_that_says_it_is_not_restorable(
    tmp_path: Path,
) -> None:
    """Deleting `.mycelium/cas/` stays safe (D-005) — and stays *honest*: the
    snapshot serves normally, is marked degraded, and says how to recover."""
    root = repo(tmp_path)
    build(root)
    shutil.rmtree(root / ".mycelium" / CAS_DIRNAME)
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")

    manifest = build(root).manifest
    assert manifest.degraded == ("snapshot_state",)
    assert any("not restorable" in warning for warning in manifest.warnings)
    assert any("--clean" in warning for warning in manifest.warnings)
    assert not list_snapshots(root)[0].restorable

    healed = build(root, clean=True).manifest
    assert healed.degraded == ()
    assert list_snapshots(root)[0].restorable
    rollback(root, healed.snapshot_id)  # and it really does restore


# ---------------------------------------------------------------------------
# mycelium gc
# ---------------------------------------------------------------------------


def _snapshot_ids(root: Path) -> list[str]:
    return sorted(path.stem for path in (root / ".mycelium" / SNAPSHOTS_DIRNAME).glob("*.json"))


def test_gc_keeps_the_newest_and_removes_the_rest(tmp_path: Path) -> None:
    root = repo(tmp_path)
    for index in range(5):
        edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + f"\nRevision {index}.\n")
        build(root)
    published = _snapshot_ids(root)
    assert len(published) == 5

    result = collect_garbage(root, keep=2)

    assert len(result.kept_snapshots) == 2
    assert result.removed_snapshots == tuple(published[:3])
    assert _snapshot_ids(root) == published[3:]
    # What survives still works: the retained older snapshot rolls back.
    rollback(root, result.kept_snapshots[0])


def test_gc_never_collects_the_served_snapshot(tmp_path: Path) -> None:
    """Even at `--keep 0`, and even when CURRENT is not the newest — which is
    exactly the state a rollback leaves behind."""
    root = repo(tmp_path)
    first = build(root).manifest
    for index in range(3):
        edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + f"\nRevision {index}.\n")
        build(root)
    rollback(root, first.snapshot_id)

    result = collect_garbage(root, keep=0)

    assert result.kept_snapshots == (first.snapshot_id,)
    assert manifest_path(root / ".mycelium", first.snapshot_id).exists()
    assert corpus_of(root)  # still served
    rollback(root, first.snapshot_id)  # still restorable after its own collection


def test_gc_sweeps_blobs_no_retained_snapshot_or_cache_row_needs(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    for index in range(4):
        edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + f"\nRevision {index}.\n")
        build(root)
    before = blob_count(root)

    result = collect_garbage(root, keep=1, cache_max_age_days=0)

    assert result.removed_blobs > 0
    assert result.reclaimed_bytes > 0
    assert blob_count(root) == before - result.removed_blobs
    assert result.removed_cache_entries > 0
    # The retained snapshot keeps everything it needs, cache row or not.
    rollback(root, result.kept_snapshots[0])
    assert corpus_of(root)


def test_gc_with_default_retention_changes_nothing_on_a_young_repository(
    tmp_path: Path,
) -> None:
    root = repo(tmp_path)
    build(root)
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)
    before = blob_count(root)

    result = collect_garbage(root)

    assert result.removed_snapshots == ()
    assert result.removed_blobs == 0
    assert result.removed_cache_entries == 0
    assert blob_count(root) == before


def test_gc_keeps_cache_rows_inside_the_age_window(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)

    # 40 days on, a 30-day window has expired; the retained snapshots still pin
    # their own artifacts, so only genuinely unreachable blobs go.
    later = datetime.now(tz=UTC) + timedelta(days=40)
    result = collect_garbage(root, keep=1, now=later)
    assert result.removed_cache_entries > 0
    rollback(root, result.kept_snapshots[0])


def test_gc_dry_run_reports_without_touching_anything(tmp_path: Path) -> None:
    root = repo(tmp_path)
    for index in range(4):
        edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + f"\nRevision {index}.\n")
        build(root)
    before_blobs = blob_count(root)
    before_snapshots = _snapshot_ids(root)

    result = collect_garbage(root, keep=1, cache_max_age_days=0, dry_run=True)

    assert result.dry_run
    assert result.removed_blobs > 0
    assert result.removed_snapshots
    assert blob_count(root) == before_blobs
    assert _snapshot_ids(root) == before_snapshots

    applied = collect_garbage(root, keep=1, cache_max_age_days=0)
    assert applied.removed_blobs == result.removed_blobs
    assert applied.removed_snapshots == result.removed_snapshots


def test_gc_removes_staging_debris_but_not_strangers(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    debris = root / ".mycelium" / "CURRENT.tmp"
    debris.write_text("interrupted write", encoding="utf-8")
    stranger = root / ".mycelium" / CAS_DIRNAME / "notes.txt"
    stranger.parent.mkdir(parents=True, exist_ok=True)
    stranger.write_text("not ours", encoding="utf-8")

    result = collect_garbage(root)

    assert result.removed_debris == 1
    assert not debris.exists()
    assert stranger.exists()  # a file the CAS did not write is never deleted


def test_gc_refuses_negative_retention(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    with pytest.raises(SnapshotError, match="must not be negative"):
        collect_garbage(root, keep=-1)


def test_gc_is_journaled(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    collect_garbage(root)
    assert any(item["event"] == "gc.completed" for item in journal_events(root))


# ---------------------------------------------------------------------------
# Interaction with the build's own locking
# ---------------------------------------------------------------------------


def test_rollback_and_gc_respect_the_writer_lock(tmp_path: Path) -> None:
    root = repo(tmp_path)
    manifest = build(root).manifest
    with BuildLock.acquire(root / ".mycelium"):
        with pytest.raises(BuildLockedError):
            rollback(root, manifest.snapshot_id)
        with pytest.raises(BuildLockedError):
            collect_garbage(root)


def test_a_rolled_back_repository_passes_doctor(tmp_path: Path) -> None:
    """The disagreement ADR-0009 taught `doctor` to detect must not be what a
    successful rollback leaves behind."""
    root = repo(tmp_path)
    first = build(root).manifest
    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)
    rollback(root, first.snapshot_id)

    checks = diagnose(root)
    assert worst_status(checks) != "fail", [check.as_dict() for check in checks]
    pointer = next(check for check in checks if check.name == "pointer")
    assert pointer.status == "ok"


def test_manifest_files_survive_being_read_after_rollback(tmp_path: Path) -> None:
    """Rollback publishes an existing manifest; it must not rewrite or move it
    (snapshots are immutable — spec 03 §2)."""
    root = repo(tmp_path)
    first = build(root).manifest
    path = manifest_path(root / ".mycelium", first.snapshot_id)
    before = path.read_bytes()
    mtime = path.stat().st_mtime

    edit(root, "knowledge/api.md", CORPUS["knowledge/api.md"] + "\nDrift.\n")
    build(root)
    rollback(root, first.snapshot_id)

    assert path.read_bytes() == before
    assert path.stat().st_mtime == mtime
    assert read_manifest(root / ".mycelium", first.snapshot_id) == first


def test_mtimes_of_sources_are_untouched_by_rollback(tmp_path: Path) -> None:
    """Rollback is a derived-world operation: it never writes to `knowledge/`."""
    root = repo(tmp_path)
    manifest = build(root).manifest
    before = {
        path: (path.read_bytes(), os.stat(path).st_mtime)
        for path in sorted((root / "knowledge").rglob("*.md"))
    }
    rollback(root, manifest.snapshot_id)
    after = {
        path: (path.read_bytes(), os.stat(path).st_mtime)
        for path in sorted((root / "knowledge").rglob("*.md"))
    }
    assert after == before
