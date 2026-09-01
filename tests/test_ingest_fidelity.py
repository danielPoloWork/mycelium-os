# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The fidelity report and its budget (roadmap 4.3): every element is accounted for, the
report is a pure function of the KIR, and the budget bounds loss rather than imperfection."""

from pathlib import Path

import pytest

from mycelium.ingest.errors import ParseError
from mycelium.ingest.fidelity import build_report, check_budget, encode_report, report_digest
from mycelium.sdk.identity import canonical_json, digest_bytes
from mycelium.sdk.types import (
    KirDocument,
    KirNode,
    NodeKind,
    OpaqueDisposition,
)

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
DIGEST = digest_bytes(b"source")
KIR_DIGEST = digest_bytes(b"kir")


def kir(*nodes: KirNode, warnings: tuple[str, ...] = ()) -> KirDocument:
    return KirDocument(doc_id=DOC_ID, source_digest=DIGEST, nodes=nodes, warnings=warnings)


def node(ordinal: int, kind: NodeKind, **fields: object) -> KirNode:
    return KirNode(id=f"n{ordinal + 1}", kind=kind, ord=ordinal, **fields)  # type: ignore[arg-type]


def report_of(document: KirDocument) -> object:
    return build_report(document, kir_digest=KIR_DIGEST, parser="stub", parser_version="0")


# ---------------------------------------------------------------------------
# The three buckets
# ---------------------------------------------------------------------------


def test_a_document_that_lost_nothing_reports_no_loss() -> None:
    report = build_report(
        kir(
            node(0, NodeKind.HEADING, level=1, text="H"),
            node(1, NodeKind.PARAGRAPH, text="text"),
        ),
        kir_digest=KIR_DIGEST,
        parser="stub",
        parser_version="0",
    )
    assert report.elements == 2
    assert report.represented == 2
    assert (report.degraded, report.lost) == (0, 0)
    assert report.loss == 0.0
    assert report.complete


def test_an_opaque_node_that_kept_its_payload_is_degraded_not_lost() -> None:
    report = build_report(
        kir(
            node(0, NodeKind.PARAGRAPH, text="text"),
            node(
                1,
                NodeKind.OPAQUE,
                variant=OpaqueDisposition.DEGRADED.value,
                note="pandoc RawBlock",
                text="<marquee>legacy</marquee>",
            ),
        ),
        kir_digest=KIR_DIGEST,
        parser="stub",
        parser_version="0",
    )
    # Structure lost, content preserved. Charging this against the loss budget
    # would fire on documents that lost nothing and teach an operator to raise it.
    assert (report.degraded, report.lost) == (1, 0)
    assert report.loss == 0.0
    assert not report.complete


def test_an_opaque_node_with_no_payload_is_lost() -> None:
    report = build_report(
        kir(
            node(0, NodeKind.PARAGRAPH, text="text"),
            node(1, NodeKind.OPAQUE, variant=OpaqueDisposition.LOST.value, note="page 2"),
        ),
        kir_digest=KIR_DIGEST,
        parser="stub",
        parser_version="0",
    )
    assert (report.degraded, report.lost) == (0, 1)
    assert report.loss == pytest.approx(0.5)


def test_reference_nodes_are_not_elements() -> None:
    """Counting them would inflate the denominator and shrink every loss ratio.

    Their text is already inside the block that contains them — the exclusion the
    chunker makes for the same reason (ADR-0006).
    """
    report = build_report(
        kir(
            node(0, NodeKind.PARAGRAPH, text="see the log"),
            node(1, NodeKind.LINK, target="https://example.com", text="the log"),
            node(2, NodeKind.TAG_REF, text="tag"),
            node(3, NodeKind.OPAQUE, variant=OpaqueDisposition.LOST.value, note="x"),
        ),
        kir_digest=KIR_DIGEST,
        parser="stub",
        parser_version="0",
    )
    assert report.elements == 2, "the paragraph and the opaque node, not the references"
    assert report.loss == pytest.approx(0.5)


def test_the_parsers_warnings_travel_verbatim() -> None:
    """A parser's declared policies are recorded once, not counted per element."""
    warnings = ("PDF text layer only: no headings", "definition lists became lists")
    report = build_report(
        kir(node(0, NodeKind.PARAGRAPH, text="t"), warnings=warnings),
        kir_digest=KIR_DIGEST,
        parser="stub",
        parser_version="0",
    )
    assert report.warnings == warnings


def test_the_report_names_the_engine_that_produced_the_kir() -> None:
    report = build_report(
        kir(node(0, NodeKind.PARAGRAPH, text="t")),
        kir_digest=KIR_DIGEST,
        parser="pandoc",
        parser_version="3.10",
    )
    assert (report.parser, report.parser_version) == ("pandoc", "3.10")
    assert report.source_digest == DIGEST
    assert report.kir_digest == KIR_DIGEST
    assert report.doc_id == DOC_ID


# ---------------------------------------------------------------------------
# The report is a pure function of the KIR
# ---------------------------------------------------------------------------


def test_the_report_can_be_recomputed_from_the_kir_alone() -> None:
    """The property that makes it worth storing rather than logging (ADR-0034)."""
    document = kir(
        node(0, NodeKind.HEADING, level=1, text="H"),
        node(1, NodeKind.OPAQUE, variant=OpaqueDisposition.LOST.value, note="page 2"),
        warnings=("one warning",),
    )
    first = build_report(document, kir_digest=KIR_DIGEST, parser="p", parser_version="1")
    second = build_report(document, kir_digest=KIR_DIGEST, parser="p", parser_version="1")
    assert first == second
    assert report_digest(first) == report_digest(second)


def test_the_stored_bytes_are_canonical_json() -> None:
    report = build_report(
        kir(node(0, NodeKind.PARAGRAPH, text="t")),
        kir_digest=KIR_DIGEST,
        parser="p",
        parser_version="1",
    )
    encoded = encode_report(report)
    assert encoded.decode("utf-8") == canonical_json(report.model_dump(mode="json"))
    assert report_digest(report) == digest_bytes(encoded)


# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------


def test_a_document_within_budget_passes() -> None:
    report = build_report(
        kir(*(node(index, NodeKind.PARAGRAPH, text="t") for index in range(20))),
        kir_digest=KIR_DIGEST,
        parser="p",
        parser_version="1",
    )
    check_budget(report, max_lost_fraction=0.05)


def test_a_document_over_budget_is_refused_with_the_numbers() -> None:
    nodes = [node(0, NodeKind.PARAGRAPH, text="t")]
    nodes.append(node(1, NodeKind.OPAQUE, variant=OpaqueDisposition.LOST.value, note="page 2"))
    report = build_report(kir(*nodes), kir_digest=KIR_DIGEST, parser="p", parser_version="1")
    with pytest.raises(ParseError) as caught:
        check_budget(report, max_lost_fraction=0.05)
    message = str(caught.value)
    # An operator meeting this is deciding whether the document is worth keeping
    # at that fidelity, and cannot decide without the numbers.
    assert "1 of 2 elements" in message
    assert "50%" in message
    assert "max_failed_elements" in message


def test_a_document_with_no_elements_at_all_is_refused_whatever_the_budget() -> None:
    report = build_report(kir(), kir_digest=KIR_DIGEST, parser="p", parser_version="1")
    assert report.loss == 0.0, "zero over zero is not loss, arithmetically"
    with pytest.raises(ParseError, match="nothing was extracted"):
        check_budget(report, max_lost_fraction=1.0)


def test_a_budget_of_one_admits_a_total_loss() -> None:
    """The escape hatch: an operator who wants the projection anyway can say so."""
    report = build_report(
        kir(node(0, NodeKind.OPAQUE, variant=OpaqueDisposition.LOST.value, note="page 1")),
        kir_digest=KIR_DIGEST,
        parser="p",
        parser_version="1",
    )
    check_budget(report, max_lost_fraction=1.0)


# ---------------------------------------------------------------------------
# Against the real corpus
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"


def test_the_real_fixtures_lose_nothing() -> None:
    """The M4 exit gate, on the fixtures that are not hostile."""
    from mycelium.ingest import Registry

    registry = Registry.resolve(
        parsers=["markdown", "docling", "pdf"], connectors=["file"], roots=[FIXTURES]
    )
    for name in ("source.md", "source.docx", "source.html", "text-layer.pdf"):
        blob = registry.acquire(str(FIXTURES / name))
        document = registry.parse(blob, doc_id=DOC_ID)
        report = build_report(document, kir_digest=KIR_DIGEST, parser="x", parser_version="1")
        assert report.lost == 0, f"{name} lost {report.lost} element(s)"
        assert report.elements > 0, name
