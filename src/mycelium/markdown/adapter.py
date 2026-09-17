# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Markdown → KIR adapter (spec 03 §§3-4, D-007/D-022).

Mycelium OS owns the *representation*, not the parser (D-007): markdown-it produces
the token stream, and this module adapts it into KIR — a thin, ordered, versioned
AST whose node kinds are fixed by spec 03 §4. Everything markdown-it knows that
KIR does not model (emphasis, list markup) flattens into node text; inline code
flattens too but is *also* recorded in ``spans``, because a code span is how a
corpus names a command (5.23, ADR-0094); and everything KIR models that
CommonMark does not know (wikilinks, embeds, tags, callouts) comes from
:mod:`mycelium.markdown.profile`.

Emphasis stays flattened and unrecorded by decision, not by omission: it names
nothing a query can use, and the one place the authored and ingested lanes
disagree about a document turned out not to be caused by the missing vocabulary
at all (roadmap 5.36, ADR-0107).

Shape rules, all consequences of "thin and ordered":

- Nodes are emitted in document order; ``ord`` is the 0-based position in that
  order and ``id`` is ``n<ord+1>``, the spec's own naming (§4).
- Headings parent their following content, and deeper headings parent to
  shallower ones — the same nesting the chunker reads as a heading path (2.5).
  No synthetic ``document``/``section`` wrappers: the spec's own example parents
  a paragraph directly to its heading.
- Structural artifacts of the token stream disappear: ``thead``/``tbody`` wrappers,
  and the paragraphs markdown-it inserts inside loose list items.
- ``src.lines`` carries an inclusive, 1-based line span in the *source file*,
  frontmatter included, so citations point where an editor puts the cursor.

Raw HTML is neither executed nor interpreted: the profile disables it, so a tag
reaches this module inside a text token. Since 5.40 the *markup* is deleted from
what KIR stores and the words are kept, which is what the rendered page shows and
what the ingested twin indexes — still without parsing any of it
(:mod:`mycelium.markdown.markup`, ADR-0110; D-017 — authored content is data,
never instructions).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode

from mycelium.markdown.frontmatter import Frontmatter, parse_frontmatter
from mycelium.markdown.markup import Part, strip_markup
from mycelium.markdown.profile import match_callout, profile_markdown_it
from mycelium.sdk.identity import digest_text, new_ulid, normalize_text
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, SrcLocator

__all__ = ["MAX_NESTING", "MarkdownDocument", "MarkdownError", "parse_markdown"]

_HEADING_LEVELS: Final = {f"h{level}": level for level in range(1, 7)}
_INLINE_KINDS: Final = {
    "link": NodeKind.LINK,
    "image": NodeKind.IMAGE,
    "wikilink": NodeKind.WIKILINK,
    "embed": NodeKind.EMBED,
    "tag_ref": NodeKind.TAG_REF,
}

MAX_NESTING: Final = 100
"""How deep a document's token tree may nest before the adapter refuses it (roadmap 6.3).

markdown-it already stops nesting *structure* at this depth (its own `maxNesting`),
but emphasis is paired after the fact and is not counted: forty kilobytes of
asterisks nest ten thousand `em` levels, and building the syntax tree from them
recursed past the interpreter's limit — a `RecursionError` the build quarantined
by luck of a catch-all and `mycelium ingest` did not catch at all (BUG-0029).
One hundred is the parser's own number, and the deepest document in the three
corpora this project compiles nests six. A document over it is refused as a
:class:`MarkdownError`, which both lanes quarantine by name.
"""


def _deepest_nesting(tokens: Sequence[Token]) -> int:
    """The deepest open-tag depth in a token stream, inline children included.

    Linear: one pass over the blocks and one over each inline token's children,
    which is exactly the walk :class:`SyntaxTreeNode` would recurse through.
    """
    depth = 0
    deepest = 0
    for token in tokens:
        depth += token.nesting
        deepest = max(deepest, depth)
        if token.children:
            inner = depth
            for child in token.children:
                inner += child.nesting
                deepest = max(deepest, inner)
    return deepest


class MarkdownError(ValueError):
    """The document cannot be adapted — a conflicting identity, so far."""


@dataclass(frozen=True, slots=True)
class MarkdownDocument:
    """The result of compiling one authored Markdown file."""

    kir: KirDocument
    frontmatter: Frontmatter
    warnings: tuple[str, ...] = ()


@dataclass
class _Builder:
    """Accumulates KIR nodes in document order while the token tree is walked."""

    line_offset: int
    nodes: list[KirNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(
        self, kind: NodeKind, *, parent: str | None, node: SyntaxTreeNode | None, **fields: object
    ) -> str:
        """Append a node and return its id."""
        ordinal = len(self.nodes)
        node_id = f"n{ordinal + 1}"
        text = fields.pop("text", None)
        self.nodes.append(
            KirNode(
                id=node_id,
                kind=kind,
                text=normalize_text(text) if isinstance(text, str) else None,
                parent=parent,
                ord=ordinal,
                src=self._locate(node),
                **fields,  # type: ignore[arg-type]
            )
        )
        return node_id

    def _locate(self, node: SyntaxTreeNode | None) -> SrcLocator | None:
        """Map a token's 0-based half-open line range onto 1-based source lines."""
        span = getattr(node, "map", None) if node is not None else None
        if span is None:
            return None
        start, end = span
        return SrcLocator(lines=(start + self.line_offset + 1, end + self.line_offset))


def _parts(node: SyntaxTreeNode) -> list[Part]:
    """Render an inline subtree as the parts KIR's text is assembled from.

    Emphasis and inline-code markup is dropped (KIR has no node for it), links and
    wikilinks contribute their display text, and tags keep their ``#``.

    Each part carries whether it is *literal*: inline code, because a corpus
    explaining HTML quotes it and `spans` records it verbatim (ADR-0094), and a
    wikilink, embed or tag's own content, because the graph is keyed on the same
    string and the two must not drift apart. Prose — including an image's alt
    text, which is a description and not a target — is not literal, and raw-HTML
    stripping rewrites it (ADR-0110).
    """
    if node.type == "text":
        return [(node.content, False)]
    if node.type == "code_inline":
        return [(node.content, True)]
    if node.type in {"softbreak", "hardbreak"}:
        return [("\n", False)]
    if node.type == "tag_ref":
        return [(f"#{node.content}", True)]
    if node.type in {"wikilink", "embed"}:
        return [(node.content, True)]
    if node.type == "image":
        return [(str(node.attrs.get("alt", "")) or node.content, False)]
    return [part for child in node.children for part in _parts(child)]


def _flatten(node: SyntaxTreeNode) -> str:
    """The plain text KIR stores for an inline subtree, markup removed."""
    return strip_markup(_parts(node))


def _inline_children(node: SyntaxTreeNode) -> list[SyntaxTreeNode]:
    """Every referential inline token beneath `node`, in document order."""
    found: list[SyntaxTreeNode] = []
    for child in node.children:
        if child.type in _INLINE_KINDS:
            found.append(child)
        found.extend(_inline_children(child))
    return found


def _emit_inlines(
    builder: _Builder, inline: SyntaxTreeNode, parent: str, block: SyntaxTreeNode
) -> None:
    """Emit the reference nodes (links, wikilinks, embeds, images, tags) of a block.

    They are the edge sources the graph is later built from (spec 03 §6), so they
    are nodes in their own right even though their text already lives in the
    parent block's ``text``.
    """
    for child in _inline_children(inline):
        kind = _INLINE_KINDS[child.type]
        fields: dict[str, object] = {}
        if kind is NodeKind.LINK:
            fields["target"] = str(child.attrs.get("href", ""))
            fields["text"] = _flatten(child)
        elif kind is NodeKind.IMAGE:
            fields["target"] = str(child.attrs.get("src", ""))
            # Through `_flatten`, so the alt text on the node and the copy of it
            # inside the block's own text are the same string — markup removed
            # from both or from neither (ADR-0110). `_parts` keeps the fallback
            # to the image's content when there is no alt at all.
            fields["text"] = _flatten(child)
        elif kind is NodeKind.TAG_REF:
            fields["text"] = child.content
        else:  # wikilink, embed
            fields["target"] = str(child.meta.get("target", ""))
            fields["text"] = child.content
        if kind in {NodeKind.LINK, NodeKind.IMAGE}:
            title = child.attrs.get("title")
            if title:
                fields["title"] = str(title)
        builder.add(kind, parent=parent, node=block, **fields)


def _block_text(node: SyntaxTreeNode) -> str:
    """Flattened text of a block's own inline content, raw HTML markup removed.

    The parts of every inline child are collected before stripping, so an element
    opened and closed across the block is recognised as the pair it is — the
    block, not the token, is the scope pairing is resolved in (ADR-0110).
    """
    return strip_markup(
        part for child in node.children if child.type == "inline" for part in _parts(child)
    )


def _spans(node: SyntaxTreeNode) -> list[str]:
    if node.type == "code_inline":
        return [node.content]
    return [span for child in node.children for span in _spans(child)]


def _block_spans(node: SyntaxTreeNode) -> tuple[str, ...]:
    """The inline code spans of a block's own inline content, in order.

    The text they came from is still flattened (ADR-0006); this is the record of
    which of its words were written as code — the syntax documentation names a
    command with, and the one signal the flattening erased (roadmap 5.23).
    """
    return tuple(
        span for child in node.children if child.type == "inline" for span in _spans(child)
    )


def _walk(
    builder: _Builder,
    nodes: list[SyntaxTreeNode],
    parent: str | None,
    headings: list[tuple[int, str]],
) -> None:
    """Convert a run of sibling block tokens, threading the heading stack."""
    for node in nodes:
        _convert(builder, node, parent, headings)


def _current_parent(parent: str | None, headings: list[tuple[int, str]]) -> str | None:
    """Inside a heading's scope, that heading is the parent; otherwise the block's own."""
    if parent is not None:
        return parent
    return headings[-1][1] if headings else None


def _convert(  # noqa: C901 - one branch per token type reads better than a dispatch table
    builder: _Builder, node: SyntaxTreeNode, parent: str | None, headings: list[tuple[int, str]]
) -> None:
    kind = node.type

    if kind == "heading":
        level = _HEADING_LEVELS[node.tag]
        while headings and headings[-1][0] >= level:
            headings.pop()
        node_id = builder.add(
            NodeKind.HEADING,
            parent=_current_parent(parent, headings),
            node=node,
            level=level,
            text=_block_text(node),
            spans=_block_spans(node),
        )
        for child in node.children:
            if child.type == "inline":
                _emit_inlines(builder, child, node_id, node)
        headings.append((level, node_id))
        return

    if kind == "paragraph":
        text = _block_text(node)
        references = [
            child for child in node.children if child.type == "inline" and _inline_children(child)
        ]
        if not text.strip() and not references:
            # Every CommonMark paragraph has content, so a blank one here was
            # markup and nothing else — the `<p align="center">` wrapper around a
            # caption, or a comment on its own line. Keeping an empty node would
            # put blank lines into the chunk its content used to justify (5.40).
            return
        node_id = builder.add(
            NodeKind.PARAGRAPH,
            parent=_current_parent(parent, headings),
            node=node,
            text=text,
            spans=_block_spans(node),
        )
        for child in node.children:
            if child.type == "inline":
                _emit_inlines(builder, child, node_id, node)
        return

    if kind in {"fence", "code_block"}:
        info = node.info.strip().split(None, 1)[0] if node.info.strip() else None
        builder.add(
            NodeKind.CODE_BLOCK,
            parent=_current_parent(parent, headings),
            node=node,
            lang=info,
            text=node.content,
        )
        return

    if kind in {"bullet_list", "ordered_list"}:
        node_id = builder.add(
            NodeKind.LIST,
            parent=_current_parent(parent, headings),
            node=node,
            variant="ordered" if kind == "ordered_list" else "bullet",
        )
        _walk(builder, node.children, node_id, headings)
        return

    if kind == "list_item":
        # markdown-it wraps item content in paragraphs; KIR keeps the item thin and
        # lifts that text onto the item itself, recursing only into real structure.
        own_text = "".join(
            _block_text(child) for child in node.children if child.type == "paragraph"
        )
        own_spans = tuple(
            span
            for child in node.children
            if child.type == "paragraph"
            for span in _block_spans(child)
        )
        node_id = builder.add(
            NodeKind.LIST_ITEM, parent=parent, node=node, text=own_text, spans=own_spans
        )
        for child in node.children:
            if child.type == "paragraph":
                for inline in child.children:
                    if inline.type == "inline":
                        _emit_inlines(builder, inline, node_id, child)
            else:
                _convert(builder, child, node_id, headings)
        return

    if kind == "table":
        node_id = builder.add(NodeKind.TABLE, parent=_current_parent(parent, headings), node=node)
        for section in node.children:  # thead / tbody are structural, not KIR nodes
            variant = "header" if section.type == "thead" else "body"
            for row in section.children:
                row_id = builder.add(NodeKind.TABLE_ROW, parent=node_id, node=row, variant=variant)
                for cell in row.children:
                    cell_id = builder.add(
                        NodeKind.TABLE_CELL,
                        parent=row_id,
                        node=row,
                        text=_block_text(cell),
                        spans=_block_spans(cell),
                    )
                    for inline in cell.children:
                        if inline.type == "inline":
                            _emit_inlines(builder, inline, cell_id, row)
        return

    if kind == "blockquote":
        callout = None
        first = next((child for child in node.children if child.type == "paragraph"), None)
        if first is not None:
            head, _, rest = _block_text(first).partition("\n")
            callout = match_callout(head)
        if callout is not None:
            node_id = builder.add(
                NodeKind.CALLOUT,
                parent=_current_parent(parent, headings),
                node=node,
                variant=callout.kind,
                title=callout.title,
            )
            _emit_callout_body(builder, node, node_id, headings, first)
            return
        node_id = builder.add(NodeKind.QUOTE, parent=_current_parent(parent, headings), node=node)
        _walk(builder, node.children, node_id, headings)
        return

    if kind == "hr":
        return  # a thematic break carries no content; dropping it loses nothing

    if kind == "html_block":  # pragma: no cover - unreachable while html is disabled
        builder.add(
            NodeKind.PARAGRAPH,
            parent=_current_parent(parent, headings),
            node=node,
            text=node.content,
        )
        builder.warnings.append("raw HTML block kept as literal text")
        return

    builder.warnings.append(f"unhandled Markdown construct '{kind}' skipped")


def _emit_callout_body(
    builder: _Builder,
    quote: SyntaxTreeNode,
    callout_id: str,
    headings: list[tuple[int, str]],
    head_paragraph: SyntaxTreeNode | None,
) -> None:
    """Emit a callout's content, minus the ``[!type] Title`` marker line."""
    for child in quote.children:
        if child is head_paragraph:
            _, _, rest = _block_text(child).partition("\n")
            if rest.strip():
                builder.add(
                    NodeKind.PARAGRAPH,
                    parent=callout_id,
                    node=child,
                    text=rest,
                    spans=_block_spans(child),
                )
                for inline in child.children:
                    if inline.type == "inline":
                        _emit_inlines(builder, inline, callout_id, child)
            continue
        _convert(builder, child, callout_id, headings)


def parse_markdown(text: str, *, doc_id: str | None = None) -> MarkdownDocument:
    """Compile authored Markdown into a KIR document.

    `doc_id` overrides the identity; otherwise the document's pinned
    ``mycelium_id`` is used, and a fresh ULID is minted when it has none (the
    build writes it back into frontmatter — this function never edits the source).
    Raises :class:`MarkdownError` if the caller's id contradicts the pinned one,
    and :class:`~mycelium.markdown.frontmatter.FrontmatterError` if the
    frontmatter is unreadable.
    """
    parsed = parse_frontmatter(text)
    pinned = parsed.frontmatter.mycelium_id
    if doc_id is not None and pinned is not None and doc_id != pinned:
        msg = f"doc_id {doc_id!r} contradicts the document's pinned mycelium_id {pinned!r}"
        raise MarkdownError(msg)
    resolved = doc_id or pinned or new_ulid()

    tokens = profile_markdown_it().parse(parsed.body)
    depth = _deepest_nesting(tokens)
    if depth > MAX_NESTING:
        msg = (
            f"document nests {depth} levels deep, above the {MAX_NESTING}-level ceiling; "
            "no authored document nests like this, and reading one that does is unbounded"
        )
        raise MarkdownError(msg)
    try:
        tree = SyntaxTreeNode(tokens)
    except RecursionError as error:
        # The ceiling above is the control; this is the guard behind it, so a
        # shape it does not model is still a typed, per-document refusal.
        msg = "document nests deeper than the syntax tree can be built"
        raise MarkdownError(msg) from error
    builder = _Builder(line_offset=parsed.body_line_offset)
    _walk(builder, list(tree.children), None, [])

    warnings = (*parsed.warnings, *builder.warnings)
    return MarkdownDocument(
        kir=KirDocument(
            doc_id=resolved,
            source_digest=digest_text(text),
            nodes=tuple(builder.nodes),
            warnings=warnings,
        ),
        frontmatter=parsed.frontmatter,
        warnings=warnings,
    )
