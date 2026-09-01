# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Tier-1 custody: the acquired original, kept (spec 02 §§3-5, D-004/D-005).

A citation into an ingested document claims to quote bytes that arrived from
somewhere. Custody is what makes that claim checkable a year later, when the
source file has moved, changed, or gone: the original is stored verbatim under
its own digest, together with the facts about where it came from, and the KIR
compiled from it is stored beside it.

**This is the one part of `.mycelium/` that is not disposable, and the
distinction is the whole design.** The build cache (:mod:`mycelium.build.cas`)
is *purely reuse* — delete it and the next build costs a recompile and nothing
else (D-005). Tier-1 custody is *evidence*: delete it and a verbatim quote has
nothing behind it, because the compiler is a pure function of tiers 1-2 and this
is tier 1 (architecture §4). They share a layout and a digest rule, and they must
not share a lifecycle, so custody lives in its own subtree that
:func:`mycelium.build.snapshots.collect_garbage` never sweeps.

Three rules follow from "this is evidence":

**Write-once, content-addressed.** A blob is named by the digest of its bytes,
so storing the same source twice is idempotent. The record's ``first_seen``
never moves, which is what makes re-ingesting an unchanged document produce an
unchanged document record — an amended timestamp would break incremental builds
by hand.

**Amendments only grow.** A record's identity fields (digest, size, kind) are
fixed at first write; ``sources`` and ``kir_digest`` may be added to, and the
sources are stored sorted so two machines that acquired the same bytes from the
same two URIs hold byte-identical records whatever order they did it in.

**Reads verify.** Every read re-hashes, and a blob that no longer matches its own
name is reported as missing rather than returned. Unlike the build cache, it is
*not* deleted: a corrupt piece of evidence is a fact an operator needs to see
(`mycelium doctor` reports it), not litter to tidy away.
"""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from mycelium.ingest.errors import CustodyError
from mycelium.layout import CAS_DIRNAME, CUSTODY_DIRNAME, atomic_write_bytes
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob
from mycelium.sdk.types import CustodyKind, CustodyRecord, Sha256Digest

__all__ = ["Custody", "CustodyIntegrity", "custody_root"]

_PREFIX: Final = "sha256:"
_SHARD_CHARS: Final = 2
_RECORD_SUFFIX: Final = ".json"


def custody_root(mycelium_dir: Path) -> Path:
    """The tier-1 subtree: ``.mycelium/cas/originals`` (architecture §4)."""
    return mycelium_dir / CAS_DIRNAME / CUSTODY_DIRNAME


@dataclass(frozen=True, slots=True)
class CustodyIntegrity:
    """What a sweep of the custody subtree found — `mycelium doctor`'s input."""

    blobs: int
    bytes: int
    corrupt: tuple[Sha256Digest, ...]
    orphaned_records: tuple[Sha256Digest, ...]
    """Records whose blob is gone: the evidence is lost and the note remains."""

    @property
    def healthy(self) -> bool:
        return not self.corrupt and not self.orphaned_records


class Custody:
    """The tier-1 store for one repository."""

    def __init__(self, mycelium_dir: Path) -> None:
        self._root = custody_root(mycelium_dir)

    @property
    def root(self) -> Path:
        return self._root

    # -- paths ------------------------------------------------------------

    def blob_path(self, digest: Sha256Digest) -> Path:
        hexdigest = _hex(digest)
        return self._root / hexdigest[:_SHARD_CHARS] / hexdigest

    def record_path(self, digest: Sha256Digest) -> Path:
        return self.blob_path(digest).with_name(_hex(digest) + _RECORD_SUFFIX)

    # -- writing ----------------------------------------------------------

    def put(
        self,
        data: bytes,
        *,
        kind: CustodyKind,
        media_type: str,
        source_uri: str | None = None,
        connector: str | None = None,
        connector_version: str | None = None,
        derived_from: Sha256Digest | None = None,
        now: datetime | None = None,
    ) -> CustodyRecord:
        """Take `data` into custody and return its record, amending an existing one.

        Idempotent by construction: identical bytes produce the same digest, the
        same path, and — because identity fields never change and `sources` is a
        sorted set — the same record.
        """
        digest = digest_bytes(data)
        path = self.blob_path(digest)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(path, data)

        existing = self.record(digest)
        sources = tuple(sorted({*(existing.sources if existing else ()), *_maybe(source_uri)}))
        if existing is None:
            record = CustodyRecord(
                digest=digest,
                size=len(data),
                kind=kind,
                media_type=media_type,
                sources=sources,
                connector=connector,
                connector_version=connector_version,
                derived_from=derived_from,
                first_seen=(now or datetime.now(tz=UTC)),
            )
        else:
            _refuse_contradiction(existing, kind=kind, size=len(data), derived_from=derived_from)
            record = existing.model_copy(
                update={
                    "sources": sources,
                    "connector": existing.connector or connector,
                    "connector_version": existing.connector_version or connector_version,
                }
            )
        self._write_record(record)
        return record

    def put_blob(
        self, blob: Blob, *, connector: str | None = None, version: str | None = None
    ) -> CustodyRecord:
        """Take an acquired :class:`~mycelium.sdk.protocols.Blob` into custody."""
        return self.put(
            blob.data,
            kind=CustodyKind.ORIGINAL,
            media_type=blob.media_type,
            source_uri=blob.source_uri,
            connector=connector,
            connector_version=version,
        )

    def link_kir(self, original: Sha256Digest, kir_digest: Sha256Digest) -> CustodyRecord:
        """Record which KIR blob was compiled from an original.

        An amendment, not a rewrite: the link is the only field a later stage
        adds, and re-parsing the same bytes with the same parser writes the same
        link, so the operation is idempotent like everything else here.
        """
        return self._amend(original, "kir_digest", kir_digest)

    def link_fidelity(self, original: Sha256Digest, fidelity_digest: Sha256Digest) -> CustodyRecord:
        """Record which fidelity report accounts for this original's projection."""
        return self._amend(original, "fidelity_digest", fidelity_digest)

    def _amend(self, original: Sha256Digest, field: str, value: Sha256Digest) -> CustodyRecord:
        """Add one derived-artefact link to an original's record, idempotently."""
        record = self.record(original)
        if record is None:
            msg = f"no custody record for {original}; the original must be stored first"
            raise CustodyError(msg)
        if getattr(record, field) == value:
            return record
        amended = record.model_copy(update={field: value})
        self._write_record(amended)
        return amended

    def _write_record(self, record: CustodyRecord) -> None:
        path = self.record_path(record.digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        atomic_write_bytes(path, payload.encode("utf-8"))

    # -- reading ----------------------------------------------------------

    def get(self, digest: Sha256Digest) -> bytes | None:
        """The bytes named by `digest`, or ``None`` when absent **or corrupt**.

        A blob that fails its own digest is not deleted the way a cache blob is
        (:func:`mycelium.build.cas.cas_get`): evidence that went bad is a finding,
        and deleting it would destroy the only trace that it existed.
        """
        try:
            data = self.blob_path(digest).read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            return None
        return data if digest_bytes(data) == digest else None

    def record(self, digest: Sha256Digest) -> CustodyRecord | None:
        """The custody record for `digest`, or ``None`` when there is none."""
        try:
            raw = self.record_path(digest).read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return None
        try:
            return CustodyRecord.model_validate_json(raw)
        except ValueError as error:
            msg = f"{self.record_path(digest)} is not a valid custody record - {error}"
            raise CustodyError(msg) from error

    def records(self) -> Iterator[CustodyRecord]:
        """Every custody record, in digest order — the tier-1 inventory."""
        if not self._root.is_dir():
            return
        for shard in sorted(self._root.iterdir()):
            if not shard.is_dir():
                continue
            for path in sorted(shard.iterdir()):
                if path.suffix != _RECORD_SUFFIX or not path.is_file():
                    continue
                try:
                    yield CustodyRecord.model_validate_json(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    msg = f"{path} is not a valid custody record - {error}"
                    raise CustodyError(msg) from error

    def digests(self) -> set[Sha256Digest]:
        """Every digest under custody — the set the garbage collector must never touch."""
        return {record.digest for record in self.records()}

    def verify(self) -> CustodyIntegrity:
        """Re-hash every blob and report what no longer holds."""
        blobs = 0
        total = 0
        corrupt: list[Sha256Digest] = []
        orphaned: list[Sha256Digest] = []
        for record in self.records():
            path = self.blob_path(record.digest)
            if not path.is_file():
                orphaned.append(record.digest)
                continue
            data = path.read_bytes()
            blobs += 1
            total += len(data)
            if digest_bytes(data) != record.digest:
                corrupt.append(record.digest)
        return CustodyIntegrity(
            blobs=blobs,
            bytes=total,
            corrupt=tuple(corrupt),
            orphaned_records=tuple(orphaned),
        )


def _hex(digest: Sha256Digest) -> str:
    hexdigest = digest.removeprefix(_PREFIX)
    if len(hexdigest) != 64 or not all(char in "0123456789abcdef" for char in hexdigest):
        msg = f"{digest!r} is not a sha256 digest"
        raise CustodyError(msg)
    return hexdigest


def _maybe(value: str | None) -> Sequence[str]:
    return (value,) if value else ()


def _refuse_contradiction(
    existing: CustodyRecord,
    *,
    kind: CustodyKind,
    size: int,
    derived_from: Sha256Digest | None,
) -> None:
    """A digest identifies bytes; two writers must agree about what they are.

    A contradiction here is not a conflict to resolve but a bug to surface: the
    same bytes cannot be an original in one call and a KIR document in another,
    and if they appear to be, something upstream is mislabelling evidence.
    """
    for field, was, now in (
        ("kind", existing.kind, kind),
        ("size", existing.size, size),
    ):
        if was != now:
            msg = f"custody record {existing.digest} already has {field}={was!r}, not {now!r}"
            raise CustodyError(msg)
    if derived_from is not None and existing.derived_from not in (None, derived_from):
        msg = (
            f"custody record {existing.digest} is derived from {existing.derived_from}, "
            f"not {derived_from}"
        )
        raise CustodyError(msg)
