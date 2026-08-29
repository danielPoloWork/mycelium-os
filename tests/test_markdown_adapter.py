# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Markdown → KIR adapter and Profile v1 (roadmap 2.4): every element of the profile
table compiles to the node the spec names, the node list is a well-formed ordered tree,
and unknown vault syntax is tolerated as text."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mycelium.markdown import (
    MarkdownError,
    match_callout,
    parse_markdown,
    profile_markdown_it,
)
from mycelium.sdk.identity import digest_text
from mycelium.sdk.types import KirNode, NodeKind

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
OTHER_ID = "01J1ZF8Q4R6XKQ3F0V9T8B2M7N"


def nodes_of(text: str, kind: NodeKind) -> list[KirNode]:
    return [node for node in parse_markdown(text).kir.nodes if node.kind is kind]


def only(text: str, kind: NodeKind) -> KirNode:
    found = nodes_of(text, kind)
    assert len(found) == 1, f"expected exactly one {kind.value}, got {len(found)}"
    return found[0]


# ---------------------------------------------------------------------------
# The profile table, row by row (spec 03 §3.1)
# ---------------------------------------------------------------------------


def test_commonmark_blocks_map_to_their_kinds() -> None:
    doc = parse_markdown("# H1\n\ntext\n\n- a\n\n1. b\n\n> quoted\n")
    kinds = [node.kind for node in doc.kir.nodes]
    assert NodeKind.HEADING in kinds
    assert NodeKind.PARAGRAPH in kinds
    assert NodeKind.LIST in kinds
    assert NodeKind.LIST_ITEM in kinds
    assert NodeKind.QUOTE in kinds
    lists = nodes_of("- a\n\n1. b\n", NodeKind.LIST)
    assert [node.variant for node in lists] == ["bullet", "ordered"]


def test_gfm_table_becomes_rows_and_cells_without_structural_wrappers() -> None:
    doc = parse_markdown("| a | b |\n|---|---|\n| 1 | 2 |\n")
    rows = [node for node in doc.kir.nodes if node.kind is NodeKind.TABLE_ROW]
    cells = [node for node in doc.kir.nodes if node.kind is NodeKind.TABLE_CELL]
    assert [row.variant for row in rows] == ["header", "body"]
    assert [cell.text for cell in cells] == ["a", "b", "1", "2"]
    table = only("| a | b |\n|---|---|\n| 1 | 2 |\n", NodeKind.TABLE)
    assert all(row.parent == table.id for row in rows)


def test_code_block_keeps_its_language_and_content() -> None:
    fenced = only("```python\nx = 1\n```\n", NodeKind.CODE_BLOCK)
    assert fenced.lang == "python"
    assert fenced.text == "x = 1"
    assert only("```\nplain\n```\n", NodeKind.CODE_BLOCK).lang is None
    # An info string may carry more than the language; only the tag is the language.
    assert only("```python title=x\nx\n```\n", NodeKind.CODE_BLOCK).lang == "python"


@pytest.mark.parametrize(
    ("source", "target", "text"),
    [
        ("[[architecture]]", "architecture", "architecture"),
        ("[[api#Retries]]", "api#Retries", "api#Retries"),
        ("[[api|the retry docs]]", "api", "the retry docs"),
        ("[[folder/note]]", "folder/note", "folder/note"),
    ],
)
def test_wikilinks(source: str, target: str, text: str) -> None:
    node = only(f"see {source} here\n", NodeKind.WIKILINK)
    assert (node.target, node.text) == (target, text)


def test_embeds_are_links_never_transclusions() -> None:
    doc = parse_markdown("![[diagram]]\n")
    embed = only("![[diagram]]\n", NodeKind.EMBED)
    assert embed.target == "diagram"
    # v1 does not transclude: nothing of the target document appears.
    assert [node.kind for node in doc.kir.nodes] == [NodeKind.PARAGRAPH, NodeKind.EMBED]


def test_markdown_links_and_images_keep_their_targets() -> None:
    link = only('[label](https://x "T")\n', NodeKind.LINK)
    assert (link.target, link.text, link.title) == ("https://x", "label", "T")
    image = only("![alt](pic.png)\n", NodeKind.IMAGE)
    assert (image.target, image.text) == ("pic.png", "alt")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("#build-keys", ["build-keys"]),
        ("start #a and #b/c end", ["a", "b/c"]),
        ("(#quoted)", ["quoted"]),
        ("C# is not a tag", []),
        ("issue#3 is not a tag", []),
        ("#123 is not a tag", []),
        ("`#notatag`", []),
    ],
)
def test_inline_tags(source: str, expected: list[str]) -> None:
    assert [node.text for node in nodes_of(f"{source}\n", NodeKind.TAG_REF)] == expected


def test_callouts_carry_type_and_title() -> None:
    doc = parse_markdown("> [!warning] Careful\n> Body here.\n")
    callout = only("> [!warning] Careful\n> Body here.\n", NodeKind.CALLOUT)
    assert (callout.variant, callout.title) == ("warning", "Careful")
    body = [node for node in doc.kir.nodes if node.kind is NodeKind.PARAGRAPH]
    assert [node.text for node in body] == ["Body here."]
    # The marker line itself is not content.
    assert all("[!warning]" not in (node.text or "") for node in doc.kir.nodes)


def test_callout_without_title_and_plain_quote_are_distinguished() -> None:
    assert only("> [!note]\n> text\n", NodeKind.CALLOUT).title is None
    assert nodes_of("> just a quote\n", NodeKind.CALLOUT) == []
    assert len(nodes_of("> just a quote\n", NodeKind.QUOTE)) == 1
    assert match_callout("[!tip] Hint") is not None
    assert match_callout("not a callout") is None


@pytest.mark.parametrize(
    "source",
    [
        "```dataview\nTABLE file.name\n```",
        "<% tp.date.now() %>",
        "= this.file.name",
        "<div>raw html</div>",
        "[[unclosed wikilink",
        "text with $$x^2$$ math",
    ],
)
def test_unknown_vault_syntax_is_tolerated(source: str) -> None:
    """Never breaks the build, never machine-interpreted (profile table, last row)."""
    doc = parse_markdown(f"{source}\n")
    assert doc.kir.nodes
    assert doc.warnings == ()


def test_raw_html_is_data_not_markup() -> None:
    """D-017: authored content is untrusted; HTML is never interpreted."""
    doc = parse_markdown("<script>alert(1)</script>\n")
    assert [node.kind for node in doc.kir.nodes] == [NodeKind.PARAGRAPH]
    assert doc.kir.nodes[0].text == "<script>alert(1)</script>"
    assert profile_markdown_it().options["html"] is False


# ---------------------------------------------------------------------------
# The node list is a well-formed, ordered tree
# ---------------------------------------------------------------------------

STRUCTURED = """# Title

Intro.

## Section A

Text A with [[link-a]].

### Deeper

Text D.

## Section B

Text B.
"""


def test_headings_parent_their_content_and_nest_by_level() -> None:
    doc = parse_markdown(STRUCTURED)
    by_id = {node.id: node for node in doc.kir.nodes}
    headings = {node.text: node for node in doc.kir.nodes if node.kind is NodeKind.HEADING}
    assert headings["Title"].parent is None
    assert headings["Section A"].parent == headings["Title"].id
    assert headings["Deeper"].parent == headings["Section A"].id
    # A sibling heading closes the deeper scope rather than nesting under it.
    assert headings["Section B"].parent == headings["Title"].id
    text_d = next(n for n in doc.kir.nodes if n.text == "Text D.")
    assert by_id[str(text_d.parent)].text == "Deeper"


@given(
    document=st.lists(
        st.sampled_from(
            [
                "# H1",
                "## H2",
                "### H3",
                "text",
                "- item",
                "1. item",
                "> quote",
                "> [!note] N",
                "```py\nx\n```",
                "| a |\n|---|\n| 1 |",
                "[[wiki]]",
                "![[embed]]",
                "#tag",
                "[l](u)",
                "![i](s.png)",
                "---",
                "<b>html</b>",
            ]
        ),
        max_size=12,
    )
)
def test_node_list_is_always_a_well_formed_ordered_tree(document: list[str]) -> None:
    nodes = parse_markdown("\n\n".join(document) + "\n").kir.nodes
    ids = [node.id for node in nodes]
    assert len(set(ids)) == len(ids)
    assert [node.ord for node in nodes] == list(range(len(nodes)))
    assert ids == [f"n{node.ord + 1}" for node in nodes]
    seen: set[str] = set()
    for node in nodes:
        # A parent is always an earlier node, so the list is a topological order
        # and cannot contain a cycle.
        assert node.parent is None or node.parent in seen
        seen.add(node.id)


@given(
    heading=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=12
    ),
    body=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=30
    ),
)
def test_authored_text_reaches_kir(heading: str, body: str) -> None:
    doc = parse_markdown(f"# {heading}\n\n{body}\n")
    texts = [node.text for node in doc.kir.nodes]
    assert heading in texts
    assert body in texts


# ---------------------------------------------------------------------------
# Source locators, identity, and digests
# ---------------------------------------------------------------------------


def test_line_locators_point_at_the_source_file_not_the_body() -> None:
    source = f"---\nmycelium_id: {DOC_ID}\n---\n\n# Heading\n\nParagraph.\n"
    doc = parse_markdown(source)
    lines = source.split("\n")
    for node in doc.kir.nodes:
        assert node.src is not None
        start, end = node.src.lines or (0, 0)
        assert start <= end
        assert (node.text or "").split("\n")[0] in "\n".join(lines[start - 1 : end])
    heading = next(n for n in doc.kir.nodes if n.kind is NodeKind.HEADING)
    assert heading.src is not None and heading.src.lines == (5, 5)


def test_identity_resolution() -> None:
    pinned = f"---\nmycelium_id: {DOC_ID}\n---\nbody\n"
    assert parse_markdown(pinned).kir.doc_id == DOC_ID
    assert parse_markdown("body\n", doc_id=DOC_ID).kir.doc_id == DOC_ID
    # Unpinned documents get a fresh identity; the source is never edited here.
    minted = parse_markdown("body\n").kir.doc_id
    assert minted != parse_markdown("body\n").kir.doc_id


def test_conflicting_identity_is_refused() -> None:
    pinned = f"---\nmycelium_id: {DOC_ID}\n---\nbody\n"
    with pytest.raises(MarkdownError, match="contradicts"):
        parse_markdown(pinned, doc_id=OTHER_ID)


def test_source_digest_covers_the_whole_file_and_ignores_line_endings() -> None:
    source = f"---\nmycelium_id: {DOC_ID}\n---\n\n# H\n\ntext\n"
    doc = parse_markdown(source)
    assert doc.kir.source_digest == digest_text(source)
    assert parse_markdown(source.replace("\n", "\r\n")).kir.source_digest == doc.kir.source_digest


def test_frontmatter_warnings_reach_the_kir_document() -> None:
    doc = parse_markdown("---\norigin: invented\n---\nbody\n")
    assert doc.kir.warnings == doc.warnings
    assert any("origin" in warning for warning in doc.warnings)


def test_empty_document_is_lawful() -> None:
    doc = parse_markdown("")
    assert doc.kir.nodes == ()
    assert doc.kir.warnings == ()
