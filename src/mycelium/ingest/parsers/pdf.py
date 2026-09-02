# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The PDF parser — PDFium's text layer, and nothing it cannot honestly claim.

PDF has no fallback: pandoc does not read it, and docling reads it only through
the ML pipeline this project declines to ship by default (see
:mod:`mycelium.ingest.parsers.docling` and ADR-0032). So PDF is served here by
adapting **PDFium** — Chrome's PDF engine, via `pypdfium2` — which extracts the
text layer a PDF already carries, deterministically, offline, with no models.

What that buys and what it does not, stated plainly because a fidelity report
(roadmap 4.3) has to be able to repeat it:

- **Buys:** every character of the text layer, in the page's own content order,
  with a page number on every node, so a citation lands on a page.
- **Does not buy:** headings, tables, lists, reading order across columns, or
  anything from a scanned page with no text layer. Those are what layout analysis
  is *for*. A document parsed here is a sequence of page-scoped paragraphs, and
  the KIR warnings say so on every document rather than in a footnote nobody
  reads.
- **A page with no text layer** yields no nodes and one warning naming the page.
  It is not an error: a PDF of scans is a real document that this parser cannot
  read, and the honest output is an empty document that says why — which the loss
  budget (roadmap 4.3) can then act on.

Paragraphs are split on blank lines, the one structural signal a text layer
carries reliably. Nothing else is inferred; a heuristic that guessed headings
from font size would be layout analysis by another name, done worse.
"""

from importlib.metadata import PackageNotFoundError, version
from typing import Any, Final

from mycelium.ingest.errors import ParseError, PluginUnavailableError
from mycelium.ingest.media import PDF
from mycelium.ingest.parsers.builder import KirBuilder
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob, PluginMeta
from mycelium.sdk.types import KirDocument, NodeKind, OpaqueDisposition, SrcLocator, Ulid

__all__ = ["PARSER_ID", "PdfParser", "plugin"]

PARSER_ID: Final = "pdf"

_STRUCTURE_NOTICE: Final = (
    "PDF text layer only: no headings, tables or reading-order analysis "
    "(ADR-0032, and ADR-0040 for what the alternative was measured to cost)"
)


class PdfParser:
    """Adapts PDFium's per-page text layer into KIR."""

    media_types: tuple[str, ...] = (PDF,)

    def __init__(self, *, version: str) -> None:
        self.meta = PluginMeta(
            id=PARSER_ID,
            version=version,
            description="PDF text layer, page by page, via PDFium (pypdfium2).",
        )

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        import pypdfium2

        builder = KirBuilder()
        builder.warn(_STRUCTURE_NOTICE)
        document: Any = None
        try:
            document = pypdfium2.PdfDocument(blob.data)
            page_count = len(document)
            for number in range(page_count):
                _page(builder, document[number], number + 1)
        except ParseError:
            raise
        except Exception as error:  # noqa: BLE001 - a C engine on untrusted input
            msg = f"{blob.source_uri}: PDFium could not read this document - {error}"
            raise ParseError(msg) from error
        finally:
            if document is not None:
                document.close()

        return KirDocument(
            doc_id=doc_id,
            source_digest=digest_bytes(blob.data),
            nodes=tuple(builder.nodes),
            warnings=(*blob.warnings, *builder.warnings),
        )


def _page(builder: KirBuilder, page: Any, number: int) -> None:
    """Emit one page's paragraphs, or record that it has no text layer."""
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_range()
    finally:
        textpage.close()

    paragraphs = [block.strip() for block in text.replace("\r\n", "\n").split("\n\n")]
    paragraphs = [block for block in paragraphs if block]
    if not paragraphs:
        # A page whose content did not survive at all. An opaque node rather than
        # only a warning, because this is what the loss budget has to be able to
        # count: a scanned PDF is 100 % lost, and projecting an empty evidence
        # document from it would be exactly the silent failure the M4 exit gate
        # forbids (ADR-0034).
        builder.opaque(
            f"page {number} has no text layer",
            disposition=OpaqueDisposition.LOST,
            media_type=PDF,
            src=SrcLocator(page=number),
        )
        return
    for block in paragraphs:
        builder.add(NodeKind.PARAGRAPH, text=block, src=SrcLocator(page=number))


def plugin() -> PdfParser:
    """Build the parser, or raise :class:`PluginUnavailableError` naming what is missing."""
    try:
        import pypdfium2  # noqa: F401 - imported to prove the engine is installed
    except ImportError as error:
        msg = (
            f"the {PARSER_ID!r} parser needs pypdfium2; install it with "
            f"`pip install 'mycelium-os[ingest]'` or drop {PARSER_ID!r} from [ingest] parsers "
            f"({error})"
        )
        raise PluginUnavailableError(msg) from error
    try:
        engine = version("pypdfium2")
    except PackageNotFoundError:  # pragma: no cover - it was just imported
        engine = "unknown"
    return PdfParser(version=engine)
