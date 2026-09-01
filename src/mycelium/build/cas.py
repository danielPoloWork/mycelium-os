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

Writes go through the same tmp-fsync-rename ritual as snapshot publication:
a crash mid-write must never leave a blob whose name lies about its bytes.
"""

from pathlib import Path
from typing import Final

from mycelium.build.publish import atomic_write_text
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.types import Sha256Digest

__all__ = ["CAS_DIRNAME", "CUSTODY_DIRNAME", "cas_get", "cas_path", "cas_put"]

CAS_DIRNAME: Final = "cas"

CUSTODY_DIRNAME: Final = "originals"
"""The one subtree of the CAS that is **not** disposable (roadmap 4.2, ADR-0033).

Tier-1 custody — acquired originals and the KIR compiled from them — lives at
``cas/originals/`` per architecture §4. It is named here, beside the sweepable
layout it sits inside, because the garbage collector has to know which of the two
it is looking at, and a lifecycle rule that lived only in the module that writes
the blobs would be invisible to the module that deletes them.
:mod:`mycelium.ingest.custody` owns what goes in it.
"""

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
    is simply redundant, never conflicting.
    """
    data = text.encode("utf-8")
    digest = digest_bytes(data)
    path = cas_path(mycelium_dir, digest)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text)
    return digest


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
        path.unlink(missing_ok=True)
        return None
    return data.decode("utf-8")
