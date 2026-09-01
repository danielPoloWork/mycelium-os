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

__all__ = ["EVIDENCE_DIRNAME", "Projection", "evidence_path", "project"]

EVIDENCE_DIRNAME: Final = "evidence"
"""Under `knowledge/`: the folder that *is* the verification status (D-021)."""

_HEADING_MARK: Final = "#"
_MAX_HEADING = 6
_SLUG_STRIP: Final = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Projection:
    """One projected evidence document, before it is written."""

    path: PurePosixPath
    """Repository-relative POSIX path, always under `knowledge/evidence/`."""

    text: str
    """The document's full text, frontmatter included, LF-terminated."""

    title: str


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
    body = "\n\n".join(_blocks(kir))
    text = f"{frontmatter}\n{body}\n" if body else frontmatter
    return Projection(
        path=evidence_path(source_uri, knowledge_dir=knowledge_dir, digest=source_digest),
        text=text,
        title=resolved,
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


def _blocks(kir: KirDocument) -> Iterator[str]:
    """Render KIR as Markdown blocks, in document order.

    Only *section-level* nodes are rendered on their own — the ones whose parent
    is nothing or a heading. Everything deeper is rendered by the container that
    owns it: a table's rows, a list's items, a quote's paragraphs. This is the
    same test the chunker applies (ADR-0007), and it has to be: without it a
    blockquote's paragraph is emitted twice, once inside the quote and once as
    prose — which is what the first run of this projector did.

    Reference nodes are skipped at any depth: their text is already inside the
    block that contains them (ADR-0006).
    """
    children = _children_of(kir.nodes)
    by_id = {node.id: node for node in kir.nodes}
    for node in kir.nodes:
        if node.kind in _REFERENCES or not _section_level(node, by_id):
            continue
        rendered = _block(node, children, kir.nodes)
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


def _children_of(nodes: Sequence[KirNode]) -> Mapping[str, list[KirNode]]:
    children: dict[str, list[KirNode]] = {}
    for node in nodes:
        if node.parent is not None:
            children.setdefault(node.parent, []).append(node)
    return children


def _block(  # noqa: C901 - one branch per node kind reads better than a dispatch table
    node: KirNode, children: Mapping[str, list[KirNode]], nodes: Sequence[KirNode]
) -> str:
    text = (node.text or "").strip()

    if node.kind is NodeKind.HEADING:
        level = min(_MAX_HEADING, max(1, node.level or 1))
        return f"{_HEADING_MARK * level} {text}" if text else ""

    if node.kind is NodeKind.CODE_BLOCK:
        fence = _fence_for(node.text or "")
        return f"{fence}{node.lang or ''}\n{node.text or ''}\n{fence}".replace(
            "\n\n" + fence, "\n" + fence
        )

    if node.kind is NodeKind.TABLE:
        return _table(node, children)

    if node.kind is NodeKind.LIST:
        return _list(node, children)

    if node.kind is NodeKind.QUOTE:
        return _quoted(_descendant_text(node, children), marker="> ")

    if node.kind is NodeKind.CALLOUT:
        head = f"[!{node.variant or 'note'}]"
        if node.title:
            head = f"{head} {node.title}"
        body = _descendant_text(node, children)
        return _quoted(f"{head}\n{body}" if body else head, marker="> ")

    if node.kind is NodeKind.EQUATION:
        return f"$$\n{text}\n$$" if text else ""

    if node.kind is NodeKind.FOOTNOTE:
        body = _descendant_text(node, children) or text
        return _quoted(f"[!note] Footnote\n{body}", marker="> ") if body else ""

    if node.kind is NodeKind.OPAQUE:
        return _opaque(node)

    if node.kind is NodeKind.SECTION:
        return ""  # a wrapper; its children are emitted in their own right

    del nodes
    return text


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


def _table(node: KirNode, children: Mapping[str, list[KirNode]]) -> str:
    rows = [child for child in children.get(node.id, ()) if child.kind is NodeKind.TABLE_ROW]
    if not rows:
        return ""
    rendered: list[str] = []
    for index, row in enumerate(rows):
        cells = [
            (cell.text or "").replace("|", "\\|").replace("\n", " ").strip()
            for cell in children.get(row.id, ())
            if cell.kind is NodeKind.TABLE_CELL
        ]
        rendered.append("| " + " | ".join(cells) + " |")
        if index == 0:
            rendered.append("|" + "|".join(" --- " for _ in cells) + "|")
    return "\n".join(rendered)


def _list(node: KirNode, children: Mapping[str, list[KirNode]], depth: int = 0) -> str:
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
            lines.append(_list(child, children, depth + 1))
            continue
        if child.kind is not NodeKind.LIST_ITEM:
            continue
        number += 1
        marker = f"{number}." if ordered else "-"
        text = (child.text or "").replace("\n", " ").strip()
        lines.append(f"{indent}{marker} {text}".rstrip())
        for grandchild in children.get(child.id, ()):
            if grandchild.kind in _REFERENCES:
                continue
            if grandchild.kind is NodeKind.LIST:
                lines.append(_list(grandchild, children, depth + 1))
                continue
            rendered = _block(grandchild, children, ())
            if rendered:
                lines.append("")
                lines.append(_indented(rendered, indent + "  "))
    return "\n".join(lines).strip("\n")


def _indented(text: str, indent: str) -> str:
    return "\n".join(f"{indent}{line}".rstrip() for line in text.split("\n"))


def _descendant_text(node: KirNode, children: Mapping[str, list[KirNode]]) -> str:
    """Every descendant block's text, in order, as plain paragraphs."""
    parts: list[str] = []
    for child in children.get(node.id, ()):
        if child.kind in _REFERENCES:
            continue
        if child.text:
            parts.append(child.text.strip())
        nested = _descendant_text(child, children)
        if nested:
            parts.append(nested)
    return "\n\n".join(part for part in parts if part)


def _quoted(text: str, *, marker: str) -> str:
    return "\n".join(f"{marker}{line}".rstrip() for line in text.split("\n"))


def _fence_for(code: str) -> str:
    """A fence long enough to contain `code`, whatever backticks it holds."""
    longest = max((len(run) for run in re.findall(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)
