# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The packed vector matrix: one file per model, memory-mapped (ADR-0026).

The exact scan spec 04 §3 asks for is arithmetic over a matrix, and the
arithmetic was never the cost. Reading 10 000 vectors out of SQLite as rows and
joining their blobs cost 79 ms of the scan's 92 ms; the matrix multiply itself
cost 0.4 ms. This module removes the reading: the same vectors are written once,
contiguously, in a file the query path memory-maps instead of materialising.

**It is a cache, not a source of truth.** The ``vectors`` table stays exactly as
it was, the pack is derived from it, and a query that cannot use the pack falls
back to the SQL scan and answers identically. That is what makes the file safe to
be absent, stale, truncated, or written by a version that packed it differently.

Staleness is not detected — it is made impossible. The file name carries the
generation counter it was packed at, so a pack whose vectors have since changed
is simply a file nobody opens. Every write to ``vectors`` bumps that counter, and
there are exactly three (``put_vectors``, ``delete_orphan_vectors``, and the
recreate that drops the schema).
"""

import os
import re
import struct
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Self

__all__ = [
    "KEY_WIDTH",
    "VectorPack",
    "pack_path",
    "prune_packs",
    "write_pack",
]

_MAGIC: Final = b"MYCVEC\x00\x01"
_FORMAT_VERSION: Final = 1
KEY_WIDTH: Final = 80
"""Fixed key width in bytes. ``sha256:`` + 64 hex is 71; the slack is padding, and
a fixed width is what makes a key lookup arithmetic instead of a parse."""

_HEADER: Final = struct.Struct("<8sHHIIQ")
"""magic, format version, key width, dim, count, generation."""
_HEADER_SIZE: Final = 32  # _HEADER.size rounded up, so the keys start aligned

_SAFE_NAME: Final = re.compile(r"[^A-Za-z0-9._-]")


def pack_path(store_db: Path, model_id: str, generation: int) -> Path:
    """Where the pack for `model_id` at `generation` lives.

    Beside the database, because it is part of the same derived state: a store
    copied without it still works, and a store copied with it stays correct.
    """
    safe = _SAFE_NAME.sub("_", model_id)[:64]
    return store_db.with_name(f"vectors-{safe}-{generation}.pack")


def prune_packs(store_db: Path, keep: Collection[Path] = ()) -> int:
    """Delete every pack not in `keep` — the previous generations, and the packs
    of models this store no longer holds. Best-effort: a file a concurrent reader
    still has mapped cannot be unlinked on Windows, and is left where it is."""
    removed = 0
    kept = set(keep)
    for candidate in store_db.parent.glob("vectors-*.pack"):
        if candidate in kept:
            continue
        try:
            candidate.unlink()
        except OSError:  # a concurrent reader still holds it mapped
            continue
        removed += 1
    return removed


def write_pack(
    store_db: Path,
    model_id: str,
    *,
    dim: int,
    generation: int,
    rows: Iterable[tuple[str, bytes]],
) -> Path | None:
    """Write the pack for `model_id`, keys sorted, through a temp file and rename.

    `rows` is ``(chunk_digest, little-endian float32 blob)``. Returns the path
    written, or ``None`` when there is nothing to pack or a row is malformed —
    a pack is an optimisation, so anything surprising declines to produce one
    rather than raising into a build that was otherwise fine.
    """
    ordered = sorted(rows, key=lambda row: row[0])
    if not ordered:
        return None
    width = dim * 4
    keys = bytearray()
    matrix = bytearray()
    for digest, blob in ordered:
        encoded = digest.encode("ascii", errors="replace")
        if len(encoded) > KEY_WIDTH or len(blob) != width:
            return None
        keys += encoded.ljust(KEY_WIDTH, b"\x00")
        matrix += blob

    target = pack_path(store_db, model_id, generation)
    header = _HEADER.pack(_MAGIC, _FORMAT_VERSION, KEY_WIDTH, dim, len(ordered), generation)
    payload = header.ljust(_HEADER_SIZE, b"\x00") + bytes(keys) + bytes(matrix)

    tmp = target.with_name(target.name + ".tmp")
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    descriptor = os.open(tmp, flags)
    try:
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        return None
    return target


@dataclass(frozen=True, slots=True)
class VectorPack:
    """A memory-mapped packed matrix, ready to score a query against.

    Held open for the life of a store handle: mapping costs page-table setup, and
    a long-lived process (the MCP server) pays it once while a one-shot CLI query
    pays it per invocation. Both are far below the cost of not having it.
    """

    matrix: Any
    """``numpy.memmap`` of shape ``(count, dim)``, little-endian float32."""
    keys: Any
    """``numpy.memmap`` of ``count`` fixed-width key records."""
    dim: int
    count: int

    @classmethod
    def open(cls, store_db: Path, model_id: str, generation: int) -> Self | None:
        """Map the pack for this model and generation, or ``None``.

        Every failure returns ``None`` — missing file, foreign format, truncation,
        no numpy — because the caller's fallback is the SQL scan, which is slower
        and exactly as correct.
        """
        path = pack_path(store_db, model_id, generation)
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - vectors imply the embeddings extra
            return None
        try:
            with path.open("rb") as handle:
                raw = handle.read(_HEADER.size)
            if len(raw) < _HEADER.size:
                return None
            magic, version, width, dim, count, stamp = _HEADER.unpack(raw)
            if magic != _MAGIC or version != _FORMAT_VERSION or stamp != generation:
                return None
            if width != KEY_WIDTH or dim <= 0 or count <= 0:
                return None
            expected = _HEADER_SIZE + count * KEY_WIDTH + count * dim * 4
            if path.stat().st_size != expected:
                return None  # truncated, or a longer file than its header claims

            keys = np.memmap(
                path, dtype=f"S{KEY_WIDTH}", mode="r", offset=_HEADER_SIZE, shape=(count,)
            )
            matrix = np.memmap(
                path,
                dtype="<f4",
                mode="r",
                offset=_HEADER_SIZE + count * KEY_WIDTH,
                shape=(count, dim),
            )
        except (OSError, ValueError):
            return None
        return cls(matrix=matrix, keys=keys, dim=dim, count=count)

    def rows_of(self, digests: Sequence[str]) -> Any:
        """Row indices of `digests`, for a filtered query. Keys are sorted, so
        this is a binary search rather than a scan; unknown digests are dropped."""
        import numpy as np

        wanted = np.array(
            [digest.encode("ascii", errors="replace") for digest in digests], dtype=f"S{KEY_WIDTH}"
        )
        found = np.searchsorted(self.keys, wanted)
        inside = found < self.count
        found, wanted = found[inside], wanted[inside]
        return found[self.keys[found] == wanted]

    def best(self, query: Any, limit: int) -> list[tuple[str, float]]:
        """Score every vector and return the `limit` best as ``(digest, score)``."""
        return self._rank(self.matrix @ query, None, limit)

    def best_of_rows(self, query: Any, rows: Any, limit: int) -> list[tuple[str, float]]:
        """The same, restricted to `rows` — spec 04 §2's pre-filter, as indices."""
        import numpy as np

        if len(rows) == 0:
            return []
        return self._rank(np.asarray(self.matrix[rows] @ query), rows, limit)

    def _rank(self, scores: Any, rows: Any, limit: int) -> list[tuple[str, float]]:
        import numpy as np

        take = min(limit, len(scores))
        if take < len(scores):
            # argpartition, not a sort: ranking 10 000 scores in Python cost
            # 10.6 ms of the old scan, against 0.5 ms for this (ADR-0026).
            top = np.argpartition(-scores, take - 1)[:take]
        else:
            top = np.arange(len(scores))
        top = top[np.argsort(-scores[top], kind="stable")]
        indices = top if rows is None else np.asarray(rows)[top]
        return [
            (self.keys[index].tobytes().rstrip(b"\x00").decode("ascii"), float(scores[position]))
            for position, index in zip(top, indices, strict=True)
        ]
