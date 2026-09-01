# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The evidence projection (roadmap 4.3).

The load-bearing test is
:func:`test_no_node_text_is_lost_in_the_projection`: every KIR node's text survives into
the projected Markdown, through all four engines. It is the chunker's no-content-loss
invariant (ADR-0007) transplanted onto the projector, and it is the only reason the word
"verbatim" in spec 02 §5 means anything.

The second thing asserted here is that the projection is a *document*, not a dump: the
compiler must read it back as an ingested evidence document with the provenance the
frontmatter contract allows, and no more.
"""

import shutil
from pathlib import Path, PurePosixPath

import pytest

from mycelium.ingest import Registry, ingest_source
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.ingest.projection import evidence_path, project
from mycelium.markdown.adapter import parse_markdown
from mycelium.markdown.frontmatter import FIELD_OWNERS, parse_frontmatter
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.types import (
    KirDocument,
    KirNode,
    NodeKind,
    OpaqueDisposition,
    ProvenanceOrigin,
    SourceTrust,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
DIGEST = digest_bytes(b"the source bytes")

HAVE_PANDOC = shutil.which(pandoc_parser.DEFAULT_EXECUTABLE) is not None
ENGINES = ["source.md", "source.docx", "source.html", "text-layer.pdf"] + (
    ["source.rst"] if HAVE_PANDOC else []
)


@pytest.fixture(scope="module")
def registry() -> Registry:
    names = ["markdown", "docling", "pdf"] + (["pandoc"] if HAVE_PANDOC else [])
    return Registry.resolve(parsers=names, connectors=["file"], roots=[FIXTURES])


def kir(*nodes: KirNode, warnings: tuple[str, ...] = ()) -> KirDocument:
    return KirDocument(doc_id=DOC_ID, source_digest=DIGEST, nodes=nodes, warnings=warnings)


def node(ordinal: int, kind: NodeKind, **fields: object) -> KirNode:
    return KirNode(id=f"n{ordinal + 1}", kind=kind, ord=ordinal, **fields)  # type: ignore[arg-type]


def rendered(document: KirDocument) -> str:
    return project(document, source_uri="file:///x.pdf", source_digest=DIGEST).text


# ---------------------------------------------------------------------------
# The invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ENGINES)
def test_no_node_text_is_lost_in_the_projection(name: str, registry: Registry) -> None:
    """Every engine's KIR survives the round-trip through Markdown.

    Asserted as containment rather than equality: the projector regenerates
    *syntax*, so the reparsed node list will not match node for node. What must
    match is the text — that is what a verbatim quote rests on.
    """
    blob = registry.acquire(str(FIXTURES / name))
    original = registry.parse(blob, doc_id=DOC_ID)
    projection = project(original, source_uri=blob.source_uri, source_digest=blob.digest)

    reparsed = parse_markdown(projection.text, doc_id=DOC_ID).kir
    body = "\n".join(item.text or "" for item in reparsed.nodes)
    lost = [
        item.text
        for item in original.nodes
        if item.text and item.text.strip() and item.text.strip() not in body
    ]
    assert lost == [], f"{name} lost text in projection"


@pytest.mark.parametrize("name", ENGINES)
def test_the_projection_reparses_as_an_ingested_evidence_document(
    name: str, registry: Registry
) -> None:
    blob = registry.acquire(str(FIXTURES / name))
    projection = project(
        registry.parse(blob, doc_id=DOC_ID),
        source_uri=blob.source_uri,
        source_digest=blob.digest,
    )
    frontmatter = parse_frontmatter(projection.text).frontmatter
    assert frontmatter.origin is ProvenanceOrigin.INGESTED
    assert frontmatter.source == blob.source_uri
    assert frontmatter.source_digest == blob.digest
    assert frontmatter.mycelium_id is None, "identity belongs to `mycelium build`"
    assert frontmatter.properties == {}, "nothing outside the contract"


def test_frontmatter_writes_only_fields_the_contract_gives_to_ingest() -> None:
    text = project(
        kir(node(0, NodeKind.HEADING, level=1, text="Title")),
        source_uri="file:///x.pdf",
        source_digest=DIGEST,
        source_trust=SourceTrust.HIGH,
    ).text
    block = text.split("---")[1]
    keys = {line.split(":", 1)[0] for line in block.strip().splitlines()}
    owners = {FIELD_OWNERS[key] for key in keys}
    assert owners <= {"mycelium ingest", "human"}
    assert "mycelium_id" not in keys
    assert "status" not in keys, "verification status is the folder's (D-021)"


def test_source_trust_is_written_when_it_is_known_and_omitted_when_not() -> None:
    with_trust = project(
        kir(node(0, NodeKind.PARAGRAPH, text="t")),
        source_uri="file:///x.pdf",
        source_digest=DIGEST,
        source_trust=SourceTrust.MEDIUM,
    ).text
    without = rendered(kir(node(0, NodeKind.PARAGRAPH, text="t")))
    assert "source_trust: medium" in with_trust
    assert "source_trust" not in without, "an absent field is never invented"


# ---------------------------------------------------------------------------
# Where it lands
# ---------------------------------------------------------------------------


def test_the_path_is_readable_and_under_the_evidence_folder() -> None:
    path = evidence_path("file:///docs/Retry%20Policy.PDF", digest=DIGEST)
    assert path.parts[:2] == ("knowledge", "evidence")
    assert path.name.startswith("retry-20policy-pdf-")
    assert path.suffix == ".md"


def test_two_sources_with_the_same_name_do_not_collide() -> None:
    first = evidence_path("file:///a/report.pdf", digest=digest_bytes(b"one"))
    second = evidence_path("file:///b/report.pdf", digest=digest_bytes(b"two"))
    assert first != second
    assert first.name.startswith("report-pdf-")


def test_the_knowledge_directory_is_honoured() -> None:
    path = evidence_path("file:///x.pdf", knowledge_dir="docs", digest=DIGEST)
    assert path.parts[0] == "docs"
    assert isinstance(path, PurePosixPath)


# ---------------------------------------------------------------------------
# Rendering, kind by kind
# ---------------------------------------------------------------------------


def test_headings_keep_their_level() -> None:
    text = rendered(
        kir(
            node(0, NodeKind.HEADING, level=1, text="One"),
            node(1, NodeKind.HEADING, level=3, text="Three"),
        )
    )
    assert "# One" in text
    assert "### Three" in text


def test_a_table_becomes_a_gfm_table_with_a_header_rule() -> None:
    text = rendered(
        kir(
            node(0, NodeKind.TABLE),
            node(1, NodeKind.TABLE_ROW, parent="n1", variant="header"),
            node(2, NodeKind.TABLE_CELL, parent="n2", text="a"),
            node(3, NodeKind.TABLE_CELL, parent="n2", text="b"),
            node(4, NodeKind.TABLE_ROW, parent="n1", variant="body"),
            node(5, NodeKind.TABLE_CELL, parent="n5", text="1"),
            node(6, NodeKind.TABLE_CELL, parent="n5", text="2"),
        )
    )
    assert "| a | b |" in text
    assert "| --- | --- |" in text
    assert "| 1 | 2 |" in text


def test_a_pipe_inside_a_cell_is_escaped() -> None:
    text = rendered(
        kir(
            node(0, NodeKind.TABLE),
            node(1, NodeKind.TABLE_ROW, parent="n1", variant="header"),
            node(2, NodeKind.TABLE_CELL, parent="n2", text="a|b"),
        )
    )
    assert r"a\|b" in text


def test_a_code_block_keeps_its_language_and_gets_a_long_enough_fence() -> None:
    text = rendered(kir(node(0, NodeKind.CODE_BLOCK, lang="python", text="x = 1")))
    assert "```python" in text
    nested = rendered(kir(node(0, NodeKind.CODE_BLOCK, text="```\ninner\n```")))
    # A fence shorter than the content's own would end the block early and turn
    # the rest of the document into code.
    assert "````" in nested


def test_a_quote_is_quoted_once() -> None:
    text = rendered(
        kir(
            node(0, NodeKind.QUOTE),
            node(1, NodeKind.PARAGRAPH, parent="n1", text="quoted line"),
        )
    )
    assert "> quoted line" in text
    assert text.count("quoted line") == 1, "the paragraph must not also render as prose"


def test_a_callout_keeps_its_type_and_title() -> None:
    text = rendered(
        kir(
            node(0, NodeKind.CALLOUT, variant="warning", title="Careful"),
            node(1, NodeKind.PARAGRAPH, parent="n1", text="body"),
        )
    )
    assert "> [!warning] Careful" in text
    assert "> body" in text


def test_a_nested_list_is_indented() -> None:
    text = rendered(
        kir(
            node(0, NodeKind.LIST, variant="bullet"),
            node(1, NodeKind.LIST_ITEM, parent="n1", text="outer"),
            node(2, NodeKind.LIST, parent="n2", variant="ordered"),
            node(3, NodeKind.LIST_ITEM, parent="n3", text="inner"),
        )
    )
    assert "- outer" in text
    assert "    1. inner" in text


def test_an_equation_is_a_display_block() -> None:
    assert "$$\ne = mc^2\n$$" in rendered(kir(node(0, NodeKind.EQUATION, text="e = mc^2")))


# ---------------------------------------------------------------------------
# Loss is visible in the document a person reads
# ---------------------------------------------------------------------------


def test_a_lost_element_becomes_a_missing_callout() -> None:
    text = rendered(
        kir(
            node(
                0,
                NodeKind.OPAQUE,
                variant=OpaqueDisposition.LOST.value,
                note="page 2 has no text layer",
            )
        )
    )
    # Profile v1 syntax, so it is visible in Obsidian, atomic in the chunker, and
    # impossible to mistake for the document's own prose.
    assert "> [!missing] page 2 has no text layer" in text


def test_a_degraded_element_keeps_its_payload_under_a_warning_callout() -> None:
    text = rendered(
        kir(
            node(
                0,
                NodeKind.OPAQUE,
                variant=OpaqueDisposition.DEGRADED.value,
                note="pandoc RawBlock",
                text="<marquee>legacy</marquee>",
            )
        )
    )
    assert "> [!warning] pandoc RawBlock" in text
    assert "> <marquee>legacy</marquee>" in text


def test_an_empty_document_projects_to_frontmatter_alone() -> None:
    text = rendered(kir())
    assert text.strip().endswith("---")
    assert parse_frontmatter(text).frontmatter.origin is ProvenanceOrigin.INGESTED


# ---------------------------------------------------------------------------
# The frontmatter is valid YAML whatever the source URI contains
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    [
        "file:///plain.pdf",
        "file:///with spaces.pdf",
        "https://example.com:8443/a?b=c#d",
        "file:///quotes'and\".pdf",
        "file:///braces{}.pdf",
    ],
)
def test_any_source_uri_round_trips_through_frontmatter(uri: str) -> None:
    text = project(
        kir(node(0, NodeKind.PARAGRAPH, text="t")), source_uri=uri, source_digest=DIGEST
    ).text
    assert parse_frontmatter(text).frontmatter.source == uri


def test_a_title_taken_from_the_first_heading() -> None:
    projection = project(
        kir(node(0, NodeKind.HEADING, level=1, text="Retry Policy")),
        source_uri="file:///r.pdf",
        source_digest=DIGEST,
    )
    assert projection.title == "Retry Policy"


def test_a_document_with_no_heading_is_titled_by_its_filename() -> None:
    projection = project(
        kir(node(0, NodeKind.PARAGRAPH, text="prose")),
        source_uri="file:///scans/report.pdf",
        source_digest=DIGEST,
    )
    assert projection.title == "report.pdf"


# ---------------------------------------------------------------------------
# Untrusted content cannot forge an assertion (D-017, spec 03 §6)
# ---------------------------------------------------------------------------


def test_a_projection_cannot_forge_an_authored_wikilink(tmp_path: Path) -> None:
    """The projector skips reference nodes, and that is what closes this hole.

    A source that says `see [[secrets]]` must not become a document asserting an
    `authored` link to `secrets`: spec 03 §6's assertion discipline is that
    extracted never becomes authored silently, and a wikilink in a projected file
    would compile to an authored edge because the compiler cannot tell who wrote
    it. KIR keeps a wikilink's *display text* inside its parent paragraph and the
    link itself as a separate reference node, and the projector renders only
    section-level, non-reference nodes — so the syntax is gone and the words
    remain (ADR-0034).
    """
    source = "# Report\n\nPlease see [[secrets]] for details.\n"
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    (tmp_path / "hostile.md").write_text(source, encoding="utf-8")

    result = ingest_source(
        tmp_path / ".mycelium", registry, str(tmp_path / "hostile.md"), doc_id=DOC_ID
    )
    text = result.projection.text
    assert "Please see secrets for details." in text
    assert "[[" not in text, "wikilink syntax must not survive into the authored tree"
    assert "![[" not in text


def test_a_projection_keeps_no_embed_syntax_either(tmp_path: Path) -> None:
    source = "# Report\n\nSee ![[private-note]] and [[other|a label]].\n"
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    (tmp_path / "hostile.md").write_text(source, encoding="utf-8")
    result = ingest_source(
        tmp_path / ".mycelium", registry, str(tmp_path / "hostile.md"), doc_id=DOC_ID
    )
    assert "[[" not in result.projection.text
    # The label a reader would have seen is still there; only the assertion is gone.
    assert "a label" in result.projection.text
