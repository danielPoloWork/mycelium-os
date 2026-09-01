# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The fidelity report, and the budget it is measured against (spec 02 §5).

Ingestion's promise is not that nothing is lost. It is that **nothing is lost
silently** — the M4 exit gate's words are "every element represented / opaque /
dropped-by-policy / failed-and-reported". This module is the accounting that
makes the promise checkable.

The report is a **pure function of the KIR document**, which is the property that
makes it worth storing rather than logging: anyone holding the KIR blob can
recompute the report and check it against the digest the document record carries.
Nothing in it is a judgement a parser made and then forgot.

Three buckets, and the reason there are three:

``represented``
    A node carrying its content. The overwhelming majority.

``degraded``
    An ``opaque`` node whose payload survived — a raw block kept as literal text,
    a docling item KIR has no kind for. *Structure* was lost, content was not, and
    the KIR warnings say which structure.

``lost``
    An ``opaque`` node whose content did not survive: a PDF page with no text
    layer, a construct with no recoverable payload. **This is the only bucket the
    loss budget counts**, because a budget that fires on a document that lost
    nothing teaches an operator to raise the budget.

A parser's *declared policies* — pandoc drops thematic breaks, docling drops
running headers, the PDF reader claims no structure at all — are not per-element
counts. They are properties of the parser, recorded once in the KIR document's
warnings, and carried into the report verbatim. Emitting a node per dropped
thematic break to make a counter tick would put noise in the projection to
satisfy a metric.

Reference nodes (links, images, wikilinks, embeds, tags) are not elements: their
text already lives inside the block that contains them, and the chunker makes the
same exclusion for the same reason (ADR-0006). Counting them would inflate the
denominator and quietly shrink every loss ratio.
"""

from typing import Final

from mycelium.ingest.errors import LossBudgetError
from mycelium.sdk.identity import canonical_json, digest_bytes
from mycelium.sdk.types import (
    FidelityReport,
    KirDocument,
    NodeKind,
    OpaqueDisposition,
    Sha256Digest,
)

__all__ = [
    "REFERENCE_KINDS",
    "build_report",
    "check_budget",
    "encode_report",
    "report_digest",
]

REFERENCE_KINDS: Final = frozenset(
    {
        NodeKind.LINK,
        NodeKind.IMAGE,
        NodeKind.WIKILINK,
        NodeKind.EMBED,
        NodeKind.TAG_REF,
    }
)
"""Nodes whose text is already inside their parent block, so not elements of their own."""


def build_report(
    kir: KirDocument,
    *,
    kir_digest: Sha256Digest,
    parser: str,
    parser_version: str,
) -> FidelityReport:
    """Account for every element of `kir`, in the three buckets above."""
    represented = 0
    degraded = 0
    lost = 0
    for node in kir.nodes:
        if node.kind in REFERENCE_KINDS:
            continue
        if node.kind is not NodeKind.OPAQUE:
            represented += 1
        elif node.variant == OpaqueDisposition.LOST.value:
            lost += 1
        else:
            degraded += 1

    return FidelityReport(
        doc_id=kir.doc_id,
        source_digest=kir.source_digest,
        kir_digest=kir_digest,
        parser=parser,
        parser_version=parser_version,
        elements=represented + degraded + lost,
        represented=represented,
        degraded=degraded,
        lost=lost,
        warnings=kir.warnings,
    )


def encode_report(report: FidelityReport) -> bytes:
    """Serialize a report to the bytes custody stores — canonical JSON (spec 03 §1)."""
    return canonical_json(report.model_dump(mode="json")).encode("utf-8")


def report_digest(report: FidelityReport) -> Sha256Digest:
    """The digest a document record carries in ``fidelity_report``."""
    return digest_bytes(encode_report(report))


def check_budget(report: FidelityReport, *, max_lost_fraction: float) -> None:
    """Refuse a projection whose loss exceeds the budget (`[ingest] max_failed_elements`).

    A `LossBudgetError` — a `ParseError`, so a document over budget is quarantined
    per document like any other ingestion failure rather than aborting a build
    (spec 02 §5), and named so its quarantine record can say the document *parsed*
    and was refused for what it lost. The message
    carries the ratio, the counts, and the setting's name — an operator meeting
    this is deciding whether the document is worth keeping at that fidelity, and
    cannot decide without the numbers.

    A document with **no elements at all** is refused too, whatever the budget
    says. Zero over zero is not "no loss": an empty projection from a non-empty
    source is the silent failure this whole module exists to prevent.
    """
    if report.elements == 0:
        msg = (
            "nothing was extracted from this document — no elements at all, so there is "
            "nothing to project. Its bytes are in custody; check whether the source is "
            "readable at all"
        )
        raise LossBudgetError(msg)
    if report.loss > max_lost_fraction:
        msg = (
            f"{report.lost} of {report.elements} elements did not survive parsing "
            f"({report.loss:.0%}), above the [ingest] max_failed_elements budget of "
            f"{max_lost_fraction:.0%}; the original is in custody and the projection was "
            "not written"
        )
        raise LossBudgetError(msg)
