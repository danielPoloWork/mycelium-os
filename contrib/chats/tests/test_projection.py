# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The projection: determinism, structural safety, and message anchors.

The claims under test:

**Same record, byte-identical Markdown** (doc 08 §10, gate 2) — and independent
of `[chunking]`, which is what makes that promise absolute rather than relative
to a configuration.

**A message cannot break the document it sits in.** Content is verbatim and
arbitrary, so a turn containing `## something` must not open a section — the
reason the content is quoted inside a callout.

**One message, one chunk, one anchor**, which is doc 08 §7's chunking unit and
the thing spec 03 §3.1's unimplemented callout atomicity would otherwise have
delivered (roadmap 5.13).

**The frontmatter says what the compiler needs and nothing it would refuse.**
"""

from datetime import UTC, datetime
from pathlib import Path

from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.markdown import parse_frontmatter, parse_markdown
from mycelium.sdk.identity import heading_slug
from mycelium_chats.archive import import_text
from mycelium_chats.paths import archive_path, projection_path
from mycelium_chats.projection import collection_of, message_heading, project_transcript
from mycelium_chats.record import Conversation, Fragment, Message, Transcript
from mycelium_chats.settings import ChatsSettings

IMPORTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
CONV = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
DIGEST = "sha256:" + "ab" * 32


def transcript(*lines: Message | Fragment, title: str = "A conversation") -> Transcript:
    return Transcript(
        conversation=Conversation(
            conv_id=CONV,
            title=title,
            project="research",
            provider="chatgpt",
            imported_at=IMPORTED,
            source_digest=DIGEST,
            started_at=IMPORTED,
        ),
        lines=lines,
    )


def message(seq: int, role: str, content: str, **kwargs: object) -> Message:
    return Message(conv_id=CONV, seq=seq, role=role, content=content, **kwargs)  # type: ignore[arg-type]


def render(item: Transcript) -> str:
    record = archive_path(
        project=item.conversation.project,
        title=item.conversation.title,
        conv_id=item.conversation.conv_id,
        dated=IMPORTED,
        zone=UTC,
    )
    return project_transcript(item, record, projection=projection_path(record, "knowledge")).text


# ---------------------------------------------------------------------------
# Gate 2: determinism
# ---------------------------------------------------------------------------


def test_the_same_record_renders_byte_identically() -> None:
    item = transcript(message(1, "user", "Ask"), message(2, "assistant", "Answer"))
    assert render(item) == render(item)


def test_the_projection_does_not_depend_on_the_chunking_configuration() -> None:
    """The reason gate 2 is absolute: a projection that varied with the chunker
    would rewrite committed tier-2 files when somebody tuned it."""
    item = transcript(message(1, "user", "word " * 500))
    text = render(item)

    for policy in (ChunkingPolicy(), ChunkingPolicy(target_tokens=40, max_tokens=60)):
        chunks = chunk_document(
            parse_markdown(text, doc_id=CONV).kir, doc_path="a.md", policy=policy
        )
        assert chunks, "the projection is chunkable under either policy"
    assert render(item) == text


# ---------------------------------------------------------------------------
# Structural safety
# ---------------------------------------------------------------------------


def test_a_message_containing_a_heading_does_not_open_a_section() -> None:
    """Quoting is not enough — CommonMark allows a heading inside a blockquote —
    so the projector escapes it, and the indexed text is unchanged."""
    item = transcript(
        message(1, "user", "Look:\n\n## Not a section\n\ntext under it"),
        message(2, "assistant", "Indeed."),
    )
    text = render(item)
    parsed = parse_markdown(text, doc_id=CONV)
    headings = [
        node.text for node in parsed.kir.nodes if node.kind.value == "heading" and node.text
    ]
    body = " ".join(node.text for node in parsed.kir.nodes if node.text)

    assert headings == ["A conversation", "1 · user", "2 · assistant"]
    assert "\\## Not a section" in text, "escaped in the file"
    assert "## Not a section" in body, "and unescaped in what the index reads"


def test_a_setext_underline_cannot_swallow_the_callout() -> None:
    """The nastier half: `---` under a line of text makes a setext heading, and
    that heading took the whole callout with it before it was escaped."""
    item = transcript(message(1, "user", "Title line\n---\nmore text"))
    parsed = parse_markdown(render(item), doc_id=CONV)
    headings = [
        node.text for node in parsed.kir.nodes if node.kind.value == "heading" and node.text
    ]
    body = " ".join(node.text for node in parsed.kir.nodes if node.text)

    assert headings == ["A conversation", "1 · user"]
    assert "Title line\n---\nmore text" in body


def test_neutralising_leaves_everything_else_alone() -> None:
    from mycelium_chats.projection import neutralise

    for untouched in ("- a list item", "```python", "| a | table |", "> quoted", "***", "text"):
        assert neutralise(untouched) == untouched
    assert neutralise("## heading") == "\\## heading"
    assert neutralise("---") == "\\---"


def test_a_message_containing_a_fence_or_a_rule_stays_inside_its_turn() -> None:
    item = transcript(
        message(1, "user", "```python\nx = 1\n```\n\n---\n\nAnd a --- rule."),
        message(2, "assistant", "Noted."),
    )
    chunks = chunk_document(
        parse_markdown(render(item), doc_id=CONV).kir, doc_path="a.md", policy=ChunkingPolicy()
    )
    anchors = [chunk.anchor for chunk in chunks]

    assert anchors == ["a.md#/0", "a.md#1-user/0", "a.md#2-assistant/0"]


def test_a_blank_line_in_a_message_does_not_split_the_callout() -> None:
    """A bare blank line would end the blockquote and make one turn two units."""
    item = transcript(message(1, "user", "First para.\n\nSecond para."))
    text = render(item)

    assert "\n>\n" in text, "the blank line is quoted too"
    chunks = chunk_document(
        parse_markdown(text, doc_id=CONV).kir, doc_path="a.md", policy=ChunkingPolicy()
    )
    assert [chunk.anchor for chunk in chunks] == ["a.md#/0", "a.md#1-user/0"]


# ---------------------------------------------------------------------------
# Anchors: one message, one chunk
# ---------------------------------------------------------------------------


def test_each_message_becomes_one_chunk_with_a_message_anchor() -> None:
    item = transcript(
        message(1, "user", "Ask"),
        message(2, "assistant", "Answer", model="gpt-5"),
        message(3, "user", "Thanks"),
    )
    chunks = chunk_document(
        parse_markdown(render(item), doc_id=CONV).kir, doc_path="a.md", policy=ChunkingPolicy()
    )

    # The first chunk is the title and metadata line; then one per message.
    assert [chunk.anchor for chunk in chunks] == [
        "a.md#/0",
        "a.md#1-user/0",
        "a.md#2-assistant/0",
        "a.md#3-user/0",
    ]
    assert "Answer" in chunks[2].text


def test_the_heading_slug_is_the_message_anchor() -> None:
    assert heading_slug(message_heading(message(12, "assistant", "x"))) == "12-assistant"
    assert heading_slug(message_heading(Fragment(conv_id=CONV, seq=3, content="x"))) == "3-fragment"


def test_a_messages_own_words_stay_out_of_its_heading() -> None:
    """Heading text is indexed at weight 3.0, so a turn's prose there would be
    counted twice — and the anchor would move whenever the text did."""
    assert message_heading(message(1, "user", "Some very distinctive words")) == "1 · user"


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def test_the_frontmatter_is_readable_by_the_compilers_own_parser() -> None:
    item = transcript(message(1, "user", "Ask"))
    parsed = parse_frontmatter(render(item))

    assert parsed.frontmatter.origin is not None and parsed.frontmatter.origin.value == "ingested"
    assert parsed.frontmatter.collection == "chats/research"
    assert parsed.frontmatter.source_digest == DIGEST
    assert parsed.frontmatter.title == "A conversation"


def test_the_projection_does_not_write_mycelium_id() -> None:
    """`mycelium build` owns that field (spec 03 §3); a projector that stamped it
    would be the second writer of a single-writer field."""
    item = transcript(message(1, "user", "Ask"))
    assert parse_frontmatter(render(item)).frontmatter.mycelium_id is None
    assert "mycelium_id" not in render(item)


def test_the_conversation_keys_land_in_properties_never_machine_read() -> None:
    """Doc 08 §7 asks for `provider`, `project` and `started_at`; spec 03 §3's
    field set is closed, so they are preserved as opaque properties (ADR-0077)."""
    item = transcript(message(1, "user", "Ask"))
    properties = parse_frontmatter(render(item)).frontmatter.properties

    assert properties["provider"] == "chatgpt"
    assert properties["project"] == "research"
    assert properties["conv_id"] == CONV
    assert str(properties["started_at"]).startswith("2026-09-01")


def test_the_collection_carries_the_project_for_retrieval() -> None:
    item = transcript(message(1, "user", "Ask"))
    assert collection_of(item.conversation) == "chats/research"


# ---------------------------------------------------------------------------
# What the body says
# ---------------------------------------------------------------------------


def test_the_callout_names_the_role_the_model_and_the_time() -> None:
    stamped = datetime(2026, 9, 1, 12, 30, tzinfo=UTC)
    item = transcript(message(1, "assistant", "Answer", model="gpt-5", ts=stamped))
    text = render(item)

    assert "> [!assistant] gpt-5 · 2026-09-01T12:30:00Z" in text


def test_a_fragment_says_what_it_is() -> None:
    item = transcript(Fragment(conv_id=CONV, seq=1, content="unsegmented residue"))
    text = render(item)

    assert "> [!fragment] preserved, unsegmented" in text
    assert "unsegmented residue" in text


def test_inferred_structure_is_stated_in_prose_a_reader_meets() -> None:
    item = Transcript(
        conversation=Conversation(
            conv_id=CONV,
            title="Pasted",
            project="research",
            provider="pasted",
            imported_at=IMPORTED,
            source_digest=DIGEST,
            structure_inferred=True,
        ),
        lines=(message(1, "user", "Ask"),),
    )
    assert "**inferred**" in render(item)


def test_the_metadata_line_names_the_provider_and_the_project() -> None:
    item = transcript(message(1, "user", "Ask"), message(2, "assistant", "Answer", model="gpt-5"))
    text = render(item)

    assert "Archived conversation from **chatgpt**" in text
    assert "project `research`" in text
    assert "model `gpt-5`" in text


# ---------------------------------------------------------------------------
# End to end, through a real import
# ---------------------------------------------------------------------------


def test_an_imported_conversation_projects_where_the_spec_says(
    repo: Path, fixtures: Path, settings: ChatsSettings
) -> None:
    outcomes, _ = import_text(
        repo,
        (fixtures / "transcript.md").read_text("utf-8"),
        source_uri="transcript.md",
        project="research",
        settings=settings,
        knowledge_dir="knowledge",
        now=IMPORTED,
    )
    (only,) = outcomes
    assert only.projection_path is not None
    text = (repo / only.projection_path).read_text("utf-8")

    assert only.projection_path.parts[:4] == ("knowledge", "evidence", "chats", "research")
    assert text.startswith("---\n")
    assert text.endswith("\n")
    assert "\r" not in text, "LF only, like every other file this project writes"
