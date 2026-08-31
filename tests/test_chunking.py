# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Heading-bounded chunker (roadmap 2.5): the spec's chunking policy holds, anchors are
unique and readable, and — the invariant this item exists for — no text is ever lost."""

from collections.abc import Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mycelium.chunking import ChunkingPolicy, chunk_document, estimate_tokens
from mycelium.markdown import parse_markdown
from mycelium.sdk.identity import digest_text, parse_anchor
from mycelium.sdk.types import Chunk, ChunkKind, KirDocument, NodeKind

DOC_PATH = "knowledge/architecture.md"

INLINE_KINDS = {
    NodeKind.LINK,
    NodeKind.IMAGE,
    NodeKind.WIKILINK,
    NodeKind.EMBED,
    NodeKind.TAG_REF,
}


def chunk(source: str, **kwargs: object) -> tuple[Chunk, ...]:
    kir = parse_markdown(source).kir
    return chunk_document(kir, doc_path=DOC_PATH, **kwargs)  # type: ignore[arg-type]


def authored_texts(kir: KirDocument) -> list[str]:
    """Every piece of text KIR carries, in document order.

    Reference nodes are excluded: their text is a substring of the block that
    contains them, so counting them would assert the same content twice.
    """
    texts: list[str] = []
    for node in kir.nodes:
        if node.kind in INLINE_KINDS:
            continue
        if node.kind is NodeKind.CALLOUT and node.title:
            texts.append(node.title)
        if node.text and node.text.strip():
            texts.append(node.text)
    return texts


# ---------------------------------------------------------------------------
# The invariant: ordered chunk texts ⊇ the document's text (spec 03 §5)
# ---------------------------------------------------------------------------

document_strategy = st.lists(
    st.sampled_from(
        [
            "# Title",
            "## Section",
            "## Section",  # a deliberate duplicate: sibling slugs must not collide
            "### Sub",
            "#### Deep",
            "Some prose here.",
            "More prose, longer, with several words in it.",
            "- item one\n- item two",
            "1. first\n2. second",
            "> quoted text",
            "> [!note] Title\n> callout body",
            "```python\nvalue = 1\n```",
            "| a | b |\n|---|---|\n| 1 | 2 |",
            "Text with [[wikilink]] and [link](https://x) and #tag.",
            "![[embedded]]",
            "---",
        ]
    ),
    max_size=14,
)


@settings(max_examples=200)
@given(blocks=document_strategy)
def test_no_content_loss(blocks: list[str]) -> None:
    """Every KIR text appears in the ordered chunk texts, in document order."""
    source = "\n\n".join(blocks) + "\n"
    kir = parse_markdown(source).kir
    chunks = chunk_document(kir, doc_path=DOC_PATH)
    joined = "\n\n".join(chunk.text for chunk in chunks)

    cursor = 0
    for text in authored_texts(kir):
        found = joined.find(text, cursor)
        assert found >= 0, f"lost {text!r} from the chunk stream"
        # Consume the match: each piece needs its own occurrence, so a repeated
        # block cannot be satisfied twice by a single one.
        cursor = found + len(text)


@given(blocks=document_strategy)
def test_chunks_are_well_formed(blocks: list[str]) -> None:
    source = "\n\n".join(blocks) + "\n"
    kir = parse_markdown(source).kir
    chunks = chunk_document(kir, doc_path=DOC_PATH)
    node_ids = {node.id for node in kir.nodes}

    anchors = [chunk.anchor for chunk in chunks]
    assert len(set(anchors)) == len(anchors), "anchors must be unique within a document"

    for chunk_record in chunks:
        assert chunk_record.doc_id == kir.doc_id
        assert chunk_record.chunk_digest == digest_text(chunk_record.text)
        assert set(chunk_record.kir_nodes) <= node_ids
        assert chunk_record.lines[0] <= chunk_record.lines[1]
        parsed = parse_anchor(chunk_record.anchor)
        assert parsed.doc_path == DOC_PATH
        assert len(parsed.heading_slugs) <= len(chunk_record.heading_path)


@given(blocks=document_strategy)
def test_ordinals_are_contiguous_per_anchor_scope(blocks: list[str]) -> None:
    chunks = chunk("\n\n".join(blocks) + "\n")
    by_scope: dict[tuple[str, ...], list[int]] = {}
    for chunk_record in chunks:
        parsed = parse_anchor(chunk_record.anchor)
        by_scope.setdefault(parsed.heading_slugs, []).append(parsed.ordinal)
    for ordinals in by_scope.values():
        assert ordinals == list(range(len(ordinals)))


# ---------------------------------------------------------------------------
# The chunking policy (spec 03 §5)
# ---------------------------------------------------------------------------

STRUCTURED = """# Architecture

Intro paragraph.

## Event Bus

Bus text.

| a | b |
|---|---|
| 1 | 2 |

```python
x = 1
```
"""


def test_sections_become_chunks_with_their_heading_path() -> None:
    chunks = chunk(STRUCTURED)
    assert [c.heading_path for c in chunks] == [
        ("Architecture",),
        ("Architecture", "Event Bus"),
        ("Architecture", "Event Bus"),
        ("Architecture", "Event Bus"),
    ]
    # The heading opens its section's first chunk: context for retrieval, and
    # document text that must survive.
    assert chunks[1].text.startswith("Event Bus")


def test_tables_and_code_blocks_are_atomic_chunks() -> None:
    chunks = chunk(STRUCTURED)
    kinds = {c.kind for c in chunks}
    assert kinds == {ChunkKind.PROSE, ChunkKind.TABLE, ChunkKind.CODE}
    table = next(c for c in chunks if c.kind is ChunkKind.TABLE)
    code = next(c for c in chunks if c.kind is ChunkKind.CODE)
    # Atomic: nothing else shares the chunk, and the table reads row-major.
    assert table.text == "a | b\n1 | 2"
    assert code.text == "x = 1"


def test_oversize_sections_split_at_paragraph_boundaries() -> None:
    paragraphs = [f"paragraph {index} " + "word " * 60 for index in range(10)]
    source = "## Section\n\n" + "\n\n".join(p.strip() for p in paragraphs) + "\n"
    chunks = chunk(source, policy=ChunkingPolicy(target_tokens=50, max_tokens=250))
    assert len(chunks) > 1
    # Every chunk is made of whole paragraphs — nothing is cut mid-sentence.
    intact = {p.strip() for p in paragraphs} | {"Section"}
    for chunk_record in chunks:
        assert set(chunk_record.text.split("\n\n")) <= intact
        assert chunk_record.tokens <= 250 + estimate_tokens("Section")
    assert [parse_anchor(c.anchor).ordinal for c in chunks] == list(range(len(chunks)))


def test_a_single_oversize_paragraph_is_never_split_mid_sentence() -> None:
    giant = "word " * 500
    chunks = chunk(
        f"## Section\n\n{giant.strip()}\n",
        policy=ChunkingPolicy(target_tokens=10, max_tokens=50),
    )
    assert len(chunks) == 1
    assert chunks[0].tokens > 50  # kept whole: a paragraph is the smallest boundary


def test_prose_accumulates_up_to_the_ceiling() -> None:
    source = "## S\n\n" + "\n\n".join(f"para {i}" for i in range(20)) + "\n"
    chunks = chunk(source, policy=ChunkingPolicy(max_tokens=800))
    assert len(chunks) == 1  # twenty short paragraphs fit in one chunk


def _paragraphs(count: int, words: int) -> str:
    body = (chr(10) * 2).join(f"p{index} " + "word " * words for index in range(count))
    return f"## S\n\n{body}\n"


def _paragraphs_of(chunks: Sequence[Chunk]) -> list[str]:
    return [part for record in chunks for part in record.text.split(chr(10) * 2)]


def test_lowering_the_target_shrinks_chunks() -> None:
    """The knob steers size: same document, same ceiling, smaller chunks."""
    source = _paragraphs(20, 40)
    wide = chunk(source, policy=ChunkingPolicy(target_tokens=800, max_tokens=800))
    narrow = chunk(source, policy=ChunkingPolicy(target_tokens=100, max_tokens=800))

    assert len(narrow) > len(wide)
    assert max(record.tokens for record in narrow) < max(record.tokens for record in wide)
    # Different boundaries, same document: the paragraphs come back in order.
    assert _paragraphs_of(narrow) == _paragraphs_of(wide)


def test_the_target_at_the_ceiling_packs_exactly_as_the_ceiling_alone_did() -> None:
    """`target_tokens == max_tokens` is fill-to-the-ceiling, unchanged (ADR-0023).

    That is what makes the target a steering knob rather than a second ceiling:
    at the top of its range it disappears, because a run can only have reached the
    ceiling where adding anything would already have breached it.
    """
    source = _paragraphs(30, 30)
    for record in chunk(source, policy=ChunkingPolicy(target_tokens=500, max_tokens=500)):
        assert record.tokens <= 500 + estimate_tokens("S")


def test_packing_never_breaches_the_ceiling_whatever_the_target() -> None:
    source = _paragraphs(24, 25)
    for target in (10, 50, 200, 400):
        chunks = chunk(source, policy=ChunkingPolicy(target_tokens=target, max_tokens=400))
        assert all(record.tokens <= 400 + estimate_tokens("S") for record in chunks)


def test_headings_with_no_content_still_produce_a_citable_chunk() -> None:
    chunks = chunk("## Empty Section\n\n### Child\n\ntext\n")
    empty = next(c for c in chunks if c.heading_path == ("Empty Section",))
    assert empty.text == "Empty Section"


# ---------------------------------------------------------------------------
# Anchors (the collision cases the identity library left to the chunker)
# ---------------------------------------------------------------------------


def test_sibling_headings_that_slug_alike_are_numbered() -> None:
    chunks = chunk("## Overview\n\na\n\n## Overview\n\nb\n")
    assert [c.anchor for c in chunks] == [
        f"{DOC_PATH}#overview/0",
        f"{DOC_PATH}#overview-2/0",
    ]


def test_same_slug_under_different_parents_does_not_collide() -> None:
    chunks = chunk("## A\n\n### X\n\na\n\n## B\n\n### X\n\nb\n")
    anchors = [c.anchor for c in chunks]
    assert f"{DOC_PATH}#a/x/0" in anchors
    assert f"{DOC_PATH}#b/x/0" in anchors


def test_the_title_heading_is_omitted_from_anchors() -> None:
    """A single H1 names the document, which the path already identifies."""
    chunks = chunk("# Doc Title\n\nintro\n\n## Section\n\ntext\n")
    assert [c.anchor for c in chunks] == [f"{DOC_PATH}#/0", f"{DOC_PATH}#section/0"]
    assert chunks[0].heading_path == ("Doc Title",)


def test_several_h1s_are_sections_not_titles() -> None:
    chunks = chunk("# One\n\na\n\n# Two\n\nb\n")
    assert [c.anchor for c in chunks] == [f"{DOC_PATH}#one/0", f"{DOC_PATH}#two/0"]


def test_preamble_and_title_share_a_scope_without_colliding() -> None:
    """Both have an empty slug path, so the shared ordinal counter separates them."""
    chunks = chunk("Preamble text.\n\n# Title\n\nBody.\n")
    assert [c.anchor for c in chunks] == [f"{DOC_PATH}#/0", f"{DOC_PATH}#/1"]
    assert chunks[0].heading_path == ()
    assert chunks[1].heading_path == ("Title",)


# ---------------------------------------------------------------------------
# Token estimation and policy validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("", 0), ("one two three", 3), ("hello, world!", 4), ("設計", 2), ("a-b", 3)],
)
def test_estimate_tokens(text: str, expected: int) -> None:
    assert estimate_tokens(text) == expected


@given(text=st.text(max_size=200))
def test_token_estimate_is_deterministic_and_bounded(text: str) -> None:
    assert estimate_tokens(text) == estimate_tokens(text)
    assert 0 <= estimate_tokens(text) <= len(text)


def test_a_custom_token_counter_is_honoured() -> None:
    chunks = chunk(
        "## S\n\n" + "\n\n".join(f"para {i}" for i in range(6)) + "\n",
        policy=ChunkingPolicy(target_tokens=1, max_tokens=10, count_tokens=len),
    )
    assert len(chunks) > 1


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"max_tokens": 0}, "positive"),
        ({"target_tokens": 900}, "exceeds"),
        ({"overlap_tokens": 50}, "overlap is not implemented"),
    ],
)
def test_invalid_policies_are_refused(kwargs: dict, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        ChunkingPolicy(**kwargs)


def test_empty_document_yields_no_chunks() -> None:
    assert chunk("") == ()


def test_namespace_is_carried_through() -> None:
    chunks = chunk("# T\n\ntext\n", namespace="team-a")
    assert all(c.namespace == "team-a" for c in chunks)
