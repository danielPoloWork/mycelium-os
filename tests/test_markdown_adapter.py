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
    """D-017: authored content is untrusted; HTML is never interpreted.

    Since roadmap 5.40 the tags are *deleted* rather than indexed (ADR-0110) —
    which is a step further from interpreting them, not a step toward it. The
    parser option stays off, nothing here is executed, and what is left is the
    element's own words: this adapter models no element semantics, so a script
    body is words like any other. Telling them apart would need the parse D-017
    refuses.
    """
    doc = parse_markdown("<script>alert(1)</script>\n")
    assert [node.kind for node in doc.kir.nodes] == [NodeKind.PARAGRAPH]
    assert doc.kir.nodes[0].text == "alert(1)"
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


# ---------------------------------------------------------------------------
# Emphasis: parsed away, never modelled (roadmap 5.36, ADR-0107)
# ---------------------------------------------------------------------------


def test_emphasis_is_flattened_into_the_text_and_nowhere_else() -> None:
    """KIR has no emphasis field, and does not need one (ADR-0107).

    `spans` exists for inline *code* because a code span is how a corpus names a
    command (roadmap 5.23, ADR-0094). Bold and italic name nothing: the indexed
    text is the same with or without them, which is the whole reason there is
    nothing to record.
    """
    node = only("A **loud** and *soft* and _quiet_ word.\n", NodeKind.PARAGRAPH)
    assert node.text == "A loud and soft and quiet word."
    assert node.spans == ()


def test_strikethrough_stays_in_the_text_verbatim() -> None:
    """GFM strikethrough is not Profile v1 (spec 03 §3.1: CommonMark *plus GFM
    tables*), so it is prose and stays prose.

    Pinned rather than left to the parser's defaults because it is the premise of
    a refusal: the ingestion lane resolves this construct into plain text, so
    enabling the rule here without re-reading ADR-0107 would close a divergence on
    one side of the corpus and not the other. It occurs in none of the three
    corpora, which is why ADR-0107 declined to widen a frozen contract for it —
    and why roadmap 5.40 left it alone while closing the HTML half.
    """
    assert only("A ~~struck~~ word.\n", NodeKind.PARAGRAPH).text == "A ~~struck~~ word."


# ---------------------------------------------------------------------------
# Raw HTML: the markup goes, the words stay (roadmap 5.40, ADR-0110)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected", "why"),
    [
        ("A <u>lined</u> word.", "A lined word.", "a matched pair is markup"),
        ("A <em>soft</em> word.", "A soft word.", "so is one the profile has an accent for"),
        ("<b>bold *and* italic</b> text", "bold and italic text", "a pair spanning emphasis"),
        (
            '<img alt="A bar chart." src="https://x/y.png"> after',
            "after",
            "a void tag with attributes, unpaired and unclosed",
        ),
        ('<p align="center">caption</p>', "caption", "an attribute-carrying wrapper"),
        ("<!-- prettier-ignore --> kept", "kept", "a comment, whole"),
        ("<!-- see `uv add` later --> kept", "kept", "a comment swallows the code it quotes"),
        ("Pass <package_name> to it.", "Pass <package_name> to it.", "a bare placeholder"),
        ("<link once released>", "<link once released>", "bare words are not attributes"),
        ("<b> <strong> <i>", "<b> <strong> <i>", "unpaired bare tags are an inventory"),
        ("if x < y and a > b", "if x < y and a > b", "a comparison"),
        ("foo <2, and foo >1", "foo <2, and foo >1", "a version range"),
        ("An unterminated <!-- comment", "An unterminated <!-- comment", "half a comment is words"),
    ],
)
def test_raw_html_markup_is_dropped_and_prose_that_looks_like_it_is_not(
    source: str, expected: str, why: str
) -> None:
    """The rule, case by case (ADR-0110).

    `<word>` is both how HTML opens an element and how documentation writes a
    placeholder, and the names collide — `<code>`, `<pre>`, `<script>`, `<path>`,
    `<link>` and `<i>` are all both — so a tag-name list cannot separate them.
    What separates them is syntax a lone placeholder cannot produce: a closing
    tag, a `name=value` attribute, a matching close in the same block, or a
    comment's delimiters. Everything else is somebody's words and stays, because
    leaving markup in costs a few noise terms and deleting a placeholder costs the
    name of the thing the sentence is about.
    """
    assert only(f"{source}\n", NodeKind.PARAGRAPH).text == expected, why


def test_a_quoted_tag_is_what_the_sentence_is_about_and_survives() -> None:
    """Inline code is never reached by the tag rules (ADR-0110, ADR-0094).

    A documentation corpus explains HTML by quoting it — this repository's roadmap
    writes ``` `<p align="center">` ``` five times, and ADR-0107's own table names
    eleven tags in a code span. Deleting those would be deleting the subject.
    """
    node = only('Write `<p align="center">` around it, and `</p>` after.\n', NodeKind.PARAGRAPH)
    assert node.text == 'Write <p align="center"> around it, and </p> after.'
    assert node.spans == ('<p align="center">', "</p>")


def test_a_block_that_was_only_markup_leaves_no_node_behind() -> None:
    """Every CommonMark paragraph has content, so a blank one was markup alone.

    Keeping an empty node would put blank lines into the chunk its content used to
    justify, which is a different way of indexing the wrapper.
    """
    doc = parse_markdown(
        '# Doc\n\n<div align="center">\n<img alt="A chart." src="https://x/y.png">\n</div>\n\n'
        "<!-- TODO: redraw -->\n\nReal prose.\n"
    )
    assert [(node.kind, node.text) for node in doc.kir.nodes] == [
        (NodeKind.HEADING, "Doc"),
        (NodeKind.PARAGRAPH, "Real prose."),
    ]


def test_a_paragraph_holding_only_a_reference_is_not_mistaken_for_markup() -> None:
    """The emptiness test asks for references too: an image with no alt text has
    no `text` and is still a node the graph is built from (spec 03 §6)."""
    doc = parse_markdown("# Doc\n\n![](assets/diagram.png)\n")
    assert [node.kind for node in doc.kir.nodes] == [
        NodeKind.HEADING,
        NodeKind.PARAGRAPH,
        NodeKind.IMAGE,
    ]


def test_the_wrapper_takes_its_layout_whitespace_with_it() -> None:
    """A caption is written on its own line inside the tag that positions it, so
    the newline belongs to the markup and goes with it — otherwise the block opens
    with a blank line the rendered page does not have."""
    source = (
        '<p align="center">\n  <i>Installing Trio\'s dependencies with a warm cache.</i>\n</p>\n'
    )
    assert only(source, NodeKind.PARAGRAPH).text == (
        "Installing Trio's dependencies with a warm cache."
    )


def test_sub_and_sup_are_the_stated_limit() -> None:
    """The one construct this change leaves diverging, and it is docling's doing.

    Stripping gives `H2O`, which is what a browser renders and one FTS token; the
    twin's renderer inserts spaces and gives `H 2 O`, which is three. So these two
    tags disagree in *tokenisation* rather than in markup — a smaller disagreement
    than before and a different one. There are none in any of the three corpora,
    which `tests/test_eval_ingested_corpus.py` asserts rather than remembers.
    """
    assert only("Water is H<sub>2</sub>O.\n", NodeKind.PARAGRAPH).text == "Water is H2O."
