# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""KIR back to Markdown: the evidence lane's visible output (spec 02 §5).

An ingested PDF becomes a file under `knowledge/evidence/`, and from that moment
the compiler treats it like any other authored document. That is the design
spec 02 §5 insists on — **the projector writes Markdown documents only**, and
chunks, indexes, vectors and edges are always produced by the deterministic
compiler from those documents (D-020). Nothing here writes an index.

Two rules govern what the file may contain.

**The text is verbatim; only the syntax is regenerated.** KIR holds a node's text
exactly as the engine read it (normalised per spec 03 §1 and no further), and this
module puts Markdown *around* it — a `#` before a heading, pipes around a table
row. What comes out is not the source document reconstructed; it is the source
document's *content*, in a form the compiler and a human can both read. The
property tested for it is the one the chunker already lives by: every node's text
survives into the projection.

**A reference is syntax too, and it is regenerated where it stood** (roadmap 5.18,
ADR-0090). A link, wikilink or embed the parser found is rendered back into the
block that carries it — ``[label](target)`` around the very words the block's
text already holds — so an ingested document's references reach the compiler and
the graph. Until 5.18 the projector rendered reference nodes by nobody, and the
threat model counted that as a control (B11) until roadmap 5.7 showed where the
guarantee actually lives: every edge derived from an ingested document is
``extracted`` whatever its syntax looked like (ADR-0079), so the projector may be
faithful and the compiler stays the judge. The block's text does not move — the
compiler flattens a label back to its words — which is what keeps every judged
anchor and every retrieval score where it was. Images are not rendered (a
picture's target is a parser-internal reference, and its alt text is already
prose) and tags need nothing (their ``#`` is already in the text).

**A line that would open block structure is escaped, and only that**
(roadmap 5.22, ADR-0093). KIR's text is verbatim, and a source whose upstream
rendering flattened a code block into prose hands this module a paragraph whose
first line is ```` ```toml ````. Written out as it stands, the compiler reads a
fence opener with no closing partner and everything to the end of the document
becomes one code block — headings, prose and links, all of it
([BUG-0024](../../../docs/bugs/2026/09/BUG-0024-prose-that-opens-a-fence-swallows-the-rest-of-a-projection.md)).
So :func:`neutralise` puts a backslash in front of the shapes that open a block,
on every line of a projected paragraph. That is the chats projector's rule
(ADR-0077) applied where it is four items older and was never asked for: a
source's prose does not get to assert the document's structure, any more than it
gets to assert a link (threat model B11).

The escape is free, and that was measured rather than assumed: CommonMark reads
``\\##`` as a literal ``##``, so the *indexed text* carries the original
characters and only the block-level meaning is gone. Every shape below
round-trips to the byte, which is what lets this land without moving a single
judged anchor outside the four documents it repairs.

**Frontmatter carries provenance and nothing else.** Four contract fields belong
to `mycelium ingest` (spec 03 §3): `origin`, `source`, `source_trust`,
`generated_by` — plus `source_digest`, added at 4.3 so a projected document can
name the tier-1 blob it came from (ADR-0034). No `status:` field: verification
status is the folder's (D-021), and this writes into `evidence/`.

An element KIR could not model appears as a `[!missing]` callout — Profile v1
syntax, so it is visible in Obsidian, chunked atomically like any callout, and
impossible to mistake for the document's own prose. A reader of the projection can
see exactly where something was lost, which is the whole point of an
"opaque-node escape hatch" that ends in a file a person reads.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from mycelium.sdk.types import (
    KirDocument,
    KirNode,
    NodeKind,
    OpaqueDisposition,
    ProvenanceOrigin,
    Sha256Digest,
    SourceTrust,
)

__all__ = ["EVIDENCE_DIRNAME", "Projection", "evidence_path", "neutralise", "project"]

EVIDENCE_DIRNAME: Final = "evidence"
"""Under `knowledge/`: the folder that *is* the verification status (D-021)."""

_HEADING_MARK: Final = "#"
_MAX_HEADING = 6

_FENCE: Final = re.compile(r"^(?:`{3,}|~{3,})")
"""An unmatched fence opener runs to the end of the document, which is the shape
BUG-0024 was reported for and the only one that can swallow a whole projection."""

_ATX: Final = re.compile(r"^#{1,6}(?:\s|$)")
"""``## X`` — a heading the source's prose did not author. The space is required,
so ``#tag`` is left alone: it is an inline tag whose ``#`` is already in the text,
and the projector has always let those through."""

_BULLET: Final = re.compile(r"^[-*+](?:\s|$)")

_ORDERED: Final = re.compile(r"^(\d{1,9})([.)])(?=\s|$)")
r"""Escaped on its *punctuation* — ``1\. `` — because a backslash is only an escape
before ASCII punctuation, so ``\1.`` would leave a literal backslash in the text."""

_QUOTE_MARK: Final = re.compile(r"^>")

_RULE: Final = re.compile(r"^(?:-+|=+|_{3,}|\*{3,})\s*$")
"""A thematic break, or a setext underline — which is worse than it looks: it makes
a *heading* out of the lines above it, so a line of dashes in projected prose can
promote the paragraph before it. Any run of ``-`` or ``=`` underlines; a break
needs three."""
_SLUG_STRIP: Final = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Projection:
    """One projected evidence document, before it is written."""

    path: PurePosixPath
    """Repository-relative POSIX path, always under `knowledge/evidence/`."""

    text: str
    """The document's full text, frontmatter included, LF-terminated."""

    title: str

    references: int = 0
    """Links, wikilinks and embeds rendered back into the body (roadmap 5.18)."""

    references_dropped: int = 0
    """References that could not be placed: no label at all (an anchor around an
    image), or a label the block's text does not contain. Dropped as the whole
    class was before 5.18, and counted so the drop is visible rather than silent."""


def evidence_path(
    source_uri: str, *, knowledge_dir: str = "knowledge", digest: Sha256Digest | None = None
) -> PurePosixPath:
    """Where a source's evidence document goes.

    The name is derived from the source's own filename, slugified, because a
    human reading `knowledge/evidence/` should recognise what is in it. A digest
    suffix is appended when one is given, so two sources whose names collide —
    `report.pdf` from two directories — do not overwrite each other. Eight hex
    characters: enough that a collision is not a practical concern, short enough
    that the filename stays readable.
    """
    stem = PurePosixPath(source_uri.rstrip("/")).name or "source"
    slug = _SLUG_STRIP.sub("-", stem.lower()).strip("-") or "source"
    if digest is not None:
        slug = f"{slug}-{digest.removeprefix('sha256:')[:8]}"
    return PurePosixPath(knowledge_dir) / EVIDENCE_DIRNAME / f"{slug}.md"


def project(
    kir: KirDocument,
    *,
    source_uri: str,
    source_digest: Sha256Digest,
    source_trust: SourceTrust | None = None,
    generated_by: str | None = None,
    knowledge_dir: str = "knowledge",
    title: str | None = None,
) -> Projection:
    """Render `kir` as an evidence document.

    `doc_id` is **not** written into frontmatter. `mycelium_id` belongs to
    `mycelium build` (spec 03 §3's ownership table), and the first build of the
    projected file pins it — the same path an authored document takes. A projector
    that stamped it would be the second writer of a single-writer field.
    """
    resolved = title or _title_of(kir.nodes, source_uri)
    frontmatter = _frontmatter(
        {
            "title": resolved,
            "origin": ProvenanceOrigin.INGESTED.value,
            "source": source_uri,
            "source_digest": source_digest,
            "source_trust": source_trust.value if source_trust is not None else None,
            "generated_by": generated_by,
        }
    )
    tally = _Tally()
    body = "\n\n".join(_blocks(kir, tally))
    text = f"{frontmatter}\n{body}\n" if body else frontmatter
    return Projection(
        path=evidence_path(source_uri, knowledge_dir=knowledge_dir, digest=source_digest),
        text=text,
        title=resolved,
        references=tally.carried,
        references_dropped=tally.dropped,
    )


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _frontmatter(fields: Mapping[str, str | None]) -> str:
    """Render the provenance block. Hand-written, not PyYAML, and on purpose.

    Every value here is a string this module produced — a URI, a digest, an enum
    value — so the only question is quoting, and a dumper's block style, key
    ordering and line folding would be three more things to pin for byte-stable
    output. The keys come out in contract order (spec 03 §3), which is the order a
    reader expects rather than alphabetical.
    """
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        lines.append(f"{key}: {_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


_NEEDS_QUOTES: Final = frozenset(":#&*!|>%@`{}[],\"'\n")


def _scalar(value: str) -> str:
    """Quote a YAML scalar when it could be read as anything but a string."""
    if not value or value.strip() != value or any(char in value for char in _NEEDS_QUOTES):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return value


def _title_of(nodes: Sequence[KirNode], source_uri: str) -> str:
    """The document's first heading, else its source filename."""
    for node in nodes:
        if node.kind is NodeKind.HEADING and node.text:
            return node.text.strip()
    return PurePosixPath(source_uri.rstrip("/")).name or "Ingested source"


# ---------------------------------------------------------------------------
# The body
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Tally:
    """How many references the body carried, and how many it could not."""

    carried: int = 0
    dropped: int = 0


def _blocks(kir: KirDocument, tally: "_Tally") -> Iterator[str]:
    """Render KIR as Markdown blocks, in document order.

    Only *section-level* nodes are rendered on their own — the ones whose parent
    is nothing or a heading. Everything deeper is rendered by the container that
    owns it: a table's rows, a list's items, a quote's paragraphs. This is the
    same test the chunker applies (ADR-0007), and it has to be: without it a
    blockquote's paragraph is emitted twice, once inside the quote and once as
    prose — which is what the first run of this projector did.

    Reference nodes are never blocks of their own: their text is already inside
    the block that contains them (ADR-0006), and that block renders them back in
    place through :func:`_with_references` (roadmap 5.18).
    """
    children = _children_of(kir.nodes)
    by_id = {node.id: node for node in kir.nodes}
    for node in kir.nodes:
        if node.kind in _REFERENCES or not _section_level(node, by_id):
            continue
        rendered = _block(node, children, tally)
        if rendered:
            yield rendered


def _section_level(node: KirNode, by_id: Mapping[str, KirNode]) -> bool:
    """Whether this node is rendered in its own right rather than by a container."""
    if node.parent is None:
        return True
    parent = by_id.get(node.parent)
    return parent is not None and parent.kind is NodeKind.HEADING


_REFERENCES: Final = frozenset(
    {
        NodeKind.LINK,
        NodeKind.IMAGE,
        NodeKind.WIKILINK,
        NodeKind.EMBED,
        NodeKind.TAG_REF,
    }
)


_CARRIED: Final = frozenset({NodeKind.LINK, NodeKind.WIKILINK, NodeKind.EMBED})
"""The reference kinds rendered back into their block (roadmap 5.18) — the three
that assert a link (spec 03 §6, `mycelium.graph._LINK_KINDS`). An image's target
is a parser's own reference, not a document's; a tag's `#` is already text."""

_LABEL_ESCAPES: Final = str.maketrans({"\\": "\\\\", "[": "\\[", "]": "\\]"})
_ANGLE_DESTINATION: Final = frozenset(" \t\n()<>")


def _children_of(nodes: Sequence[KirNode]) -> Mapping[str, list[KirNode]]:
    children: dict[str, list[KirNode]] = {}
    for node in nodes:
        if node.parent is not None:
            children.setdefault(node.parent, []).append(node)
    return children


def _with_references(
    text: str,
    node: KirNode,
    children: Mapping[str, list[KirNode]],
    tally: _Tally,
    *,
    in_cell: bool = False,
) -> str:
    """`text` with the node's own references rendered back where their labels sit.

    A reference node carries its label and its target but no offset (KIR's
    locator is line-grained, spec 03 §4), so the label is *found* in the block's
    text — from a cursor that advances with each placement, because references
    are emitted in document order and the same word may be linked twice. Measured
    on the vendored ingested corpus before this was written: 507 of 509
    references placed, the two exceptions being anchors around images with no
    label at all. One that cannot be placed is dropped and counted, never
    appended: appending would put the label into the block twice, and the chunk
    text is the one thing this rendering must not move.

    Inside a table cell a wikilink that needs a `|` for its label is not carried:
    the pipe would have to be backslash-escaped, and whether a wikilink parser
    reads an escaped pipe is not a bet this projector should place on someone
    else's parser.
    """
    references = [
        child for child in children.get(node.id, ()) if child.kind in _CARRIED and child.target
    ]
    if not references:
        return text
    out: list[str] = []
    cursor = 0
    for reference in references:
        label = reference.text or ""
        index = text.find(label, cursor) if label.strip() else -1
        if index < 0:
            tally.dropped += 1
            continue
        if in_cell and reference.kind is not NodeKind.LINK and label != reference.target:
            tally.dropped += 1
            continue
        out.append(text[cursor:index])
        out.append(_reference(reference, label))
        cursor = index + len(label)
        tally.carried += 1
    out.append(text[cursor:])
    return "".join(out)


def _reference(node: KirNode, label: str) -> str:
    """One reference as the Markdown syntax it was — the Profile's own (spec 03 §3.1)."""
    target = node.target or ""
    if node.kind is NodeKind.WIKILINK:
        return f"[[{target}]]" if label == target else f"[[{target}|{label}]]"
    if node.kind is NodeKind.EMBED:
        return f"![[{target}]]" if label == target else f"![[{target}|{label}]]"
    title = f' "{node.title.replace(chr(34), chr(92) + chr(34))}"' if node.title else ""
    return f"[{label.translate(_LABEL_ESCAPES)}]({_destination(target)}{title})"


def _destination(target: str) -> str:
    """A link destination CommonMark reads back as the same string.

    The bare form takes anything without whitespace, parentheses or angle
    brackets; everything else goes in `<…>`, which cannot hold a newline. A
    backslash is escaped in both, because a backslash before punctuation would
    otherwise be read as an escape and change the target.
    """
    escaped = target.replace("\\", "\\\\")
    if any(char in _ANGLE_DESTINATION for char in escaped):
        inner = escaped.replace("<", "\\<").replace(">", "\\>").replace("\n", "%0A")
        return f"<{inner}>"
    return escaped


def neutralise(text: str) -> str:
    """Escape the lines of `text` that would open block structure (roadmap 5.22).

    Applied to a projected paragraph — every line of it, not only the first.
    Measured on the three corpora: each of these shapes interrupts a paragraph
    mid-block as readily as it opens one, so a rule for the first line alone
    would have left `dependencies-docx` exactly as broken as it was.

    What is deliberately *not* escaped: an inline tag (``#tag``, no space — its
    ``#`` is already in the text and the projector has always carried it), raw
    HTML (the Profile disables it, so ``<div>`` is already prose), and an indented
    line, which no backslash can neutralise — four leading spaces are a code block
    whatever precedes them. The last one is a gap rather than a decision, and it
    is empty on all three corpora: ADR-0093 records the measurement.
    """
    return "\n".join(_neutralise_line(line) for line in text.split("\n"))


def _neutralise_line(line: str) -> str:
    ordered = _ORDERED.match(line)
    if ordered is not None:
        return f"{ordered.group(1)}\\{ordered.group(2)}{line[ordered.end() :]}"
    if (
        _FENCE.match(line)
        or _ATX.match(line)
        or _BULLET.match(line)
        or _QUOTE_MARK.match(line)
        or _RULE.match(line)
    ):
        return "\\" + line
    return line


def _block(  # noqa: C901 - one branch per node kind reads better than a dispatch table
    node: KirNode, children: Mapping[str, list[KirNode]], tally: _Tally
) -> str:
    text = (node.text or "").strip()

    if node.kind is NodeKind.HEADING:
        level = min(_MAX_HEADING, max(1, node.level or 1))
        rendered = _with_references(text, node, children, tally)
        return f"{_HEADING_MARK * level} {rendered}" if text else ""

    if node.kind is NodeKind.CODE_BLOCK:
        fence = _fence_for(node.text or "")
        return f"{fence}{node.lang or ''}\n{node.text or ''}\n{fence}".replace(
            "\n\n" + fence, "\n" + fence
        )

    if node.kind is NodeKind.TABLE:
        return _table(node, children, tally)

    if node.kind is NodeKind.LIST:
        return _list(node, children, tally)

    if node.kind is NodeKind.QUOTE:
        return _quoted(_descendant_text(node, children, tally), marker="> ")

    if node.kind is NodeKind.CALLOUT:
        head = f"[!{node.variant or 'note'}]"
        if node.title:
            head = f"{head} {node.title}"
        body = _descendant_text(node, children, tally)
        return _quoted(f"{head}\n{body}" if body else head, marker="> ")

    if node.kind is NodeKind.EQUATION:
        return f"$$\n{text}\n$$" if text else ""

    if node.kind is NodeKind.FOOTNOTE:
        body = _descendant_text(node, children, tally) or text
        return _quoted(f"[!note] Footnote\n{body}", marker="> ") if body else ""

    if node.kind is NodeKind.OPAQUE:
        return _opaque(node)

    if node.kind is NodeKind.SECTION:
        return ""  # a wrapper; its children are emitted in their own right

    # The paragraph path, and every kind KIR models as prose. References are
    # rendered first and the escape runs over the result, so a label that begins
    # a line is already wrapped in `[` by the time the shapes are tested.
    return neutralise(_with_references(text, node, children, tally))


def _opaque(node: KirNode) -> str:
    """An element KIR could not model, as a callout a reader cannot miss.

    `[!missing]` rather than an HTML comment: the profile disables raw HTML, so a
    comment would survive as literal prose and be indexed as content (ADR-0006).
    A callout is Profile v1 syntax, atomic in the chunker, and legible in Obsidian.
    """
    lost = node.variant == OpaqueDisposition.LOST.value
    label = "missing" if lost else "warning"
    note = node.note or "unrepresentable element"
    head = f"[!{label}] {note}"
    if node.text:
        return _quoted(f"{head}\n{node.text}", marker="> ")
    return _quoted(head, marker="> ")


def _table(node: KirNode, children: Mapping[str, list[KirNode]], tally: _Tally) -> str:
    rows = [child for child in children.get(node.id, ()) if child.kind is NodeKind.TABLE_ROW]
    if not rows:
        return ""
    rendered: list[str] = []
    for index, row in enumerate(rows):
        cells = [
            _with_references((cell.text or "").strip(), cell, children, tally, in_cell=True)
            .replace("|", "\\|")
            .replace("\n", " ")
            .strip()
            for cell in children.get(row.id, ())
            if cell.kind is NodeKind.TABLE_CELL
        ]
        rendered.append("| " + " | ".join(cells) + " |")
        if index == 0:
            rendered.append("|" + "|".join(" --- " for _ in cells) + "|")
    return "\n".join(rendered)


def _list(
    node: KirNode, children: Mapping[str, list[KirNode]], tally: _Tally, depth: int = 0
) -> str:
    """Render a list, including whatever hangs off its items.

    An item's own text is its first line; anything else beneath it — a nested
    list, or the paragraph a definition list puts under its term — becomes an
    indented continuation block. Without that, pandoc's definition lists lose
    their definitions: the term survives as the item, and the definition, being a
    paragraph parented to the item rather than to a heading, is rendered by
    nobody.
    """
    ordered = node.variant == "ordered"
    indent = "    " * depth
    lines: list[str] = []
    number = 0
    for child in children.get(node.id, ()):
        if child.kind is NodeKind.LIST:
            lines.append(_list(child, children, tally, depth + 1))
            continue
        if child.kind is not NodeKind.LIST_ITEM:
            continue
        number += 1
        marker = f"{number}." if ordered else "-"
        text = _with_references((child.text or "").strip(), child, children, tally)
        text = text.replace("\n", " ").strip()
        lines.append(f"{indent}{marker} {text}".rstrip())
        for grandchild in children.get(child.id, ()):
            if grandchild.kind in _REFERENCES:
                continue
            if grandchild.kind is NodeKind.LIST:
                lines.append(_list(grandchild, children, tally, depth + 1))
                continue
            rendered = _block(grandchild, children, tally)
            if rendered:
                lines.append("")
                lines.append(_indented(rendered, indent + "  "))
    return "\n".join(lines).strip("\n")


def _indented(text: str, indent: str) -> str:
    return "\n".join(f"{indent}{line}".rstrip() for line in text.split("\n"))


def _descendant_text(node: KirNode, children: Mapping[str, list[KirNode]], tally: _Tally) -> str:
    """Every descendant block's text, in order, as plain paragraphs."""
    parts: list[str] = []
    for child in children.get(node.id, ()):
        if child.kind in _REFERENCES:
            continue
        if child.text:
            parts.append(_with_references(child.text.strip(), child, children, tally))
        nested = _descendant_text(child, children, tally)
        if nested:
            parts.append(nested)
    return "\n\n".join(part for part in parts if part)


def _quoted(text: str, *, marker: str) -> str:
    return "\n".join(f"{marker}{line}".rstrip() for line in text.split("\n"))


def _fence_for(code: str) -> str:
    """A fence long enough to contain `code`, whatever backticks it holds."""
    longest = max((len(run) for run in re.findall(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)
