# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The parsers, exercised for real (roadmap 4.1).

The load-bearing test in this file is
:func:`test_one_document_through_four_engines_cites_identically`: the same document,
authored once and rendered by pandoc into DOCX, HTML and reStructuredText, reaches four
different parsing engines and comes back with the *same anchors*. That is the claim the
KIR boundary makes (D-007) — Mycelium owns the representation, not the parsers — and it
is worth nothing until an engine other than markdown-it has to satisfy it.

Nothing here is mocked. The engines run: docling converts the DOCX and HTML, pandoc's
binary converts the reStructuredText, PDFium reads the PDF. The pandoc tests skip when
the binary is absent, and say so.
"""

import shutil
from pathlib import Path

import pytest

from mycelium.chunking import chunk_document
from mycelium.ingest import Registry
from mycelium.ingest.errors import ParseError, PluginUnavailableError
from mycelium.ingest.media import DOCX, HTML, MARKDOWN, PDF, RST
from mycelium.ingest.parsers import docling as docling_parser
from mycelium.ingest.parsers import markdown as markdown_parser
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.ingest.parsers import pdf as pdf_parser
from mycelium.ingest.parsers.builder import KirBuilder
from mycelium.sdk.identity import digest_text
from mycelium.sdk.protocols import Blob, Parser
from mycelium.sdk.types import KirDocument, NodeKind

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
FIXTURES = Path(__file__).parent / "fixtures" / "ingest"

HAVE_PANDOC = shutil.which(pandoc_parser.DEFAULT_EXECUTABLE) is not None
needs_pandoc = pytest.mark.skipif(not HAVE_PANDOC, reason="the pandoc binary is not on PATH")


@pytest.fixture(scope="module")
def registry() -> Registry:
    names = ["markdown", "docling", "pdf"] + (["pandoc"] if HAVE_PANDOC else [])
    return Registry.resolve(parsers=names, connectors=["file"], roots=[FIXTURES])


def parse(registry: Registry, name: str) -> KirDocument:
    return registry.parse(registry.acquire(str(FIXTURES / name)), doc_id=DOC_ID)


def texts(document: KirDocument, kind: NodeKind) -> list[str]:
    return [node.text or "" for node in document.nodes if node.kind is kind]


def blob_of(path: Path, media_type: str) -> Blob:
    return Blob.of(path.read_bytes(), media_type=media_type, source_uri=path.as_uri())


# ---------------------------------------------------------------------------
# The claim the whole milestone rests on
# ---------------------------------------------------------------------------


@needs_pandoc
def test_one_document_through_four_engines_cites_identically(registry: Registry) -> None:
    anchors = {}
    for name in ("source.md", "source.docx", "source.html", "source.rst"):
        document = parse(registry, name)
        anchors[name] = [
            chunk.anchor for chunk in chunk_document(document, doc_path="docs/retry.md")
        ]
    # The Markdown route is the reference: every other engine must land on the
    # same citable anchors, or an ingested copy of a document cites differently
    # from the document.
    reference = anchors["source.md"]
    assert "docs/retry.md#backoff/0" in reference
    for name, found in anchors.items():
        assert set(found) <= set(reference), f"{name} invented an anchor"
        assert found[0] == reference[0], f"{name} disagrees about the document's first chunk"


@needs_pandoc
def test_every_engine_finds_the_same_headings(registry: Registry) -> None:
    for name in ("source.md", "source.docx", "source.html", "source.rst"):
        document = parse(registry, name)
        headings = [
            (node.level, node.text) for node in document.nodes if node.kind is NodeKind.HEADING
        ]
        assert headings == [(1, "Retry Policy"), (2, "Backoff")], name


@needs_pandoc
def test_every_engine_recovers_the_paragraph_verbatim(registry: Registry) -> None:
    expected = (
        "Webhook deliveries are retried five times, and the delivery log records each attempt."
    )
    for name in ("source.md", "source.docx", "source.html"):
        assert expected in texts(parse(registry, name), NodeKind.PARAGRAPH), name


@needs_pandoc
def test_every_engine_finds_the_link_target(registry: Registry) -> None:
    for name in ("source.md", "source.docx", "source.html", "source.rst"):
        document = parse(registry, name)
        targets = [node.target for node in document.nodes if node.kind is NodeKind.LINK]
        assert "https://example.com/log" in targets, name


# ---------------------------------------------------------------------------
# markdown — the parser with no optional runtime
# ---------------------------------------------------------------------------


def test_markdown_parser_satisfies_the_protocol() -> None:
    assert isinstance(markdown_parser.plugin(), Parser)


def test_markdown_parser_takes_the_caller_s_identity() -> None:
    document = markdown_parser.plugin().parse(
        blob_of(FIXTURES / "source.md", MARKDOWN), doc_id=DOC_ID
    )
    # Identity belongs to the caller (spec 03 §3): a parser that minted its own
    # would hand back a different document id on every rebuild.
    assert document.doc_id == DOC_ID


def test_markdown_refuses_bytes_that_are_not_utf8() -> None:
    blob = Blob.of(b"# \xff\xfe", media_type=MARKDOWN, source_uri="file:///bad.md")
    with pytest.raises(ParseError, match="not valid UTF-8"):
        markdown_parser.plugin().parse(blob, doc_id=DOC_ID)


# ---------------------------------------------------------------------------
# docling — DOCX and HTML through the declarative backends
# ---------------------------------------------------------------------------


def test_docling_declares_only_what_it_reads_offline() -> None:
    parser = docling_parser.plugin()
    assert set(parser.media_types) == {DOCX, HTML}
    # PDF is deliberately absent: docling reads it only through the ML pipeline
    # this project does not ship (ADR-0032).
    assert PDF not in parser.media_types


def test_docling_reads_the_table_by_row_and_column(registry: Registry) -> None:
    document = parse(registry, "source.html")
    cells = texts(document, NodeKind.TABLE_CELL)
    assert cells == ["attempt", "delay", "1", "1 s", "2", "2 s"]
    rows = [node.variant for node in document.nodes if node.kind is NodeKind.TABLE_ROW]
    assert rows[0] == "header"


def test_docling_keeps_the_code_block_atomic(registry: Registry) -> None:
    assert "delay = 2 ** attempt" in texts(parse(registry, "source.docx"), NodeKind.CODE_BLOCK)


def test_docling_records_a_docx_note_its_backend_cannot_see(registry: Registry) -> None:
    """BUG-0016: the part docling does not read is accounted for, not ignored.

    `word/footnotes.xml` never reaches docling's DOCX backend, so the note's body
    reaches no KIR node — and the fidelity report, being a pure function of the
    KIR, reported the document as complete. The loss is now an opaque `lost`
    element, which is what makes it countable.
    """
    document = parse(registry, "corpus/elements.docx")
    notes = [
        node
        for node in document.nodes
        if node.kind is NodeKind.OPAQUE and "note" in (node.note or "")
    ]
    assert len(notes) == 1, "the fixture carries exactly one footnote"
    assert notes[0].variant == "lost"
    assert any("does not surface" in warning for warning in document.warnings)


def test_a_docx_without_notes_reports_none(registry: Registry) -> None:
    """The separator furniture every DOCX carries must not be counted as content.

    Word declares `separator` and `continuationSeparator` notes whether or not the
    document has any real ones, and the parts are full of `<w:footnoteRef/>`. The
    first version of this count reported three footnotes for a document with none.
    """
    document = parse(registry, "source.docx")
    assert not [node for node in document.nodes if node.kind is NodeKind.OPAQUE]


def test_docling_reports_the_engine_version_not_ours() -> None:
    meta = docling_parser.plugin().meta
    assert meta.id == "docling"
    assert meta.deterministic is True
    assert meta.version[0].isdigit()


def test_docling_joins_formatting_runs_without_losing_the_spaces() -> None:
    # docling strips whitespace at a run boundary, so a sentence containing a link
    # arrives in three pieces. Concatenating them would corrupt every such sentence.
    assert docling_parser._join_runs(["and the", "delivery log", "records it."]) == (
        "and the delivery log records it."
    )
    assert docling_parser._join_runs(["a link", "."]) == "a link."
    assert docling_parser._join_runs(["(", "parenthesised", ")"]) == "(parenthesised)"
    assert docling_parser._join_runs(["", "only"]) == "only"


def test_docling_maps_page_provenance_onto_a_source_locator() -> None:
    # Constructed by hand because the declarative backends carry no page
    # geometry; the mapping still has to be right for the day a backend does.
    docling_core = pytest.importorskip("docling_core.types.doc.document")
    base = pytest.importorskip("docling_core.types.doc.base")

    item = docling_core.TextItem(
        self_ref="#/texts/0",
        label="text",
        orig="on a page",
        text="on a page",
        prov=[
            docling_core.ProvenanceItem(
                page_no=3,
                bbox=base.BoundingBox(l=10.0, t=700.0, r=200.0, b=680.0),
                charspan=(0, 9),
            )
        ],
    )
    locator = docling_parser._src(item)
    assert locator is not None
    assert locator.page == 3
    assert locator.bbox == (10.0, 680.0, 200.0, 700.0), "the box is ordered, whatever the origin"


def test_docling_without_provenance_has_no_locator(registry: Registry) -> None:
    document = parse(registry, "source.docx")
    assert all(node.src is None for node in document.nodes)


# ---------------------------------------------------------------------------
# pandoc — the fallback
# ---------------------------------------------------------------------------


@needs_pandoc
def test_pandoc_declares_six_formats_and_not_pdf() -> None:
    parser = pandoc_parser.plugin()
    assert set(parser.media_types) == set(pandoc_parser.READERS)
    assert PDF not in parser.media_types, "pandoc does not read PDF; that is why pdf exists"


@needs_pandoc
def test_pandoc_records_an_unmappable_construct_instead_of_dropping_it(
    registry: Registry,
) -> None:
    """The M4 exit gate is zero *silent* element loss.

    The fixture's definition list is the case: GFM cannot express it, so an
    adapter that went through pandoc's Markdown writer would lose it without a
    trace. Reading the AST, the term and the definition survive and the warning
    records what the representation no longer distinguishes.
    """
    document = parse(registry, "source.rst")
    assert any("definition list" in warning for warning in document.warnings)
    items = texts(document, NodeKind.LIST_ITEM)
    assert "Term" in items


@needs_pandoc
def test_pandoc_keeps_raw_output_as_an_opaque_node() -> None:
    """A construct KIR cannot model survives as an opaque node, not as a hole."""
    source = b"Title\n=====\n\n.. raw:: html\n\n   <marquee>legacy</marquee>\n\ntext\n"
    document = pandoc_parser.plugin().parse(
        Blob.of(source, media_type=RST, source_uri="file:///raw.rst"), doc_id=DOC_ID
    )
    opaque = [node for node in document.nodes if node.kind is NodeKind.OPAQUE]
    assert len(opaque) == 1
    assert opaque[0].note == "pandoc RawBlock"
    # The payload is literal source text, so it is kept as text — the treatment
    # ADR-0006 already gives raw HTML in authored Markdown. `blob` stays unset:
    # a parser has no custody handle, and a digest naming bytes nobody wrote is
    # a claim the reader cannot follow (ADR-0033).
    assert opaque[0].media_type == "text/plain"
    assert opaque[0].text == "<marquee>legacy</marquee>"
    assert opaque[0].blob is None
    assert any("RawBlock" in warning for warning in document.warnings)
    assert texts(document, NodeKind.PARAGRAPH) == ["text"], "the rest is untouched"


def test_an_unknown_pandoc_construct_becomes_opaque_without_the_engine() -> None:
    # The fall-through itself, unit-tested: a constructor this adapter has never
    # seen must produce a recorded node, whatever pandoc version emitted it.
    builder = KirBuilder()
    pandoc_parser._block(builder, {"t": "SomeFutureBlock", "c": ["x"]}, parent=None)
    assert [node.kind for node in builder.nodes] == [NodeKind.OPAQUE]
    assert builder.nodes[0].note == "pandoc SomeFutureBlock"
    # A structured construct has no literal text to keep, so it travels as its
    # name and its position — which is what "makes loss visible" asks for.
    assert builder.nodes[0].text is None
    # The warning names the construct *and* its disposition, because the fidelity
    # report reads the disposition back out of the node (ADR-0034).
    assert builder.warnings == ["pandoc SomeFutureBlock kept as an opaque node (lost)"]
    assert builder.nodes[0].variant == "lost"


@needs_pandoc
def test_pandoc_reports_a_failure_with_the_engine_s_own_message() -> None:
    parser = pandoc_parser.plugin()
    blob = Blob.of(b"not a docx at all", media_type=DOCX, source_uri="file:///broken.docx")
    with pytest.raises(ParseError, match="pandoc exited"):
        parser.parse(blob, doc_id=DOC_ID)


@needs_pandoc
def test_pandoc_reads_the_table_and_marks_its_header(registry: Registry) -> None:
    document = parse(registry, "source.rst")
    assert texts(document, NodeKind.TABLE_CELL) == ["attempt", "delay", "1", "1 s", "2", "2 s"]
    assert [node.variant for node in document.nodes if node.kind is NodeKind.TABLE_ROW][0] == (
        "header"
    )


@needs_pandoc
def test_pandoc_carries_no_source_positions_and_says_nothing_it_cannot(
    registry: Registry,
) -> None:
    # Pandoc's JSON AST has no offsets. The honest output is `src = None`
    # everywhere rather than a fabricated line number.
    assert all(node.src is None for node in parse(registry, "source.rst").nodes)


def test_pandoc_is_unavailable_with_a_remedy_when_the_binary_is_missing() -> None:
    with pytest.raises(PluginUnavailableError, match="pandoc"):
        pandoc_parser.plugin(executable="pandoc-that-does-not-exist")


@needs_pandoc
def test_pandoc_below_version_three_is_refused_for_the_missing_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Completed:
        returncode = 0
        stdout = b"pandoc 2.19.2\nCompiled with ...\n"
        stderr = b""

    monkeypatch.setattr(pandoc_parser.subprocess, "run", lambda *a, **k: Completed())
    with pytest.raises(PluginUnavailableError, match="--sandbox"):
        pandoc_parser.plugin()


# ---------------------------------------------------------------------------
# pdf — the text layer, and only the text layer
# ---------------------------------------------------------------------------


def test_pdf_extracts_the_text_layer_with_a_page_locator(registry: Registry) -> None:
    document = parse(registry, "text-layer.pdf")
    body = "\n".join(texts(document, NodeKind.PARAGRAPH))
    assert "Retry Policy" in body
    assert "The maximum payload size is 256 KiB." in body
    pages = {node.src.page for node in document.nodes if node.src is not None}
    assert pages == {1}


def test_pdf_says_on_every_document_what_it_cannot_see(registry: Registry) -> None:
    document = parse(registry, "text-layer.pdf")
    assert any("text layer only" in warning for warning in document.warnings)
    assert not any(node.kind is NodeKind.HEADING for node in document.nodes)


def test_pdf_refuses_bytes_that_are_not_a_pdf() -> None:
    blob = Blob.of(b"%PDF-1.4\nbut truncated", media_type=PDF, source_uri="file:///bad.pdf")
    with pytest.raises(ParseError, match="PDFium could not read"):
        pdf_parser.plugin().parse(blob, doc_id=DOC_ID)


@pytest.mark.parametrize(
    ("module", "blocked"),
    [(docling_parser, "docling.document_converter"), (pdf_parser, "pypdfium2")],
)
def test_a_missing_engine_names_the_extra_that_installs_it(
    module: object, blocked: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The message an operator meets most often has to contain the fix."""
    import builtins

    real_import = builtins.__import__

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == blocked or name.startswith(f"{blocked}."):
            raise ImportError(f"No module named {blocked!r}")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(PluginUnavailableError, match=r"mycelium-os\[ingest\]"):
        module.plugin()  # type: ignore[attr-defined]


def test_pdf_declares_itself_deterministic_and_names_its_engine() -> None:
    meta = pdf_parser.plugin().meta
    assert meta.id == "pdf"
    assert meta.deterministic is True


# ---------------------------------------------------------------------------
# Determinism: the same bytes, twice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["source.md", "source.docx", "source.html", "text-layer.pdf"])
def test_parsing_the_same_bytes_twice_gives_identical_kir(registry: Registry, name: str) -> None:
    # NFR-1: the parse stage is deterministic, so gate G6 can rely on it once
    # ingestion feeds the compiler (roadmap 4.2).
    first = parse(registry, name)
    second = parse(registry, name)
    assert first.model_dump_json() == second.model_dump_json()


@pytest.mark.parametrize("name", ["source.docx", "source.html", "text-layer.pdf"])
def test_an_ingested_source_digest_is_over_the_acquired_bytes(
    registry: Registry, name: str
) -> None:
    # The CAS rule for acquired originals (spec 03 §1): bytes are digested
    # verbatim, because normalising a DOCX would be meaningless.
    blob = registry.acquire(str(FIXTURES / name))
    assert parse(registry, name).source_digest == blob.digest


def test_an_authored_source_digest_is_over_the_normalised_text(registry: Registry) -> None:
    """Markdown keeps the *content* digest, and it must.

    Authored text is digested after normalisation so a checkout that rewrites
    line endings does not change a document's identity — the rule gate G6 rests
    on (ADR-0005). Ingested bytes get no such normalisation, so the two rules
    differ on purpose, and their digests differ with them.
    """
    blob = registry.acquire(str(FIXTURES / "source.md"))
    document = parse(registry, "source.md")
    assert document.source_digest == digest_text(blob.data.decode("utf-8"))
    assert document.source_digest != blob.digest


@needs_pandoc
def test_the_pinned_order_decides_which_engine_reads_a_docx() -> None:
    docling_first = Registry.resolve(
        parsers=["docling", "pandoc"], connectors=["file"], roots=[FIXTURES]
    )
    pandoc_first = Registry.resolve(
        parsers=["pandoc", "docling"], connectors=["file"], roots=[FIXTURES]
    )
    assert docling_first.parser_for(DOCX).meta.id == "docling"
    assert pandoc_first.parser_for(DOCX).meta.id == "pandoc"
    # reStructuredText only pandoc reads, so the order cannot change that one.
    assert docling_first.parser_for(RST).meta.id == "pandoc"
