# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Snapshot lifecycle: list, rollback, garbage collection (spec 02 §4.3, 05 §1).

Spec 02 §4.3 says ``mycelium rollback <id>`` *"repoints ``CURRENT``; nothing
rebuilds"*. Taken literally against this milestone's single mutable store, that
would publish a lie: the rows in ``store.db`` belong to the newest build, so
moving the pointer alone yields a repository whose ``CURRENT`` names one
snapshot while its data is another — exactly the disagreement ``mycelium
doctor`` reports as corruption (ADR-0009).

So a snapshot here **carries the state it can be restored from** (ADR-0016).
Every publication writes one content-addressed blob holding that build's whole
``doc_state`` table — a Memento — and ``snapshot_state`` points at it. Rollback
then restores documents, chunks, and the incremental build state from the CAS
and *then* swaps the pointer, under the same lock and transaction discipline as
a build. Nothing recompiles, which is the promise the spec was making; the
pointer swap alone was never enough to keep it.

The same records give ``mycelium gc`` a defined live set, which a
content-addressed store otherwise lacks: a blob is garbage exactly when no
retained snapshot's state names it and no retained build-cache row points at it.
Retention has two dials because there are two kinds of history — snapshots you
might roll back to (``--keep``) and cached artifacts that only make future
builds faster (``--cache-max-age``). Without the second dial the cache pins
every blob it ever wrote and the sweep can never collect anything.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from mycelium.build.cas import CAS_DIRNAME, cas_get, cas_path, cas_put
from mycelium.build.dag import decode_chunks_artifact, decode_document_artifact
from mycelium.build.lock import DEFAULT_STALE_AFTER_S, BuildLock
from mycelium.build.publish import (
    SNAPSHOTS_DIRNAME,
    append_journal,
    manifest_path,
    read_current,
    read_manifest,
    swap_current,
)
from mycelium.graph import edges_digest, resolve_graph
from mycelium.sdk.identity import canonical_json, digest_json
from mycelium.sdk.types import Chunk, Document, Sha256Digest, SnapshotManifest
from mycelium.store import STORE_DIRNAME, DocState, SnapshotState, SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

__all__ = [
    "DEFAULT_CACHE_MAX_AGE_DAYS",
    "DEFAULT_KEEP",
    "GarbageCollection",
    "RollbackResult",
    "SnapshotError",
    "SnapshotInfo",
    "collect_garbage",
    "decode_snapshot_state",
    "encode_snapshot_state",
    "list_snapshots",
    "rollback",
]

DEFAULT_KEEP: Final = 10
"""Snapshots retained by `mycelium gc`, newest first. `CURRENT` is always kept."""

DEFAULT_CACHE_MAX_AGE_DAYS: Final = 30
"""How long an unreferenced cached artifact survives before it is collectable."""

_DIGEST_FILENAME: Final = re.compile(r"^[0-9a-f]{64}$")


class SnapshotError(RuntimeError):
    """A snapshot operation cannot be completed, and says exactly why."""


# ---------------------------------------------------------------------------
# The snapshot Memento
# ---------------------------------------------------------------------------


def encode_snapshot_state(states: tuple[DocState, ...]) -> str:
    """Serialize a build's ``doc_state`` table as the snapshot's restore blob.

    Canonical JSON in path order, so two builds that produced the same corpus
    address the identical blob and the second writes nothing.
    """
    return canonical_json(
        [
            {
                "doc_id": state.doc_id,
                "path": state.path,
                "source_digest": state.source_digest,
                "source_mtime": state.source_mtime,
                "env_digest": state.env_digest,
                "document": state.document_digest,
                "chunks": state.chunks_digest,
                "warnings": list(state.warnings),
                # The document's contribution to the link graph (roadmap 3.4).
                # Restoring it is what lets a rollback rebuild the *same* graph
                # by re-resolving, rather than inheriting the newer build's edges.
                "links": [dict(link) for link in state.links],
                "aliases": list(state.aliases),
                "headings": list(state.headings),
            }
            for state in sorted(states, key=lambda state: state.path)
        ]
    )


def decode_snapshot_state(text: str) -> tuple[DocState, ...]:
    return tuple(
        DocState(
            doc_id=item["doc_id"],
            path=item["path"],
            source_digest=item["source_digest"],
            source_mtime=item["source_mtime"],
            env_digest=item["env_digest"],
            document_digest=item["document"],
            chunks_digest=item["chunks"],
            warnings=tuple(item["warnings"]),
            links=tuple(item.get("links", ())),
            aliases=tuple(item.get("aliases", ())),
            headings=tuple(item.get("headings", ())),
        )
        for item in json.loads(text)
    )


# ---------------------------------------------------------------------------
# mycelium snapshots
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SnapshotInfo:
    """One published snapshot, as `mycelium snapshots` reports it."""

    snapshot_id: str
    created_at: str
    parent_id: str | None
    documents: int
    chunks: int
    quarantined: int
    warnings: int
    is_current: bool
    restorable: bool
    """Its restore state is recorded and present.

    A cheap check — one lookup per snapshot, not one per document. It is
    :func:`rollback` that verifies every artifact the state names, and refuses
    by name when one is missing.
    """

    def as_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "parent_id": self.parent_id,
            "counts": {
                "documents": self.documents,
                "chunks": self.chunks,
                "quarantined": self.quarantined,
            },
            "warnings": self.warnings,
            "current": self.is_current,
            "restorable": self.restorable,
        }


def _manifest_ids(mycelium_dir: Path) -> list[str]:
    """Published snapshot ids, oldest first — ULIDs sort by mint time."""
    directory = mycelium_dir / SNAPSHOTS_DIRNAME
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def list_snapshots(root: Path) -> tuple[SnapshotInfo, ...]:
    """Every published snapshot, newest first (spec 05 §1).

    Reads the manifest files, which are the record of what was published; the
    store contributes only restorability. A manifest that cannot be parsed is
    skipped rather than fatal — one damaged file must not hide the others.
    """
    mycelium_dir = root / STORE_DIRNAME
    current = read_current(mycelium_dir)

    recorded: dict[str, SnapshotState] = {}
    if (mycelium_dir / "store.db").exists():
        try:
            with SqliteStore.open(root, read_only=True) as store:
                recorded = {state.snapshot_id: state for state in store.snapshot_states()}
        except Exception:  # noqa: BLE001 - listing must survive an unreadable store
            recorded = {}

    found: list[SnapshotInfo] = []
    for snapshot_id in _manifest_ids(mycelium_dir):
        try:
            manifest = read_manifest(mycelium_dir, snapshot_id)
        except Exception:  # noqa: BLE001 - a damaged manifest hides nothing else
            continue
        state = recorded.get(snapshot_id)
        found.append(
            SnapshotInfo(
                snapshot_id=manifest.snapshot_id,
                created_at=manifest.created_at.isoformat().replace("+00:00", "Z"),
                parent_id=manifest.parent_id,
                documents=manifest.counts.documents,
                chunks=manifest.counts.chunks,
                quarantined=manifest.counts.quarantined,
                warnings=len(manifest.warnings),
                is_current=manifest.snapshot_id == current,
                restorable=(
                    state is not None and cas_path(mycelium_dir, state.state_blob).exists()
                ),
            )
        )
    return tuple(reversed(found))


# ---------------------------------------------------------------------------
# mycelium rollback
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """What a rollback restored."""

    snapshot_id: str
    previous_id: str | None
    documents: int
    chunks: int

    def as_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "previous_id": self.previous_id,
            "restored": {"documents": self.documents, "chunks": self.chunks},
        }


def _load_state(mycelium_dir: Path, store: SqliteStore, snapshot_id: str) -> tuple[DocState, ...]:
    recorded = store.get_snapshot_state(snapshot_id)
    if recorded is None:
        msg = (
            f"snapshot {snapshot_id} records no restorable state; it predates restorable "
            "snapshots or its state was collected — run `mycelium build` to publish a new one"
        )
        raise SnapshotError(msg)
    blob = cas_get(mycelium_dir, recorded.state_blob)
    if blob is None:
        msg = (
            f"snapshot {snapshot_id} names state blob {recorded.state_blob}, which is missing "
            "or corrupt; it cannot be restored - run `mycelium build`"
        )
        raise SnapshotError(msg)
    return decode_snapshot_state(blob)


def _load_artifacts(
    mycelium_dir: Path, states: tuple[DocState, ...]
) -> list[tuple[DocState, Document, tuple[Chunk, ...]]]:
    """Fetch and revalidate every artifact a snapshot names, before touching the store.

    Loading everything first is the crash-safety rule ADR-0009 set for builds,
    applied here: the transaction that replaces the corpus must not be able to
    discover a missing blob halfway through.
    """
    loaded: list[tuple[DocState, Document, tuple[Chunk, ...]]] = []
    for state in states:
        document_blob = cas_get(mycelium_dir, state.document_digest)
        chunks_blob = cas_get(mycelium_dir, state.chunks_digest)
        if document_blob is None or chunks_blob is None:
            missing = "document" if document_blob is None else "chunks"
            msg = (
                f"cannot restore {state.path}: its {missing} artifact is missing or corrupt "
                f"in the cache; run `mycelium build` to recompile"
            )
            raise SnapshotError(msg)
        try:
            document = decode_document_artifact(document_blob)
            chunks = decode_chunks_artifact(chunks_blob)
        except Exception as error:  # noqa: BLE001 - a cached artifact is never trusted blindly
            msg = f"cannot restore {state.path}: cached artifact is unreadable ({error})"
            raise SnapshotError(msg) from error
        loaded.append((state, document, chunks))
    return loaded


def _verify_against_manifest(
    manifest: SnapshotManifest, states: tuple[DocState, ...], namespace: str
) -> None:
    """Fold the restored per-document digests and demand the manifest's numbers.

    The same construction publication uses (ADR-0015), so a successful restore
    is *proof* that what is now in the store is the snapshot the manifest
    describes — not merely something plausible found in the cache.
    """
    ordered = sorted(states, key=lambda state: state.path)
    edges, _ = resolve_graph(ordered, namespace)
    folded = {
        "documents": digest_json([state.document_digest for state in ordered]),
        "chunks": digest_json([state.chunks_digest for state in ordered]),
        # Re-resolved rather than stored: the graph is a function of the corpus,
        # so reproducing the published digest from the restored state is what
        # proves the restore rebuilt the *same* graph (ADR-0018).
        "edges": edges_digest(edges),
    }
    for artifact_class, digest in folded.items():
        expected = manifest.artifact_digests.get(artifact_class)
        if expected != digest:
            msg = (
                f"refusing to restore {manifest.snapshot_id}: recorded state does not reproduce "
                f"its manifest ({artifact_class} digest {digest} != {expected})"
            )
            raise SnapshotError(msg)


def rollback(
    root: Path, snapshot_id: str, *, stale_after_s: float = DEFAULT_STALE_AFTER_S
) -> RollbackResult:
    """Restore `snapshot_id` and publish it as ``CURRENT`` (spec 05 §1).

    Nothing is recompiled: documents, chunks, and the incremental build state
    come from the content-addressed cache. The publication order is the one
    ADR-0009 fixed for builds — replace under one transaction, commit, then swap
    the pointer — so an interrupted rollback leaves ``CURRENT`` untouched.

    Raises :class:`SnapshotError` when the snapshot is unknown, records no
    restorable state, names an artifact the cache no longer holds, or does not
    reproduce its own manifest; :class:`~mycelium.build.lock.BuildLockedError`
    when a build holds the writer lock.
    """
    mycelium_dir = root / STORE_DIRNAME
    if not manifest_path(mycelium_dir, snapshot_id).exists():
        msg = f"unknown snapshot {snapshot_id}; run `mycelium snapshots` to list them"
        raise SnapshotError(msg)
    manifest = read_manifest(mycelium_dir, snapshot_id)

    with BuildLock.acquire(mycelium_dir, stale_after_s=stale_after_s):
        previous = read_current(mycelium_dir)
        append_journal(
            mycelium_dir, "rollback.started", snapshot_id=snapshot_id, previous_id=previous
        )
        try:
            with SqliteStore.open(root, create=False) as store:
                states = _load_state(mycelium_dir, store, snapshot_id)
                loaded = _load_artifacts(mycelium_dir, states)
                # The namespace comes from the restored records themselves: the
                # manifest digests it rather than naming it, and the documents
                # about to be written are the authority on what they belong to.
                namespace = loaded[0][1].namespace if loaded else "default"
                _verify_against_manifest(manifest, states, namespace)
                edges, _ = resolve_graph(states, namespace)

                chunk_count = 0
                with store.transaction():
                    store.clear_documents()
                    store.clear_edges()
                    for state, document, chunks in loaded:
                        store.put_document(document)
                        chunk_count += store.put_chunks(chunks)
                        store.put_doc_state(state)
                    store.put_edges(edges)
                    store.set_meta(META_CURRENT_SNAPSHOT, snapshot_id)
                swap_current(mycelium_dir, snapshot_id)
        except BaseException as error:
            append_journal(
                mycelium_dir, "rollback.failed", error=f"{type(error).__name__}: {error}"
            )
            raise

        append_journal(
            mycelium_dir,
            "rollback.published",
            snapshot_id=snapshot_id,
            previous_id=previous,
            documents=len(loaded),
            chunks=chunk_count,
        )
    return RollbackResult(
        snapshot_id=snapshot_id,
        previous_id=previous,
        documents=len(loaded),
        chunks=chunk_count,
    )


# ---------------------------------------------------------------------------
# mycelium gc
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GarbageCollection:
    """What a collection removed — or would remove, under ``--dry-run``."""

    kept_snapshots: tuple[str, ...]
    removed_snapshots: tuple[str, ...]
    removed_cache_entries: int
    removed_blobs: int
    reclaimed_bytes: int
    removed_debris: int
    dry_run: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "kept_snapshots": list(self.kept_snapshots),
            "removed_snapshots": list(self.removed_snapshots),
            "removed_cache_entries": self.removed_cache_entries,
            "removed_blobs": self.removed_blobs,
            "reclaimed_bytes": self.reclaimed_bytes,
            "removed_debris": self.removed_debris,
            "dry_run": self.dry_run,
        }


def _parse_stamp(value: str) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


def _retained_ids(
    mycelium_dir: Path, keep: int, current: str | None
) -> tuple[list[str], list[str]]:
    """Split published snapshots into (retained, collectable), newest-first retention.

    ``CURRENT`` is retained whatever its age: collecting the snapshot being
    served would leave the repository pointing at a manifest that no longer
    exists, which is the one state this command must never create.
    """
    published = _manifest_ids(mycelium_dir)
    retained = set(published[-keep:]) if keep > 0 else set()
    if current is not None and current in published:
        retained.add(current)
    return (
        [item for item in published if item in retained],
        [item for item in published if item not in retained],
    )


def collect_garbage(
    root: Path,
    *,
    keep: int = DEFAULT_KEEP,
    cache_max_age_days: int = DEFAULT_CACHE_MAX_AGE_DAYS,
    dry_run: bool = False,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
    now: datetime | None = None,
) -> GarbageCollection:
    """Remove snapshots beyond retention, aged cache rows, and orphaned blobs.

    The live set is computed *before* anything is deleted and from the survivors
    only: the state blob of every retained snapshot, every document and chunks
    artifact those states name, and the artifact of every retained build-cache
    row. Whatever is left under ``.mycelium/cas/`` is unreachable by
    construction, and dropping it costs at most a recompile (D-005).

    `keep` retains that many published snapshots (newest first, plus ``CURRENT``
    always); `cache_max_age_days` retains build-cache rows written within that
    window — ``0`` collects every row not pinned by a retained snapshot. Takes
    the writer lock, because a build racing a sweep would be reading the blobs
    it deletes.
    """
    if keep < 0 or cache_max_age_days < 0:
        msg = "retention values must not be negative"
        raise SnapshotError(msg)

    mycelium_dir = root / STORE_DIRNAME
    moment = now or datetime.now(tz=UTC)
    cutoff = moment - timedelta(days=cache_max_age_days)

    with BuildLock.acquire(mycelium_dir, stale_after_s=stale_after_s):
        current = read_current(mycelium_dir)
        retained_ids, collectable_ids = _retained_ids(mycelium_dir, keep, current)

        with SqliteStore.open(root, create=False) as store:
            live: set[Sha256Digest] = set()
            for snapshot_id in retained_ids:
                state = store.get_snapshot_state(snapshot_id)
                if state is None:
                    continue
                live.add(state.state_blob)
                blob = cas_get(mycelium_dir, state.state_blob)
                if blob is None:
                    continue
                for doc_state in decode_snapshot_state(blob):
                    live.add(doc_state.document_digest)
                    live.add(doc_state.chunks_digest)

            aged_keys: list[str] = []
            for entry in store.cache_entries():
                stamp = _parse_stamp(entry.created_at)
                # An unparseable stamp is treated as ancient: a row whose age
                # cannot be established must not pin a blob forever.
                if stamp is None or stamp < cutoff:
                    aged_keys.append(entry.build_key)
                else:
                    live.add(entry.artifact_digest)

            removed_blobs, reclaimed = _sweep_blobs(mycelium_dir, live, dry_run=dry_run)
            debris = _sweep_debris(mycelium_dir, dry_run=dry_run)

            removed_entries = len(aged_keys)
            if not dry_run:
                with store.transaction():
                    store.delete_cache_entries(aged_keys)
                    for snapshot_id in collectable_ids:
                        store.delete_snapshot_state(snapshot_id)
                for snapshot_id in collectable_ids:
                    manifest_path(mycelium_dir, snapshot_id).unlink(missing_ok=True)

        result = GarbageCollection(
            kept_snapshots=tuple(retained_ids),
            removed_snapshots=tuple(collectable_ids),
            removed_cache_entries=removed_entries,
            removed_blobs=removed_blobs,
            reclaimed_bytes=reclaimed,
            removed_debris=debris,
            dry_run=dry_run,
        )
        append_journal(mycelium_dir, "gc.completed", **result.as_dict())
    return result


def _sweep_blobs(mycelium_dir: Path, live: set[Sha256Digest], *, dry_run: bool) -> tuple[int, int]:
    """Delete every CAS blob outside `live`, returning (count, bytes)."""
    cas_root = mycelium_dir / CAS_DIRNAME
    if not cas_root.is_dir():
        return 0, 0
    live_names = {digest.removeprefix("sha256:") for digest in live}

    removed = 0
    reclaimed = 0
    for shard in sorted(cas_root.iterdir()):
        if not shard.is_dir():
            continue
        for blob in sorted(shard.iterdir()):
            # Anything that is not a digest-named file was not written by the
            # CAS; leave it alone rather than deleting a stranger's file.
            if not blob.is_file() or not _DIGEST_FILENAME.match(blob.name):
                continue
            if blob.name in live_names:
                continue
            reclaimed += blob.stat().st_size
            removed += 1
            if not dry_run:
                blob.unlink(missing_ok=True)
        if not dry_run and not any(shard.iterdir()):
            shard.rmdir()
    return removed, reclaimed


def _sweep_debris(mycelium_dir: Path, *, dry_run: bool) -> int:
    """Remove staging debris: ``*.tmp`` files a crashed atomic write left behind.

    An atomic write cleans up after itself on failure; a process killed between
    the write and the rename cannot. These are always safe to delete — the
    rename either happened (the target exists) or the write is lost anyway.
    """
    removed = 0
    for path in sorted(mycelium_dir.rglob("*.tmp")):
        if not path.is_file():
            continue
        removed += 1
        if not dry_run:
            path.unlink(missing_ok=True)
    return removed


def record_snapshot_state(
    mycelium_dir: Path, store: SqliteStore, snapshot_id: str, states: tuple[DocState, ...]
) -> Sha256Digest:
    """Store a build's restore state and point the snapshot at it (roadmap 3.2).

    Called by the orchestrator inside the publication transaction, so a snapshot
    and its restorability commit together or not at all.
    """
    digest = cas_put(mycelium_dir, encode_snapshot_state(states))
    store.put_snapshot_state(
        SnapshotState(
            snapshot_id=snapshot_id,
            state_blob=digest,
            created_at=datetime.now(tz=UTC).isoformat(),
        )
    )
    return digest
