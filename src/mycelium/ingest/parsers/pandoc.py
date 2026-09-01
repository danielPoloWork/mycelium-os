# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The pandoc parser — the fallback, and the widest reader we have (D-007).

Pandoc is one static binary with no Python closure, no model files, and no
network. It reads DOCX, HTML, ODT, EPUB, reStructuredText and LaTeX, and it
cannot read PDF — which is exactly the division of labour architecture §5
describes when it calls pandoc the fallback.

**We read its AST, not its Markdown.** The obvious cheap adapter is
``pandoc --to gfm`` piped into the Markdown adapter that already exists. It is
rejected here: pandoc's Markdown writer silently flattens what GFM cannot express
— definition lists, line blocks, raw blocks, spans — and the M4 exit gate is
*zero silent element loss*. The JSON AST names every construct, so an element
this adapter cannot map becomes a KIR ``opaque`` node carrying the constructor's
name (spec 03 §4's lawful escape hatch, F-3) instead of dissolving into prose.

**The subprocess is fenced.** ``--sandbox`` restricts pandoc's IO to what it is
handed, the bytes go in over stdin so no path is ever passed to a shell, the
argument vector is fixed (never a string), and a timeout bounds the run.
Untrusted input stays untrusted all the way down (D-017).

**What the AST does not carry is source positions.** Pandoc's JSON has no line or
byte offsets, so every node this parser emits has ``src = None``. That is a real
fidelity cost — an ingested DOCX cites by anchor, never by line — and it is
stated rather than papered over; docling's provenance is the answer where it is
available (:mod:`mycelium.ingest.parsers.docling`).
"""

import json
import shutil
import subprocess
from typing import Any, Final

from mycelium.ingest.errors import ParseError, PluginUnavailableError
from mycelium.ingest.media import DOCX, EPUB, HTML, LATEX, ODT, RST
from mycelium.ingest.parsers.builder import KirBuilder
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob, PluginMeta
from mycelium.sdk.types import KirDocument, NodeKind, OpaqueDisposition, Ulid

__all__ = ["DEFAULT_EXECUTABLE", "PARSER_ID", "READERS", "PandocParser", "plugin"]

PARSER_ID: Final = "pandoc"

DEFAULT_EXECUTABLE: Final = "pandoc"
DEFAULT_TIMEOUT_S: Final = 120.0

READERS: Final[dict[str, str]] = {
    DOCX: "docx",
    HTML: "html",
    ODT: "odt",
    EPUB: "epub",
    RST: "rst",
    LATEX: "latex",
}
"""Media type → pandoc reader name.

Pandoc reads three dozen more formats. Each entry here is one this repository has
a fixture for, so widening the set is a line plus a fixture rather than an
untested claim."""

_MAX_DEPTH: Final = 256
"""How deeply the block walk will descend, matching `safety.Limits.max_depth`."""

_MIN_MAJOR: Final = 3
"""``--sandbox`` arrived in pandoc 3. Refusing 2.x is refusing to run an untrusted
document through an unfenced converter."""

_INLINE_MARKUP: Final = frozenset(
    {"Emph", "Strong", "Underline", "Strikeout", "Superscript", "Subscript", "SmallCaps"}
)
_INLINE_WRAPPED: Final = frozenset({"Quoted", "Span", "Cite"})
_WHITESPACE: Final = {"Space": " ", "SoftBreak": "\n", "LineBreak": "\n"}
_RAW_MEDIA: Final = {"RawBlock": "text/plain", "RawInline": "text/plain"}
"""An opaque node's media type: the raw constructs carry literal source text; a
structured constructor we could not map is described by its AST shape."""


class PandocParser:
    """Adapts pandoc's JSON AST into KIR."""

    media_types: tuple[str, ...] = tuple(READERS)

    def __init__(self, *, executable: str, version: str, timeout_s: float) -> None:
        self._executable = executable
        self._timeout_s = timeout_s
        self.meta = PluginMeta(
            id=PARSER_ID,
            version=version,
            description="DOCX, HTML, ODT, EPUB, reStructuredText and LaTeX, via pandoc.",
        )

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        reader = READERS.get(blob.media_type)
        if reader is None:  # pragma: no cover - the registry dispatches on media_types
            msg = f"{blob.source_uri}: pandoc has no reader pinned for {blob.media_type}"
            raise ParseError(msg)

        document = self._run(blob, reader)
        blocks = document.get("blocks")
        if not isinstance(blocks, list):
            msg = f"{blob.source_uri}: pandoc returned a document with no block list"
            raise ParseError(msg)

        builder = KirBuilder()
        try:
            for block in blocks:
                _block(builder, block, parent=None)
        except RecursionError as error:  # pragma: no cover - _MAX_DEPTH bites first
            msg = f"{blob.source_uri}: pandoc's document tree is nested too deeply to walk"
            raise ParseError(msg) from error
        return KirDocument(
            doc_id=doc_id,
            source_digest=digest_bytes(blob.data),
            nodes=tuple(builder.nodes),
            warnings=(*blob.warnings, *builder.warnings),
        )

    def _run(self, blob: Blob, reader: str) -> dict[str, Any]:
        """Convert `blob` to pandoc's JSON AST in a fenced subprocess."""
        argv = [self._executable, "--sandbox", "--from", reader, "--to", "json"]
        try:
            # Fixed argument vector, no shell, sandboxed reader, bounded runtime.
            completed = subprocess.run(
                argv,
                input=blob.data,
                capture_output=True,
                timeout=self._timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            msg = f"{blob.source_uri}: pandoc did not finish within {self._timeout_s:.0f}s"
            raise ParseError(msg) from error
        except OSError as error:  # pragma: no cover - the binary is probed at plugin() time
            msg = f"{blob.source_uri}: pandoc could not be run - {error}"
            raise ParseError(msg) from error

        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            msg = f"{blob.source_uri}: pandoc exited {completed.returncode} - {detail}"
            raise ParseError(msg)
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            msg = f"{blob.source_uri}: pandoc emitted output that is not JSON - {error}"
            raise ParseError(msg) from error
        except RecursionError as error:
            # Measured: HTML nested 1 000 elements deep blows the decoder's stack
            # (ADR-0033). `mycelium.ingest.safety` refuses such a document before
            # pandoc is ever run, so reaching here means a format whose depth the
            # pre-scan does not bound — and a hostile document must still fail as
            # one document, never as an unhandled exception.
            msg = f"{blob.source_uri}: pandoc's output is nested too deeply to decode"
            raise ParseError(msg) from error
        if not isinstance(parsed, dict):
            msg = f"{blob.source_uri}: pandoc emitted {type(parsed).__name__}, not a document"
            raise ParseError(msg)
        return parsed


# ---------------------------------------------------------------------------
# The AST walk. Pandoc's JSON is `{"t": <constructor>, "c": <contents>}`.
# ---------------------------------------------------------------------------


def _tag(node: object) -> str:
    """The constructor name of an AST node, or ``""`` for anything else."""
    if isinstance(node, dict):
        tag = node.get("t")
        if isinstance(tag, str):
            return tag
    return ""


def _contents(node: object) -> Any:
    """The contents of an AST node — shape depends on the constructor."""
    return node.get("c") if isinstance(node, dict) else None


def _block(  # noqa: C901
    builder: KirBuilder, block: object, *, parent: str | None, depth: int = 0
) -> None:
    """Emit one pandoc block.

    One branch per constructor, and the final fall-through is an opaque node: a
    construct this adapter does not know is *recorded*, never skipped.

    `depth` is the adapter's own bound on the walk. Relying on the interpreter's
    stack limit would make the failure a `RecursionError` from an arbitrary frame
    instead of a document-level refusal that names what was wrong (ADR-0033).
    """
    if depth > _MAX_DEPTH:
        msg = f"pandoc document nests deeper than {_MAX_DEPTH} blocks"
        raise ParseError(msg)
    tag = _tag(block)
    content = _contents(block)

    if tag == "Header":
        level, _attr, inlines = content
        builder.add_heading(int(level), _inline_text(inlines))
        _references(builder, inlines, builder.open_heading)
        return

    if tag in {"Para", "Plain"}:
        node_id = builder.add(NodeKind.PARAGRAPH, parent=parent, text=_inline_text(content))
        _references(builder, content, node_id)
        return

    if tag == "CodeBlock":
        (_ident, classes, _kv), text = content
        builder.add(
            NodeKind.CODE_BLOCK,
            parent=parent,
            text=str(text),
            lang=str(classes[0]) if classes else None,
        )
        return

    if tag in {"BulletList", "OrderedList"}:
        ordered = tag == "OrderedList"
        items = content[1] if ordered else content
        list_id = builder.add(
            NodeKind.LIST, parent=parent, variant="ordered" if ordered else "bullet"
        )
        for item in items:
            _list_item(builder, item, parent=list_id, depth=depth + 1)
        return

    if tag == "DefinitionList":
        _definition_list(builder, content, parent=parent, depth=depth)
        return

    if tag == "BlockQuote":
        quote_id = builder.add(NodeKind.QUOTE, parent=parent)
        for child in content:
            _block(builder, child, parent=quote_id, depth=depth + 1)
        return

    if tag == "Table":
        _table(builder, content, parent=parent, depth=depth)
        return

    if tag == "Figure":
        _attr, caption, blocks = content
        for child in blocks:
            _block(builder, child, parent=parent, depth=depth + 1)
        _caption(builder, caption, parent=parent, depth=depth)
        return

    if tag == "Div":
        for child in content[1]:
            _block(builder, child, parent=parent, depth=depth + 1)
        return

    if tag == "LineBlock":
        for line in content:
            builder.add(NodeKind.PARAGRAPH, parent=parent, text=_inline_text(line))
        builder.warn("line blocks became paragraphs; their hard line breaks are lost")
        return

    if tag == "HorizontalRule":
        return  # a thematic break carries no content; dropping it loses nothing (ADR-0006)

    _opaque(builder, tag, content, parent=parent)


def _list_item(builder: KirBuilder, item: object, *, parent: str, depth: int = 0) -> None:
    """Emit a list item; its leading paragraph becomes the item's own text."""
    blocks = list(item) if isinstance(item, list) else []
    text = ""
    lead: object | None = None
    if blocks and _tag(blocks[0]) in {"Plain", "Para"}:
        lead = blocks.pop(0)
        text = _inline_text(_contents(lead))
    item_id = builder.add(NodeKind.LIST_ITEM, parent=parent, text=text)
    if lead is not None:
        _references(builder, _contents(lead), item_id)
    for child in blocks:
        _block(builder, child, parent=item_id, depth=depth + 1)


def _definition_list(
    builder: KirBuilder, content: object, *, parent: str | None, depth: int = 0
) -> None:
    """Emit a definition list as a list, and say what that representation drops.

    KIR's list variants are ``bullet`` and ``ordered`` (ADR-0006); a
    ``definition`` variant is a schema event, not an adapter's choice. So the
    terms survive as item text, the definitions as the item's blocks, and the
    warning records that the two roles are no longer distinguishable.
    """
    list_id = builder.add(NodeKind.LIST, parent=parent, variant="bullet")
    builder.warn("definition lists became lists; the term/definition roles are lost")
    if not isinstance(content, list):  # pragma: no cover - pandoc always emits a list
        return
    for entry in content:
        term, definitions = entry
        item_id = builder.add(NodeKind.LIST_ITEM, parent=list_id, text=_inline_text(term))
        _references(builder, term, item_id)
        for definition in definitions:
            for child in definition:
                _block(builder, child, parent=item_id, depth=depth + 1)


def _caption(builder: KirBuilder, caption: object, *, parent: str | None, depth: int = 0) -> None:
    """Emit a table's or figure's caption blocks, which are content like any other."""
    if not isinstance(caption, list) or len(caption) != 2:  # pragma: no cover - fixed shape
        return
    for child in caption[1]:
        _block(builder, child, parent=parent, depth=depth + 1)


def _table(builder: KirBuilder, content: Any, *, parent: str | None, depth: int = 0) -> None:
    """Emit a pandoc Table as table → row → cell, with header rows marked.

    The caption is emitted *before* the table rather than inside it: the chunker
    treats a table as an atomic chunk (ADR-0007), and a caption is prose that
    belongs with the surrounding section, not inside the grid.
    """
    _attr, caption, _colspecs, head, bodies, foot = content
    _caption(builder, caption, parent=parent, depth=depth)
    table_id = builder.add(NodeKind.TABLE, parent=parent)
    for row in head[1]:
        _table_row(builder, row, parent=table_id, variant="header")
    for body in bodies:
        for row in body[2]:  # a body's intermediate head rows
            _table_row(builder, row, parent=table_id, variant="header")
        for row in body[3]:
            _table_row(builder, row, parent=table_id, variant="body")
    for row in foot[1]:
        _table_row(builder, row, parent=table_id, variant="body")


def _table_row(builder: KirBuilder, row: object, *, parent: str, variant: str) -> None:
    row_id = builder.add(NodeKind.TABLE_ROW, parent=parent, variant=variant)
    for cell in row[1]:  # type: ignore[index]
        _attr, _align, _rowspan, _colspan, blocks = cell
        parts = [
            _inline_text(_contents(block)) for block in blocks if _tag(block) in {"Plain", "Para"}
        ]
        cell_id = builder.add(NodeKind.TABLE_CELL, parent=row_id, text=" ".join(parts))
        for block in blocks:
            if _tag(block) in {"Plain", "Para"}:
                _references(builder, _contents(block), cell_id)


def _opaque(builder: KirBuilder, tag: str, content: object, *, parent: str | None) -> None:
    """Record an unmappable construct as an opaque node (spec 03 §4).

    The node keeps the constructor's name in `note` and, when pandoc's payload is
    literal source text — a `RawBlock`, a `RawInline` — that text verbatim. This
    is the same treatment ADR-0006 already gives raw HTML in authored Markdown:
    kept as text, never interpreted (D-017).

    The `variant` records which of the two it was, because that is what the
    fidelity report counts: a payload that survived is `degraded`, one that did
    not is `lost`, and only the second is charged against the loss budget
    (ADR-0034).

    It deliberately does **not** set `blob`. That field names a payload stored in
    the CAS, and a parser has no custody handle to store one with; a digest
    pointing at bytes nobody wrote is a claim the reader cannot follow (ADR-0033).
    """
    raw = _raw_text(tag, content)
    builder.opaque(
        f"pandoc {tag or 'unknown'}",
        disposition=(OpaqueDisposition.DEGRADED if raw is not None else OpaqueDisposition.LOST),
        parent=parent,
        text=raw,
        media_type=_RAW_MEDIA.get(tag, "application/x-pandoc-ast+json"),
    )


def _raw_text(tag: str, content: object) -> str | None:
    """The literal payload of a raw construct, or ``None`` for a structured one."""
    if tag in {"RawBlock", "RawInline"} and isinstance(content, list) and len(content) == 2:
        return str(content[1])
    return None


# ---------------------------------------------------------------------------
# Inlines. KIR stores flattened text plus the referential nodes edges are built
# from (spec 03 §6) — the division the Markdown adapter already makes (ADR-0006).
# ---------------------------------------------------------------------------


def _inline_text(inlines: object) -> str:
    """Flatten an inline sequence into the plain text KIR stores."""
    if not isinstance(inlines, list):
        return ""
    return "".join(_one_inline_text(inline) for inline in inlines)


def _one_inline_text(inline: object) -> str:
    tag = _tag(inline)
    content = _contents(inline)
    if tag == "Str":
        return str(content)
    if tag in _WHITESPACE:
        return _WHITESPACE[tag]
    if tag in {"Code", "Math"}:
        return str(content[1])
    if tag in _INLINE_MARKUP:
        return _inline_text(content)
    if tag in _INLINE_WRAPPED or tag in {"Link", "Image"}:
        return _inline_text(content[1])
    # RawInline is output aimed at another writer, and a Note's body is emitted
    # as its own node; neither is this document's running text.
    return ""


def _references(builder: KirBuilder, inlines: object, parent: str | None) -> None:
    """Emit the link, image, footnote and raw-inline nodes carried inside a block."""
    if not isinstance(inlines, list):
        return
    for inline in inlines:
        tag = _tag(inline)
        content = _contents(inline)
        if tag in {"Link", "Image"}:
            _attr, label, (target, title) = content
            builder.add(
                NodeKind.LINK if tag == "Link" else NodeKind.IMAGE,
                parent=parent,
                text=_inline_text(label),
                target=str(target),
                title=str(title) if title else None,
            )
            _references(builder, label, parent)
        elif tag == "Note":
            note_id = builder.add(NodeKind.FOOTNOTE, parent=parent)
            for block in content:
                _block(builder, block, parent=note_id, depth=1)
        elif tag == "RawInline":
            _opaque(builder, "RawInline", content, parent=parent)
        elif tag in _INLINE_MARKUP:
            _references(builder, content, parent)
        elif tag in _INLINE_WRAPPED:
            _references(builder, content[1], parent)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def _probe(executable: str) -> str:
    """Return pandoc's version string, or explain precisely why it cannot be used."""
    resolved = shutil.which(executable)
    if resolved is None:
        msg = (
            f"the {PARSER_ID!r} parser needs the pandoc binary on PATH; install pandoc "
            f"{_MIN_MAJOR}.x (https://pandoc.org/installing.html) or drop {PARSER_ID!r} "
            "from [ingest] parsers"
        )
        raise PluginUnavailableError(msg)
    try:
        completed = subprocess.run(  # fixed argument vector, no shell
            [resolved, "--version"], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        msg = f"the {PARSER_ID!r} parser found {resolved} but could not run it - {error}"
        raise PluginUnavailableError(msg) from error
    if completed.returncode != 0:
        msg = f"the {PARSER_ID!r} parser found {resolved}, and `pandoc --version` exited nonzero"
        raise PluginUnavailableError(msg)

    words = completed.stdout.decode("utf-8", errors="replace").split()
    reported = words[1] if len(words) > 1 else "unknown"
    major = reported.split(".")[0]
    if not major.isdigit() or int(major) < _MIN_MAJOR:
        msg = (
            f"the {PARSER_ID!r} parser needs pandoc {_MIN_MAJOR}.x or newer for --sandbox; "
            f"{resolved} reports {reported}"
        )
        raise PluginUnavailableError(msg)
    return reported


def plugin(
    *, executable: str = DEFAULT_EXECUTABLE, timeout_s: float = DEFAULT_TIMEOUT_S
) -> PandocParser:
    """Build the parser, or raise :class:`PluginUnavailableError` naming what is missing."""
    return PandocParser(executable=executable, version=_probe(executable), timeout_s=timeout_s)
