# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Heading-bounded chunker (spec 03 §5).

Chunks are the retrieval unit, and their boundaries are the document's own
structure rather than a sliding window: a section becomes a chunk, an oversize
section splits at paragraph boundaries, and tables and code blocks stand alone.
Structure replaces overlap (overlap defaults to 0), because a heading path is a
better summary of "where am I" than the previous paragraph repeated.

The invariant, property-tested, is that **no text is lost**: the ordered chunk
texts contain every KIR node's text, in document order. What KIR already dropped
— emphasis markers, list bullets, table pipes (ADR-0006) — is out of scope by
construction; a chunker cannot restore what its input never carried.

Anchors come from the identity library (ADR-0005), which deliberately left one
question here: sibling headings that slug identically. This module owns it, and
resolves it the way every Markdown anchor generator does — by numbering repeats
within their parent — so an anchor stays unique and readable.
"""

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

from mycelium.sdk.identity import anchor as build_anchor
from mycelium.sdk.identity import digest_text, heading_slug, normalize_text
from mycelium.sdk.types import Chunk, ChunkKind, KirDocument, KirNode, NodeKind

__all__ = [
    "ChunkingPolicy",
    "TokenCounter",
    "chunk_document",
    "estimate_tokens",
]

type TokenCounter = Callable[[str], int]

_TOKEN_PATTERN: Final = re.compile(
    r"[぀-ヿ㐀-䶿一-鿿豈-﫿]"  # CJK: one token per glyph
    r"|[A-Za-z0-9_']+"  # word
    r"|[^\sA-Za-z0-9_']"  # standalone punctuation
)

_INLINE_KINDS: Final = frozenset(
    {
        NodeKind.LINK,
        NodeKind.IMAGE,
        NodeKind.WIKILINK,
        NodeKind.EMBED,
        NodeKind.TAG_REF,
    }
)
"""Reference nodes: their text is already inside the block that contains them."""

_ATOMIC_KINDS: Final = {NodeKind.TABLE: ChunkKind.TABLE, NodeKind.CODE_BLOCK: ChunkKind.CODE}


def estimate_tokens(text: str) -> int:
    """Estimate the token count of `text`.

    Words, standalone punctuation, and one token per CJK glyph. This is a
    *budgeting* estimate, not a tokenizer: it runs offline with no model files
    and is deterministic across platforms and versions, which matters more here
    than matching any particular BPE vocabulary (ADR-0007). A policy that needs
    exactness supplies its own counter.
    """
    return len(_TOKEN_PATTERN.findall(text))


@dataclass(frozen=True, slots=True)
class ChunkingPolicy:
    """Chunking knobs (spec 03 §5 defaults; `mycelium.toml` overrides them later).

    `target_max_tokens` is a real ceiling — prose fills toward it and splits at the
    paragraph before it would be breached. `target_min_tokens` is the declared
    lower target, and the packer deliberately does *not* enforce it: the only
    chunks that fall below it are a section's remainder, a heading with no content,
    and atomic tables and code blocks. Lifting any of them to the minimum would
    mean merging across a heading boundary, which is precisely what
    heading-bounded chunking exists to avoid (ADR-0007).
    """

    target_min_tokens: int = 200
    target_max_tokens: int = 800
    overlap_tokens: int = 0
    count_tokens: TokenCounter = estimate_tokens

    def __post_init__(self) -> None:
        if self.target_min_tokens < 0 or self.target_max_tokens <= 0:
            msg = "token targets must be positive"
            raise ValueError(msg)
        if self.target_min_tokens > self.target_max_tokens:
            msg = (
                f"target_min_tokens {self.target_min_tokens} exceeds "
                f"target_max_tokens {self.target_max_tokens}"
            )
            raise ValueError(msg)
        if self.overlap_tokens != 0:
            # Structure replaces overlap (spec 03 §5). The knob exists so the
            # decision is visible and measurable, not so it can be set today.
            msg = "overlap is not implemented in v1; structure replaces overlap"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class _Unit:
    """One section-level block of content, with the text it contributes."""

    node_ids: tuple[str, ...]
    text: str
    kind: ChunkKind
    lines: tuple[int, int] | None


@dataclass
class _Section:
    """A heading and the content that belongs to it."""

    heading: KirNode | None
    path: tuple[str, ...]
    slugs: tuple[str, ...]
    units: list[_Unit] = field(default_factory=list)


def _index(nodes: Sequence[KirNode]) -> tuple[dict[str, KirNode], dict[str | None, list[KirNode]]]:
    by_id = {node.id: node for node in nodes}
    children: dict[str | None, list[KirNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent].append(node)
    return by_id, children


def _unique_heading_slugs(nodes: Sequence[KirNode]) -> dict[str, str]:
    """Slug every heading, numbering repeats among siblings (``overview-2``)."""
    slugs: dict[str, str] = {}
    seen: dict[tuple[str | None, str], int] = defaultdict(int)
    for node in nodes:
        if node.kind is not NodeKind.HEADING:
            continue
        base = heading_slug(node.text or "")
        key = (node.parent, base)
        seen[key] += 1
        slugs[node.id] = base if seen[key] == 1 else f"{base}-{seen[key]}"
    return slugs


def _title_heading_id(nodes: Sequence[KirNode]) -> str | None:
    """The document's title heading, whose slug anchors omit.

    A single level-1 heading is the document's title: the document is already
    identified by its path, so repeating it in every anchor is noise. A document
    with several level-1 headings is using them as sections, and they all count
    (ADR-0007).
    """
    top = [node for node in nodes if node.kind is NodeKind.HEADING and node.level == 1]
    return top[0].id if len(top) == 1 else None


def _subtree_text(
    node: KirNode, children: dict[str | None, list[KirNode]]
) -> tuple[str, list[str]]:
    """Flatten a block and its descendants into the text a chunk stores."""
    if node.kind is NodeKind.TABLE:
        return _table_text(node, children)

    parts: list[str] = []
    ids: list[str] = []
    if node.kind is NodeKind.CALLOUT and node.title:
        parts.append(node.title)
    if node.text:
        parts.append(node.text)
    ids.append(node.id)
    for child in children.get(node.id, []):
        if child.kind in _INLINE_KINDS:
            ids.append(child.id)  # its text already sits in this block's text
            continue
        child_text, child_ids = _subtree_text(child, children)
        if child_text:
            parts.append(child_text)
        ids.extend(child_ids)
    return "\n".join(parts), ids


def _table_text(node: KirNode, children: dict[str | None, list[KirNode]]) -> tuple[str, list[str]]:
    """Render a table row-major, so a chunk of it reads as a table."""
    ids = [node.id]
    rows: list[str] = []
    for row in children.get(node.id, []):
        ids.append(row.id)
        cells: list[str] = []
        for cell in children.get(row.id, []):
            ids.append(cell.id)
            cells.append(cell.text or "")
            ids.extend(
                grandchild.id
                for grandchild in children.get(cell.id, [])
                if grandchild.kind in _INLINE_KINDS
            )
        rows.append(" | ".join(cells))
    return "\n".join(rows), ids


def _span(node_ids: Iterable[str], by_id: dict[str, KirNode]) -> tuple[int, int] | None:
    """The smallest line range covering a set of nodes."""
    spans: list[tuple[int, int]] = []
    for node_id in node_ids:
        src = by_id[node_id].src
        if src is not None and src.lines is not None:
            spans.append(src.lines)
    if not spans:
        return None
    return min(start for start, _ in spans), max(end for _, end in spans)


def _sections(kir: KirDocument) -> list[_Section]:
    """Split the node list into heading-bounded sections, in document order."""
    by_id, children = _index(kir.nodes)
    slugs = _unique_heading_slugs(kir.nodes)
    title_id = _title_heading_id(kir.nodes)

    sections: list[_Section] = [_Section(heading=None, path=(), slugs=())]
    stack: list[KirNode] = []

    for node in kir.nodes:
        parent = by_id.get(node.parent) if node.parent else None
        is_section_level = parent is None or parent.kind is NodeKind.HEADING
        if not is_section_level:
            continue  # reached through its container's subtree

        if node.kind is NodeKind.HEADING:
            while stack and (stack[-1].level or 1) >= (node.level or 1):
                stack.pop()
            stack.append(node)
            sections.append(
                _Section(
                    heading=node,
                    path=tuple(head.text or "" for head in stack),
                    slugs=tuple(slugs[head.id] for head in stack if head.id != title_id),
                )
            )
            continue

        if node.kind in _INLINE_KINDS:
            continue  # a reference directly under a heading; its text is the heading's
        text, ids = _subtree_text(node, children)
        if not text.strip():
            continue
        sections[-1].units.append(
            _Unit(
                node_ids=tuple(ids),
                text=text,
                kind=_ATOMIC_KINDS.get(node.kind, ChunkKind.PROSE),
                lines=_span(ids, by_id),
            )
        )

    return [section for section in sections if section.heading is not None or section.units]


def _pack(section: _Section, policy: ChunkingPolicy) -> list[tuple[list[_Unit], ChunkKind]]:
    """Group a section's units into chunk-sized runs.

    Prose accumulates until the next block would breach the token ceiling; tables
    and code blocks are atomic and never share a chunk. A single block larger than
    the ceiling stays whole — the policy forbids mid-sentence splits, and a
    paragraph is the smallest boundary there is.
    """
    packed: list[tuple[list[_Unit], ChunkKind]] = []
    pending: list[_Unit] = []
    pending_tokens = 0

    for unit in section.units:
        if unit.kind is not ChunkKind.PROSE:
            if pending:
                packed.append((pending, ChunkKind.PROSE))
                pending, pending_tokens = [], 0
            packed.append(([unit], unit.kind))
            continue
        tokens = policy.count_tokens(unit.text)
        if pending and pending_tokens + tokens > policy.target_max_tokens:
            packed.append((pending, ChunkKind.PROSE))
            pending, pending_tokens = [], 0
        pending.append(unit)
        pending_tokens += tokens

    if pending:
        packed.append((pending, ChunkKind.PROSE))
    if not packed and section.heading is not None:
        # A heading with no content of its own is still citable, and its text is
        # document text that must survive.
        packed.append(([], ChunkKind.PROSE))
    return packed


def chunk_document(
    kir: KirDocument,
    *,
    doc_path: str,
    policy: ChunkingPolicy | None = None,
    namespace: str = "default",
) -> tuple[Chunk, ...]:
    """Split a KIR document into heading-bounded chunks (spec 03 §5).

    `doc_path` is the document's repository-relative path, which anchors are keyed
    on. Chunks come back in document order; within a section they are numbered
    from 0, so an anchor is ``<doc-path>#<heading-slug-path>/<ordinal>``.
    """
    policy = policy or ChunkingPolicy()
    by_id, _ = _index(kir.nodes)
    chunks: list[Chunk] = []
    # Ordinals count within a slug path, not within a section. The two coincide
    # except when distinct sections share one path — a document whose preamble
    # precedes its title heading, say, since the title's own slug is omitted —
    # and there the shared counter is what keeps anchors unique.
    ordinals: dict[tuple[str, ...], int] = defaultdict(int)

    for section in _sections(kir):
        heading = section.heading
        for index, (units, kind) in enumerate(_pack(section, policy)):
            ordinal = ordinals[section.slugs]
            ordinals[section.slugs] += 1
            node_ids: list[str] = []
            parts: list[str] = []
            if heading is not None and index == 0:
                # The heading opens its section's first chunk: it is both context
                # for retrieval and document text that must not be lost.
                node_ids.append(heading.id)
                if heading.text:
                    parts.append(heading.text)
            for unit in units:
                node_ids.extend(unit.node_ids)
                parts.append(unit.text)

            text = normalize_text("\n\n".join(part for part in parts if part))
            span = _span(node_ids, by_id) or (0, 0)
            chunks.append(
                Chunk(
                    anchor=build_anchor(doc_path, section.slugs, ordinal),
                    doc_id=kir.doc_id,
                    chunk_digest=digest_text(text),
                    heading_path=section.path,
                    kir_nodes=tuple(node_ids),
                    text=text,
                    tokens=policy.count_tokens(text),
                    lines=span,
                    kind=kind,
                    namespace=namespace,
                )
            )
    return tuple(chunks)
