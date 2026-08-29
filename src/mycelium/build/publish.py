# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Snapshot publication: manifest files, the ``CURRENT`` pointer, the journal.

The publication rules (spec 02 §7, D-015), which every later phase inherits:

- A snapshot manifest is **immutable**: written once to
  ``.mycelium/snapshots/<ulid>.json`` with deterministic bytes, never edited.
- ``CURRENT`` is a one-line pointer file holding the published snapshot id. It
  changes only by atomic replacement — write ``CURRENT.tmp``, fsync it, then
  ``os.replace`` — so no reader ever observes a torn pointer. ``os.replace`` is
  a POSIX ``rename(2)`` and Windows ``MoveFileEx(MOVEFILE_REPLACE_EXISTING)``,
  the ``ReplaceFile`` semantics the spec names.
- On POSIX the containing directory is fsynced after the replace so the swap
  survives power loss; Windows cannot fsync a directory handle this way and its
  ``MoveFileEx`` metadata write is the strongest guarantee available.
- ``journal.jsonl`` is an append-only operational log for diagnostics only
  (F-4): nothing rebuilds from it, nothing replays it.
"""

import json
import os
from pathlib import Path
from typing import Final

from mycelium.sdk.types import SnapshotManifest

__all__ = [
    "CURRENT_FILENAME",
    "JOURNAL_FILENAME",
    "SNAPSHOTS_DIRNAME",
    "append_journal",
    "atomic_write_text",
    "manifest_path",
    "read_current",
    "read_manifest",
    "swap_current",
    "write_manifest",
]

CURRENT_FILENAME: Final = "CURRENT"
SNAPSHOTS_DIRNAME: Final = "snapshots"
JOURNAL_FILENAME: Final = "journal.jsonl"


def atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` through a same-directory temp file and rename.

    The temp file lives beside the target (rename is only atomic within one
    filesystem), is fsynced before the rename (so the *content* is durable
    before the *name* appears), and is removed on failure.
    """
    tmp = path.with_name(path.name + ".tmp")
    # O_BINARY matters: without it, Windows' CRT opens in text mode and rewrites
    # LF as CRLF — which would make manifest bytes platform-dependent (G6).
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    descriptor = os.open(tmp, flags)
    try:
        try:
            os.write(descriptor, text.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    """Make a rename durable on POSIX; a no-op where directories can't be opened."""
    if os.name != "posix":  # pragma: no cover - exercised on the POSIX CI cells
        return
    descriptor = os.open(directory, os.O_RDONLY)  # pragma: no cover
    try:  # pragma: no cover
        os.fsync(descriptor)
    finally:  # pragma: no cover
        os.close(descriptor)


def manifest_path(mycelium_dir: Path, snapshot_id: str) -> Path:
    return mycelium_dir / SNAPSHOTS_DIRNAME / f"{snapshot_id}.json"


def write_manifest(mycelium_dir: Path, manifest: SnapshotManifest) -> Path:
    """Write an immutable snapshot manifest with deterministic bytes.

    Refuses to overwrite: a manifest that already exists belongs to a published
    snapshot, and snapshots are immutable (spec 03 §2).
    """
    path = manifest_path(mycelium_dir, manifest.snapshot_id)
    if path.exists():
        msg = f"snapshot manifest already exists and is immutable: {path}"
        raise FileExistsError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, text)
    return path


def read_manifest(mycelium_dir: Path, snapshot_id: str) -> SnapshotManifest:
    path = manifest_path(mycelium_dir, snapshot_id)
    return SnapshotManifest.model_validate_json(path.read_text(encoding="utf-8"))


def swap_current(mycelium_dir: Path, snapshot_id: str) -> None:
    """Atomically point ``CURRENT`` at `snapshot_id` — the publish instant."""
    atomic_write_text(mycelium_dir / CURRENT_FILENAME, snapshot_id + "\n")


def read_current(mycelium_dir: Path) -> str | None:
    """The published snapshot id, or ``None`` when nothing has been published."""
    try:
        text = (mycelium_dir / CURRENT_FILENAME).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return text or None


def append_journal(mycelium_dir: Path, event: str, **fields: object) -> None:
    """Append one structured event line to ``journal.jsonl``.

    Diagnostics only (F-4): best-effort, never raises into the build — a full
    disk must fail the build through a real write, not through its logging.
    """
    record = {"event": event, **fields}
    try:
        with (mycelium_dir / JOURNAL_FILENAME).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    except OSError:  # pragma: no cover - by design, diagnostics must not kill a build
        pass
