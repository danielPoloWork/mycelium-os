# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Content-addressed artifact storage: ``.mycelium/cas/<xx>/<sha256>`` (spec 02 §3).

The CAS holds the build cache's *bytes*; the ``build_cache`` table in the store
holds the *index* (build key → artifact digest). Splitting the two is what makes
the cache safe to distrust: a row without its blob is a cache miss, never an
error, and a blob whose bytes no longer hash to its own name is discarded rather
than believed. Nothing in the published snapshot references the CAS — it is
purely reuse, so deleting the whole directory costs one clean rebuild and
nothing else (D-005: the derived world is disposable).

Blobs are stored verbatim and named by ``digest_bytes`` of their content — the
same tier-1 custody rule spec 03 §2 fixes for acquired originals, so ingestion
shares this layout instead of growing a second CAS. It does **not** share the
lifecycle: acquired originals live under :data:`CUSTODY_DIRNAME`, which the
garbage collector never sweeps, because "costs a recompile" and "loses the
evidence a citation quotes" are not the same kind of loss (ADR-0033).

**Writes go straight to the final name** — no temp file, no fsync, no rename —
and the integrity story is the re-hash on read that this module has always done.
A blob's name *is* the digest of its bytes, so a torn write leaves a file that
does not hash to its own name, which is the one thing :func:`cas_get` already
refuses to believe. The ceremony bought nothing the content addressing did not
already provide, and it was expensive: measured at roadmap 6.30, the second name
costs **~7 ms** per blob on the machine of record against ~1 ms for the fsync,
so the ritual was **2.1x** a plain write and ~25 s of a 91.7 s thousand-document
build (ADR-0145).

Snapshot publication, tier-1 custody and quarantine keep
:func:`~mycelium.layout.atomic_write_bytes`: none of them is disposable, and for
those a name appearing before its content is durable is a real failure rather
than a cache miss.
"""

import os
from pathlib import Path
from typing import Final

from mycelium.layout import CAS_DIRNAME, CUSTODY_DIRNAME, write_bytes
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.types import Sha256Digest

__all__ = ["CAS_DIRNAME", "CUSTODY_DIRNAME", "cas_get", "cas_inventory", "cas_path", "cas_put"]


_PREFIX: Final = "sha256:"
_SHARD_CHARS: Final = 2


def cas_path(mycelium_dir: Path, digest: Sha256Digest) -> Path:
    """Where a blob with this digest lives: ``cas/<first two hex chars>/<hex>``."""
    hexdigest = digest.removeprefix(_PREFIX)
    return mycelium_dir / CAS_DIRNAME / hexdigest[:_SHARD_CHARS] / hexdigest


def cas_put(mycelium_dir: Path, text: str) -> Sha256Digest:
    """Store `text` and return its digest; a blob that already exists is not rewritten.

    Content addressing makes the write idempotent: two builds racing to store the
    same artifact produce the same bytes under the same name, so the loser's work
    is simply redundant, never conflicting. It is also what makes the write
    *direct*, rather than the tmp-fsync-rename the rest of this project uses.

    **What the ceremony protected against, and why the digest already does.** A
    crash mid-write leaves a short or empty file under a name that is the digest
    of the *whole* artifact, and :func:`cas_get` re-hashes every blob it reads —
    so the torn blob is discarded and the stage recomputes, which is exactly what
    would have happened had the blob never existed. The failure the ritual
    prevents is a name appearing before its content is durable, and here that
    failure is already indistinguishable from a cache miss (D-005: the derived
    world is disposable, and its recovery story is `mycelium build`).

    **What it costs to keep is not the fsync.** Roadmap 6.30 decomposed it
    (`tools/measure_cas_write.py`): on the machine of record a plain write of a
    12 KiB blob takes 7.6 ms, the fsync adds 2.0 ms, and the second name adds
    **6.7 ms** — the ritual is 2.1x a plain write, and a filter driver charges it
    per file operation rather than per byte. Across the 2 995 blobs a
    thousand-document build writes, dropping it is ~25 s.

    **The one behaviour this changes for a reader.** A concurrent reader can now
    observe a blob mid-write, where before the final name only ever appeared
    complete. It reads as a cache miss — the digest will not match — so the
    outcome is a recompute rather than bad bytes. That is the cache's documented
    worst case, and it is the trade this makes deliberately.
    """
    data = text.encode("utf-8")
    digest = digest_bytes(data)
    path = cas_path(mycelium_dir, digest)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_bytes(path, data)
    return digest


def cas_inventory(mycelium_dir: Path) -> frozenset[str]:
    """Every blob digest the sweepable CAS holds right now, from one listing per shard.

    The question a build asks of the cache on every run is "are this snapshot's
    artifacts still here" — restorability (ADR-0016) — and asking it with
    `exists()` costs two probes per live document, which at a thousand documents
    cost more than reading the store did (roadmap 6.20). Two hundred and fifty-six
    directory listings cost the same whatever the corpus size, and the set they
    build answers every probe. Only the two-character shards are read:
    `originals/` is tier-1 custody with its own lifecycle and its own reader
    (ADR-0033), and a `.tmp` beside a blob is a write in flight, not a blob.

    Since roadmap 6.30 this module writes no `.tmp` of its own — a blob goes
    straight to its final name — so the filter now only excludes debris an older
    cache left behind, and it stays for exactly that. What replaced it is a
    narrower imprecision worth naming: a blob still being written *is* listed
    here, because its name is already final. The consequence is bounded, because
    this set answers *restorability* and :func:`cas_get` answers *readability* —
    an in-flight blob counts as present, then reads as a miss, and the stage
    recomputes it.
    """
    root = mycelium_dir / CAS_DIRNAME
    found: set[str] = set()
    try:
        shards = [entry for entry in os.scandir(root) if entry.is_dir()]
    except FileNotFoundError:
        return frozenset()
    for shard in shards:
        if len(shard.name) != _SHARD_CHARS:
            continue
        with os.scandir(shard.path) as entries:
            found.update(
                f"{_PREFIX}{entry.name}"
                for entry in entries
                if entry.is_file() and not entry.name.endswith(".tmp")
            )
    return frozenset(found)


def cas_get(mycelium_dir: Path, digest: Sha256Digest) -> str | None:
    """Read the blob named by `digest`, or ``None`` when it is absent or corrupt.

    The bytes are re-hashed on every read: a blob that no longer matches its own
    name (bit rot, a truncated copy, manual editing) is deleted and reported as a
    miss, so the stage re-runs from source instead of trusting bad bytes. The
    caller never has to distinguish "never cached" from "cache went bad".
    """
    path = cas_path(mycelium_dir, digest)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if digest_bytes(data) != digest:
        _discard(path)
        return None
    return data.decode("utf-8")


def _discard(path: Path) -> None:
    """Delete a blob whose bytes do not match its name, and never fail doing it.

    The delete is what keeps a corrupt blob from being a *permanent* miss:
    :func:`cas_put` skips a name that already exists, so a bad blob left in place
    would be re-read and re-rejected on every build.

    It tolerates failure because since roadmap 6.30 a blob is written directly to
    its final name, so this can race a writer that is still filling it. On
    Windows the delete then fails with a sharing violation - and the right
    outcome is the miss this function is already returning, not an exception in a
    reader. The next build re-reads it, by which time it is either complete or
    genuinely stale.
    """
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
