# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The docling parser — the primary adapter D-007 names, at the weight we can defend.

Docling is the parsing ecosystem this project agreed to wrap rather than rebuild
(D-007), and its declarative backends — DOCX and HTML here — are pure Python:
they read a document's own structure, produce a `DoclingDocument` with heading
nesting, tables addressed by row and column, code language, hyperlink targets and
per-item provenance, and they do it offline, deterministically, with no model
files.

**What this adapter deliberately does not use is docling's PDF pipeline.** That
pipeline is the ML one — a layout model and a table model, ``torch`` and
``transformers`` in the closure, and weights fetched from HuggingFace on first
use. Three project constraints refuse it here and the reasons are measured, not
assumed: NFR-6 forbids a network call unless configured, D-013 makes the default
profile offline, and NFR-1/gate G6 demand byte-identical artifacts across the
Linux/Windows/macOS matrix — which float kernels on three platforms do not
promise. PDF is therefore read by :mod:`mycelium.ingest.parsers.pdf`, its text
layer only, and docling's structural PDF understanding is filed as its own
roadmap item with these constraints as its acceptance criteria (ADR-0032).

The adapter's own job is the usual one: walk docling's tree and emit KIR in the
shape :mod:`mycelium.ingest.parsers.builder` fixes, mapping what maps and making
what does not into an ``opaque`` node rather than a hole.
"""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from typing import Any, Final

from mycelium.ingest.errors import ParseError, PluginUnavailableError
from mycelium.ingest.media import DOCX, HTML
from mycelium.ingest.parsers.builder import KirBuilder
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob, PluginMeta
from mycelium.sdk.types import KirDocument, NodeKind, SrcLocator, Ulid

__all__ = ["PARSER_ID", "DoclingParser", "plugin"]

PARSER_ID: Final = "docling"

_FORMAT_NAMES: Final[dict[str, str]] = {DOCX: "DOCX", HTML: "HTML"}
"""Media type → the :class:`docling.datamodel.base_models.InputFormat` member name.

Names rather than members so this module imports without docling installed: the
registry has to be able to *report* an unavailable parser, which it cannot do if
merely importing the module explodes."""

_EXTENSIONS: Final[dict[str, str]] = {DOCX: "docx", HTML: "html"}

_LABEL_KIND: Final[dict[str, NodeKind]] = {
    "text": NodeKind.PARAGRAPH,
    "paragraph": NodeKind.PARAGRAPH,
    "caption": NodeKind.PARAGRAPH,
    "footnote": NodeKind.FOOTNOTE,
    "formula": NodeKind.EQUATION,
    "code": NodeKind.CODE_BLOCK,
    "list_item": NodeKind.LIST_ITEM,
    "picture": NodeKind.IMAGE,
    "table": NodeKind.TABLE,
    "chart": NodeKind.IMAGE,
    "reference": NodeKind.PARAGRAPH,
}
"""Docling item label → KIR node kind, for the labels the declarative backends emit.

Labels outside this map become opaque nodes. That is the point of the map being
explicit: docling's label vocabulary grows with its backends, and a new label
must be a decision here rather than silently arriving as a paragraph."""

_SKIPPED_LABELS: Final = frozenset({"page_header", "page_footer"})
"""Running headers and footers: page furniture, not document content. Dropped by
policy — which the M4 exit gate counts as *represented*, because the choice is
declared here rather than made by accident."""


class DoclingParser:
    """Adapts docling's declarative backends into KIR."""

    media_types: tuple[str, ...] = tuple(_FORMAT_NAMES)

    def __init__(self, *, converter: Any, formats: dict[str, Any], version: str) -> None:
        self._converter = converter
        self._formats = formats
        self.meta = PluginMeta(
            id=PARSER_ID,
            version=version,
            description="DOCX and HTML structure, via docling's declarative backends.",
        )

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        from docling.datamodel.base_models import DocumentStream

        input_format = self._formats.get(blob.media_type)
        if input_format is None:  # pragma: no cover - the registry dispatches on media_types
            msg = f"{blob.source_uri}: docling has no format pinned for {blob.media_type}"
            raise ParseError(msg)

        name = f"source.{_EXTENSIONS[blob.media_type]}"
        stream = DocumentStream(name=name, stream=BytesIO(blob.data))
        try:
            result = self._converter.convert(stream, raises_on_error=False)
        except Exception as error:  # noqa: BLE001 - a third-party engine on untrusted input
            msg = f"{blob.source_uri}: docling failed to convert - {error}"
            raise ParseError(msg) from error

        status = getattr(result.status, "value", str(result.status))
        if status not in {"success", "partial_success"}:
            detail = "; ".join(str(item) for item in getattr(result, "errors", ()) or ())
            msg = f"{blob.source_uri}: docling reported {status}{f' - {detail}' if detail else ''}"
            raise ParseError(msg)

        builder = KirBuilder()
        if status == "partial_success":
            builder.warn("docling converted this document only partially")
        document = result.document
        state = _Nesting()
        for ref in document.body.children or ():
            _item(builder, ref.resolve(document), document, state, parent=None)
        return KirDocument(
            doc_id=doc_id,
            source_digest=digest_bytes(blob.data),
            nodes=tuple(builder.nodes),
            warnings=(*blob.warnings, *builder.warnings),
        )


# ---------------------------------------------------------------------------
# The tree walk
# ---------------------------------------------------------------------------


@dataclass
class _Nesting:
    """The one fact the walk has to remember: whether a document title was seen.

    Docling numbers section headers from 1 whether or not the document also has a
    title item, so a DOCX whose first heading is "Heading 1" and a Markdown file
    whose first heading is ``#`` must both come out at KIR level 1 — otherwise the
    chunker, which reads level 1 as "this is the document's title" (ADR-0007),
    anchors the two differently and the same content cites differently depending
    on which format it arrived in.
    """

    has_title: bool = False


def _item(  # noqa: C901
    builder: KirBuilder, item: Any, document: Any, state: _Nesting, *, parent: str | None
) -> None:
    """Emit one docling item and its subtree."""
    label = str(getattr(getattr(item, "label", None), "value", "") or "")
    kind = type(item).__name__

    if label in _SKIPPED_LABELS:
        return

    if kind == "InlineGroup":
        # docling splits a run of differently-formatted text into sibling items;
        # KIR stores one paragraph, because that is the unit a reader cites.
        runs = [str(getattr(ref.resolve(document), "text", "")) for ref in item.children]
        node_id = builder.add(
            NodeKind.PARAGRAPH, parent=parent, text=_join_runs(runs), src=_src(item)
        )
        _links(builder, item, document, node_id)
        return

    if kind in {"ListGroup", "OrderedList", "UnorderedList"}:
        ordered = bool(getattr(item, "enumerated", False)) or kind == "OrderedList"
        node_id = builder.add(
            NodeKind.LIST, parent=parent, variant="ordered" if ordered else "bullet"
        )
        _children(builder, item, document, state, parent=node_id)
        return

    if kind == "GroupItem":
        _children(builder, item, document, state, parent=parent)
        return

    if label == "title":
        state.has_title = True
        node_id = builder.add(
            NodeKind.HEADING, parent=parent, text=item.text, level=1, src=_src(item)
        )
        _children(builder, item, document, state, parent=node_id)
        return

    if label == "section_header":
        depth = max(1, int(getattr(item, "level", 1))) + (1 if state.has_title else 0)
        node_id = builder.add(
            NodeKind.HEADING, parent=parent, text=item.text, level=min(6, depth), src=_src(item)
        )
        _children(builder, item, document, state, parent=node_id)
        return

    if label == "table":
        _table(builder, item, parent=parent)
        _children(builder, item, document, state, parent=parent)
        return

    mapped = _LABEL_KIND.get(label)
    if mapped is None:
        _opaque(builder, item, parent=parent, note=f"docling {label or kind}")
        _children(builder, item, document, state, parent=parent)
        return

    lang: str | None = None
    if mapped is NodeKind.CODE_BLOCK:
        language = getattr(getattr(item, "code_language", None), "value", None)
        if language and language != "unknown":
            lang = str(language)
    target = str(getattr(item, "self_ref", "")) if mapped is NodeKind.IMAGE else None

    node_id = builder.add(
        mapped,
        parent=parent,
        text=str(getattr(item, "text", "") or ""),
        src=_src(item),
        lang=lang,
        target=target,
    )
    _links(builder, item, document, node_id)
    _children(builder, item, document, state, parent=node_id)


_NO_SPACE_BEFORE: Final = frozenset(".,;:!?)]}%»…’”")
_NO_SPACE_AFTER: Final = frozenset("([{$#@/«“‘")


def _join_runs(runs: list[str]) -> str:
    """Rejoin docling's formatting runs into one paragraph, restoring the spaces.

    docling strips whitespace at a run boundary, in ``text`` and ``orig`` alike:
    a sentence with a link in it comes back as three items whose concatenation
    reads ``...and thedelivery logrecords...``. The whitespace is gone from the
    input, so it has to be reconstructed, and a single space between runs is
    right everywhere except next to punctuation that binds to its neighbour —
    which is what the two sets below name. The alternative, joining with nothing,
    is not neutral: it corrupts every sentence containing emphasis or a link.
    """
    out = ""
    for run in runs:
        if not run:
            continue
        needs_space = (
            out
            and not out[-1].isspace()
            and not run[0].isspace()
            and run[0] not in _NO_SPACE_BEFORE
            and out[-1] not in _NO_SPACE_AFTER
        )
        out += " " + run if needs_space else run
    return out


def _children(
    builder: KirBuilder, item: Any, document: Any, state: _Nesting, *, parent: str | None
) -> None:
    for ref in getattr(item, "children", None) or ():
        _item(builder, ref.resolve(document), document, state, parent=parent)


def _links(builder: KirBuilder, item: Any, document: Any, parent: str) -> None:
    """Emit a link node when the item carries a hyperlink — an edge source (spec 03 §6)."""
    target = getattr(item, "hyperlink", None)
    if target is not None:
        builder.add(
            NodeKind.LINK,
            parent=parent,
            text=str(getattr(item, "text", "") or ""),
            target=str(target),
        )
    for ref in getattr(item, "children", None) or ():
        child = ref.resolve(document)
        if getattr(child, "hyperlink", None) is not None:
            builder.add(
                NodeKind.LINK,
                parent=parent,
                text=str(getattr(child, "text", "") or ""),
                target=str(child.hyperlink),
            )


def _table(builder: KirBuilder, item: Any, *, parent: str | None) -> None:
    """Emit a docling table as table → row → cell, addressed by its own grid."""
    table_id = builder.add(NodeKind.TABLE, parent=parent, src=_src(item))
    data = getattr(item, "data", None)
    cells = list(getattr(data, "table_cells", ()) or ())
    if not cells:
        return
    rows: dict[int, list[Any]] = {}
    for cell in cells:
        rows.setdefault(int(cell.start_row_offset_idx), []).append(cell)
    for index in sorted(rows):
        row = sorted(rows[index], key=lambda cell: int(cell.start_col_offset_idx))
        header = all(bool(getattr(cell, "column_header", False)) for cell in row)
        row_id = builder.add(
            NodeKind.TABLE_ROW, parent=table_id, variant="header" if header else "body"
        )
        for cell in row:
            builder.add(NodeKind.TABLE_CELL, parent=row_id, text=str(cell.text or ""))


def _opaque(builder: KirBuilder, item: Any, *, parent: str | None, note: str) -> None:
    """Record an item this adapter does not map, rather than dropping it."""
    payload = str(getattr(item, "self_ref", "")) + "\n" + str(getattr(item, "text", "") or "")
    builder.add(
        NodeKind.OPAQUE,
        parent=parent,
        media_type="application/x-docling-item+json",
        blob=digest_bytes(payload.encode("utf-8")),
        note=note,
    )
    builder.warn(f"{note} kept as an opaque node")


def _src(item: Any) -> SrcLocator | None:
    """Map docling provenance onto a KIR source locator, when it has any.

    Only the first provenance entry is used: KIR's locator is "the smallest
    practical unit the connector can provide" (spec 03 §4), a single place, and an
    item spanning two pages is cited from where it starts. The box is normalised
    to ``(x0, y0, x1, y1)`` with ``min``/``max`` so it stays ordered whichever
    coordinate origin the backend used.
    """
    provenance = list(getattr(item, "prov", None) or ())
    if not provenance:
        return None
    first = provenance[0]
    page = getattr(first, "page_no", None)
    box = getattr(first, "bbox", None)
    bbox: tuple[float, float, float, float] | None = None
    if box is not None:
        left, right = sorted((float(box.l), float(box.r)))
        bottom, top = sorted((float(box.b), float(box.t)))
        bbox = (left, bottom, right, top)
    if page is None and bbox is None:
        return None
    return SrcLocator(page=int(page) if page is not None else None, bbox=bbox)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def _engine_version() -> str:
    for distribution in ("docling", "docling-slim"):
        try:
            return version(distribution)
        except PackageNotFoundError:
            continue
    return "unknown"  # pragma: no cover - one of the two is installed if the import worked


def plugin() -> DoclingParser:
    """Build the parser, or raise :class:`PluginUnavailableError` naming what is missing."""
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter
    except ImportError as error:
        msg = (
            f"the {PARSER_ID!r} parser needs docling; install it with "
            f"`pip install 'mycelium-os[ingest]'` or drop {PARSER_ID!r} from [ingest] parsers "
            f"({error})"
        )
        raise PluginUnavailableError(msg) from error

    formats = {media: getattr(InputFormat, name) for media, name in _FORMAT_NAMES.items()}
    # `allowed_formats` is a fence, not an optimisation: it is what guarantees a
    # PDF handed to this parser is refused rather than reaching for the ML
    # pipeline this adapter deliberately does not ship.
    converter = DocumentConverter(allowed_formats=list(formats.values()))
    return DoclingParser(converter=converter, formats=formats, version=_engine_version())
