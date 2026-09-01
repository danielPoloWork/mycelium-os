# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The evidence lane, end to end: acquire → guard → custody → parse (spec 02 §5).

Five steps that must happen in this order, and one function that is the only
place they are ordered:

1. **Acquire** through the pinned connector — path safety, the byte ceiling,
   media-type classification (roadmap 4.1).
2. **Store the original**, verbatim and content-addressed, in tier-1 custody.
3. **Guard** the bytes against shapes that cost more to read than they claim to
   be, *before* any engine sees them (:mod:`mycelium.ingest.safety`).
4. **Parse** with the pinned parser for the media type.
5. **Store the KIR** and link it to the original, so the compiled form is
   recoverable without re-running the engine.

The order of 2 and 3 is the one decision here worth stating. Storing the original
*before* deciding whether it is worth parsing costs a write for a document that
turns out to be hostile — and buys the ability to look at that document
afterwards. A quarantined file whose bytes were never kept cannot be re-examined,
and re-examining quarantined files is the whole point of quarantining them
rather than dropping them (roadmap 4.6). Ingestion is custody first, compilation
second.

What this module deliberately does not do is *decide what to do about a failure*.
It raises the typed errors :mod:`mycelium.ingest.errors` defines and lets the
caller choose: `mycelium ingest` will quarantine and carry on (roadmap 4.6), a
test asserts the type, and a future build stage records it in the manifest. A
seam that swallowed failures would take that choice away from all three.
"""

from dataclasses import dataclass
from pathlib import Path

from mycelium.ingest.custody import Custody
from mycelium.ingest.registry import Registry
from mycelium.ingest.safety import DEFAULT_LIMITS, Limits, guard
from mycelium.sdk.identity import canonical_json
from mycelium.sdk.protocols import Blob
from mycelium.sdk.types import CustodyKind, CustodyRecord, KirDocument, Sha256Digest, Ulid

__all__ = ["Ingested", "encode_kir", "ingest_source"]


@dataclass(frozen=True, slots=True)
class Ingested:
    """One source, taken into custody and compiled."""

    blob: Blob
    original: CustodyRecord
    kir: KirDocument
    kir_digest: Sha256Digest
    parser_id: str
    parser_version: str


def encode_kir(kir: KirDocument) -> bytes:
    """Serialize a KIR document to the bytes custody stores.

    Canonical JSON (spec 03 §1), so the same KIR is the same blob on every
    platform: the custody digest of a compiled document is then a *fact about the
    document*, not about the machine that compiled it.
    """
    return canonical_json(kir.model_dump(mode="json")).encode("utf-8")


def ingest_source(
    mycelium_dir: Path,
    registry: Registry,
    source: str,
    *,
    doc_id: Ulid,
    scheme: str = "",
    limits: Limits = DEFAULT_LIMITS,
) -> Ingested:
    """Take `source` into custody and compile it into KIR.

    Raises :class:`~mycelium.ingest.errors.ConnectorError` when the source cannot
    be acquired, :class:`~mycelium.ingest.errors.ParseError` when the bytes are
    refused or cannot be compiled, and
    :class:`~mycelium.ingest.errors.UnsupportedMediaTypeError` when no pinned
    parser reads it. The original is in custody by the time any of the last two
    can be raised.
    """
    custody = Custody(mycelium_dir)
    blob = registry.acquire(source, scheme=scheme)
    parser = registry.parser_for(blob.media_type)

    original = custody.put_blob(
        blob,
        connector=registry.connector_for(scheme).meta.id,
        version=registry.connector_for(scheme).meta.version,
    )

    guard(blob.data, blob.media_type, limits=limits)
    kir = registry.parse(blob, doc_id=doc_id)

    encoded = encode_kir(kir)
    stored = custody.put(
        encoded,
        kind=CustodyKind.KIR,
        media_type="application/json",
        derived_from=original.digest,
        connector=parser.meta.id,
        connector_version=parser.meta.version,
    )
    # The *linked* record is what comes back, not the one written before parsing:
    # a caller wants the complete custody fact, and returning the earlier one
    # would make two identical ingestions of the same bytes disagree.
    linked = custody.link_kir(original.digest, stored.digest)

    return Ingested(
        blob=blob,
        original=linked,
        kir=kir,
        kir_digest=stored.digest,
        parser_id=parser.meta.id,
        parser_version=parser.meta.version,
    )
