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
6. **Account** for every element in a fidelity report, store it, and refuse the
   projection when its loss exceeds `[ingest] max_failed_elements` (roadmap 4.3).
7. **Project** the KIR as an evidence document under `knowledge/evidence/`, which
   the compiler then treats like any other authored file.

Steps 6 and 7 are in that order for the same reason 2 precedes 3: the report is
written whether or not the projection is, so a document refused for losing too
much still leaves an account of *what* it lost. A refusal with no evidence behind
it is not a diagnosis.

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

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mycelium.ingest.custody import Custody
from mycelium.ingest.fidelity import build_report, check_budget, encode_report
from mycelium.ingest.projection import Projection, project
from mycelium.ingest.registry import Registry
from mycelium.ingest.safety import DEFAULT_LIMITS, Limits, guard
from mycelium.sdk.identity import canonical_json
from mycelium.sdk.protocols import Blob
from mycelium.sdk.types import (
    CustodyKind,
    CustodyRecord,
    FidelityReport,
    KirDocument,
    Sha256Digest,
    SourceTrust,
    Ulid,
)

__all__ = ["Ingested", "encode_kir", "ingest_source", "write_projection"]


@dataclass(frozen=True, slots=True)
class Ingested:
    """One source, taken into custody, compiled, accounted for, and projected."""

    blob: Blob
    original: CustodyRecord
    kir: KirDocument
    kir_digest: Sha256Digest
    parser_id: str
    parser_version: str
    report: FidelityReport
    fidelity_digest: Sha256Digest
    projection: Projection


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
    max_failed_elements: float = 0.05,
    knowledge_dir: str = "knowledge",
    source_trust: SourceTrust | None = None,
    trust_for: Callable[[str], SourceTrust | None] | None = None,
) -> Ingested:
    """Take `source` into custody, compile it, account for it, and project it.

    Raises :class:`~mycelium.ingest.errors.ConnectorError` when the source cannot
    be acquired, :class:`~mycelium.ingest.errors.ParseError` when the bytes are
    refused, cannot be compiled, or lose more than the budget allows, and
    :class:`~mycelium.ingest.errors.UnsupportedMediaTypeError` when no pinned
    parser reads it. The original is in custody by the time any of the last two
    can be raised, and the fidelity report by the time the budget one can.

    Returns the projection **without writing it** — see :func:`write_projection`.
    The split is deliberate: everything up to here writes only into `.mycelium/`,
    and putting a file into someone's Git working tree is a decision for the
    caller that knows about their repository.
    """
    custody = Custody(mycelium_dir)
    blob = registry.acquire(source, scheme=scheme)
    # `[sources]` classifies an *origin*, and the origin is only known once the
    # connector has resolved the source into a URI — so the caller passes the
    # resolver, not a resolved answer. An explicit `source_trust` still wins: it
    # is a caller saying "I know what this is".
    trust = (
        source_trust
        if source_trust is not None
        else (trust_for(blob.source_uri) if trust_for else None)
    )
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
    custody.link_kir(original.digest, stored.digest)

    report = build_report(
        kir,
        kir_digest=stored.digest,
        parser=parser.meta.id,
        parser_version=parser.meta.version,
    )
    fidelity = custody.put(
        encode_report(report),
        kind=CustodyKind.FIDELITY,
        media_type="application/json",
        derived_from=original.digest,
        connector=parser.meta.id,
        connector_version=parser.meta.version,
    )
    # The *linked* record is what comes back, not one written earlier: a caller
    # wants the complete custody fact, and returning an earlier one would make two
    # identical ingestions of the same bytes disagree.
    linked = custody.link_fidelity(original.digest, fidelity.digest)

    # After the report is stored, so a document refused for losing too much still
    # leaves an account of what it lost.
    check_budget(report, max_lost_fraction=max_failed_elements)

    return Ingested(
        blob=blob,
        original=linked,
        kir=kir,
        kir_digest=stored.digest,
        parser_id=parser.meta.id,
        parser_version=parser.meta.version,
        report=report,
        fidelity_digest=fidelity.digest,
        projection=project(
            kir,
            source_uri=blob.source_uri,
            source_digest=original.digest,
            source_trust=trust,
            knowledge_dir=knowledge_dir,
        ),
    )


def write_projection(root: Path, ingested: Ingested) -> Path:
    """Write the evidence document into the repository at `root`, and return its path.

    The one step that touches **tier 2** — the authored tree, in Git, that a human
    owns. Re-ingesting an unchanged source rewrites nothing, so the operation is
    idempotent and leaves no spurious diff; the source digest is in the filename,
    so a *changed* source normally lands beside the old document rather than on
    top of it, and the human decides what to do with the pair.
    """
    destination = root / ingested.projection.path
    text = ingested.projection.text
    if destination.exists() and destination.read_text(encoding="utf-8") == text:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")
    return destination
