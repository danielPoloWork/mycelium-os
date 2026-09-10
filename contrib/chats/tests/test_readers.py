# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Readers: what each input shape yields, and what a reader refuses to guess.

The claims under test:

**A provider export is read from its own structure**, including the parts a
naive reader loses — ChatGPT's abandoned edit branches, its non-text parts,
Claude's two body shapes.

**Roles are translated at the edge**, so a consumer of a record never has to
know which export it came from, and an untranslated word is preserved rather
than dropped.

**Sniffing never chooses for an operator who chose**, and the reader that
matches anything is reached last.

**A paste is inferred structure, and an unlabelled paste invents no speakers.**
"""

from pathlib import Path

import pytest

from mycelium_chats.readers import ImportContext, ReaderError, reader_for, reader_ids
from mycelium_chats.readers.base import normalise_role
from mycelium_chats.record import Fragment, Message

CONTEXT = ImportContext(project="research", source_uri="fixture")


def read(name: str, fixtures: Path, *, provider: str | None = None, mapping: dict | None = None):
    text = (fixtures / name).read_text(encoding="utf-8")
    reader = reader_for(text, provider=provider, source_uri=name, mapping=mapping)
    return reader, reader.read(
        text, ImportContext(project="research", source_uri=name, mapping=mapping or {})
    )


# ---------------------------------------------------------------------------
# Resolution: pinned first, sniffed second, permissive last
# ---------------------------------------------------------------------------


def test_every_reader_is_registered() -> None:
    assert reader_ids() == ("chatgpt", "claude", "generic", "transcript", "pasted")


def test_each_export_is_recognised_without_being_told(fixtures: Path) -> None:
    """The sniff order matters: both providers are JSON arrays of objects."""
    assert read("chatgpt-export.json", fixtures)[0].id == "chatgpt"
    assert read("claude-export.json", fixtures)[0].id == "claude"
    assert read("transcript.md", fixtures)[0].id == "transcript"
    assert read("pasted-labelled.txt", fixtures)[0].id == "pasted"
    assert read("pasted-unlabelled.txt", fixtures)[0].id == "pasted"


def test_an_unknown_json_export_is_refused_with_the_remedy(fixtures: Path) -> None:
    """Two rules meeting: `generic` is out until configured, and `pasted` refuses
    JSON — so an export no reader knows produces an actionable refusal rather
    than an archive of punctuation."""
    text = (fixtures / "generic-export.json").read_text(encoding="utf-8")
    with pytest.raises(ReaderError, match="configure \\[chats\\] mapping"):
        reader_for(text, provider=None, source_uri="generic-export.json", mapping=None)

    mapping = {
        "conversations": "threads",
        "messages": "history",
        "role": "speaker",
        "content": "body",
    }
    assert reader_for(text, provider=None, source_uri="x.json", mapping=mapping).id == "generic"


def test_a_paste_is_not_confused_with_a_data_file() -> None:
    from mycelium_chats.readers.pasted import PastedTextReader

    assert PastedTextReader().sniff("You said:\nhello\n", source_uri="p.txt")
    assert not PastedTextReader().sniff('{"messages": []}', source_uri="x.json")


def test_a_pinned_provider_wins_over_the_sniff(fixtures: Path) -> None:
    """An operator who names a reader gets it, and its own error explains the fit."""
    text = (fixtures / "chatgpt-export.json").read_text(encoding="utf-8")
    reader = reader_for(text, provider="claude", source_uri="x.json")
    assert reader.id == "claude"
    with pytest.raises(ReaderError, match="chat_messages"):
        reader.read(text, CONTEXT)


def test_an_unknown_provider_lists_the_readers() -> None:
    with pytest.raises(ReaderError, match="chatgpt, claude, generic, transcript, pasted"):
        reader_for("anything", provider="gemini-export", source_uri="x")


def test_empty_input_is_refused_rather_than_archived() -> None:
    with pytest.raises(ReaderError):
        reader_for("   \n", provider=None, source_uri="empty.txt")


# ---------------------------------------------------------------------------
# ChatGPT
# ---------------------------------------------------------------------------


def test_chatgpt_reads_the_branch_the_user_last_saw(fixtures: Path) -> None:
    _, result = read("chatgpt-export.json", fixtures)
    first = result.conversations[0]
    messages = [line for line in first.lines if isinstance(line, Message)]

    assert first.title == "Webhook retry design"
    assert first.provider_conv_id == "c-webhook-1"
    assert [line.role for line in messages] == ["user", "assistant", "user", "assistant"]
    assert "Exponential backoff" in messages[1].content
    assert messages[1].model == "gpt-5"
    assert first.recognised == 4
    assert not first.structure_inferred


def test_chatgpt_keeps_an_abandoned_edit_branch_rather_than_dropping_it(fixtures: Path) -> None:
    """The finding the reader was written around: a regenerated turn leaves its
    predecessor in the export, and a parent-walk never visits it."""
    _, result = read("chatgpt-export.json", fixtures)
    fragments = [line for line in result.conversations[0].lines if isinstance(line, Fragment)]

    assert [line.content for line in fragments] == ["Linear backoff is simpler."]
    assert fragments[0].meta["reason"] == "abandoned_branch"
    assert any("abandoned edit branch" in note for note in result.warnings)


def test_chatgpt_preserves_a_non_text_part_instead_of_flattening_it(fixtures: Path) -> None:
    _, result = read("chatgpt-export.json", fixtures)
    second = result.conversations[1]
    first_turn = second.lines[0]

    assert isinstance(first_turn, Message)
    assert first_turn.content == "What does this diagram show?"
    assert first_turn.meta["content_type"] == "multimodal_text"
    assert first_turn.meta["parts"] == [
        {"asset_pointer": "file-service://file-abc", "size_bytes": 20481}
    ]


def test_chatgpt_preserves_conversation_keys_it_does_not_interpret(fixtures: Path) -> None:
    _, result = read("chatgpt-export.json", fixtures)
    assert result.conversations[0].meta["moderation_results"] == []


def test_chatgpt_reads_both_conversations_in_one_export(fixtures: Path) -> None:
    _, result = read("chatgpt-export.json", fixtures)
    assert [item.title for item in result.conversations] == [
        "Webhook retry design",
        "Multimodal note",
    ]


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


def test_claude_reads_both_body_shapes(fixtures: Path) -> None:
    _, result = read("claude-export.json", fixtures)
    lines = result.conversations[0].lines
    messages = [line for line in lines if isinstance(line, Message)]

    assert result.conversations[0].title == "Anchor stability"
    assert result.conversations[0].provider_conv_id == "9f0c1d2e-claude-export"
    # m-1 carries a flat `text`; m-2 carries typed `content` blocks.
    assert messages[0].content.startswith("Do citations survive")
    assert messages[1].content.startswith("Yes. A citation keys on")
    assert [line.role for line in messages] == ["user", "assistant", "user", "assistant"]


def test_claude_preserves_a_block_type_it_cannot_render(fixtures: Path) -> None:
    """A `thinking` block is not text the assistant said, so it is kept whole
    rather than concatenated into the prose."""
    _, result = read("claude-export.json", fixtures)
    assistant = result.conversations[0].lines[1]

    assert isinstance(assistant, Message)
    assert "Checking the identity rules" not in assistant.content
    assert assistant.meta["blocks"] == [
        {"type": "thinking", "thinking": "Checking the identity rules."}
    ]


def test_claude_reports_attachments_it_has_no_bytes_for(fixtures: Path) -> None:
    _, result = read("claude-export.json", fixtures)
    third = result.conversations[0].lines[2]

    assert isinstance(third, Message)
    assert third.meta["attachments"] == [{"file_name": "mycelium.toml", "file_size": 412}]
    assert any("attachments the export does not contain" in note for note in result.warnings)


def test_claude_timestamps_are_read_as_utc(fixtures: Path) -> None:
    _, result = read("claude-export.json", fixtures)
    started = result.conversations[0].started_at

    assert started is not None
    assert started.isoformat().startswith("2026-07-31T09:02:11")
    assert started.utcoffset() is not None and started.utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "role"),
    [
        ("user", "user"),
        ("human", "user"),
        ("You", "user"),
        ("assistant", "assistant"),
        ("bot", "assistant"),
        ("GPT", "assistant"),
        ("Claude", "assistant"),
        ("system", "system"),
        ("tool", "tool"),
        ("function", "tool"),
    ],
)
def test_a_providers_word_for_a_role_maps_onto_the_four(word: str, role: str) -> None:
    assert normalise_role(word) == role


def test_an_unmapped_role_falls_back_and_the_original_survives(fixtures: Path) -> None:
    """The mapping never loses what it could not place — `meta` keeps the word."""
    from mycelium_chats.readers.claude import ClaudeReader

    export = '[{"uuid": "u", "chat_messages": [{"sender": "oracle", "text": "hello"}]}]'
    result = ClaudeReader().read(export, CONTEXT)
    line = result.conversations[0].lines[0]

    assert isinstance(line, Message)
    assert line.role == "user"  # the declared fallback
    assert line.meta["provider_role"] == "oracle"


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


def test_a_transcript_is_read_from_its_markup(fixtures: Path) -> None:
    _, result = read("transcript.md", fixtures)
    conversation = result.conversations[0]
    messages = [line for line in conversation.lines if isinstance(line, Message)]

    assert conversation.title == "Snapshot publication"
    assert [line.role for line in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1].model == "gpt-5"
    # Markup is structure the source states, so nothing was inferred.
    assert not conversation.structure_inferred
    # A code fence inside a turn is part of what was said.
    assert "swap_current(mycelium_dir, snapshot_id)" in messages[1].content


def test_a_transcripts_preamble_is_kept_rather_than_attributed(fixtures: Path) -> None:
    _, result = read("transcript.md", fixtures)
    first = result.conversations[0].lines[0]

    assert isinstance(first, Fragment)
    assert first.meta["reason"] == "preamble"
    assert "a transcript kept by hand" in first.content


def test_this_modules_own_callout_projection_is_re_readable() -> None:
    """The round trip doc 08 §6 implies: a projected conversation reads back."""
    from mycelium_chats.readers.transcript import TranscriptReader

    text = (
        "# Round trip\n\n"
        "## 1 · user\n\n> [!user] 2026-09-01T12:00:00Z\n> A question.\n\n"
        "## 2 · assistant\n\n> [!assistant] gpt-5 · 2026-09-01T12:00:30Z\n> An answer.\n"
    )
    result = TranscriptReader().read(text, CONTEXT)
    messages = [line for line in result.conversations[0].lines if isinstance(line, Message)]

    assert [line.role for line in messages] == ["user", "assistant"]
    assert [line.content for line in messages] == ["A question.", "An answer."]
    assert messages[1].model == "gpt-5"


def test_one_marker_convention_wins_for_a_whole_document() -> None:
    """A stray `Note:` line must not open a turn in a callout transcript."""
    from mycelium_chats.readers.transcript import markers_in

    text = (
        "> [!user]\n> Ask\n\n"
        "User: this looks like a marker but is prose\n\n"
        "> [!assistant]\n> Answer"
    )
    assert [role for _, role, _, _ in markers_in(text)] == ["user", "assistant"]


# ---------------------------------------------------------------------------
# Pasted text
# ---------------------------------------------------------------------------


def test_a_labelled_paste_is_segmented_and_marked_inferred(fixtures: Path) -> None:
    _, result = read("pasted-labelled.txt", fixtures)
    conversation = result.conversations[0]
    messages = [line for line in conversation.lines if isinstance(line, Message)]

    assert [line.role for line in messages] == ["user", "assistant", "user", "assistant"]
    assert "writer lock" in messages[1].content
    # A label is prose that looks like structure, so the reading is inferred.
    assert conversation.structure_inferred
    assert conversation.recognised == 0


def test_an_unlabelled_paste_invents_no_speakers(fixtures: Path) -> None:
    """The refusal the reader exists to make: no labels means no attribution."""
    _, result = read("pasted-unlabelled.txt", fixtures)
    conversation = result.conversations[0]

    assert len(conversation.lines) == 1
    assert isinstance(conversation.lines[0], Fragment)
    assert conversation.lines[0].meta["reason"] == "unsegmented_paste"
    assert conversation.structure_inferred
    assert conversation.recognised == 0
    assert any("no turn labels found" in note for note in result.warnings)


def test_a_single_label_is_not_a_conversation() -> None:
    """One label is as likely to be prose as a turn boundary."""
    from mycelium_chats.readers.pasted import PastedTextReader

    result = PastedTextReader().read("Claude: a note on naming\n\nSome prose.\n", CONTEXT)
    assert len(result.conversations[0].lines) == 1
    assert isinstance(result.conversations[0].lines[0], Fragment)


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


def test_the_generic_reader_follows_the_configured_paths(fixtures: Path) -> None:
    mapping = {
        "conversations": "threads",
        "messages": "history",
        "role": "speaker",
        "content": "body",
        "timestamp": "at",
        "title": "subject",
    }
    _, result = read("generic-export.json", fixtures, mapping=mapping)
    conversation = result.conversations[0]
    messages = [line for line in conversation.lines if isinstance(line, Message)]

    assert conversation.title == "Retention windows"
    assert [line.role for line in messages] == ["user", "assistant"]
    assert messages[1].content.startswith("No. It leaves the index")
    assert messages[0].ts is not None
    assert messages[0].meta["provider_role"] == "me"
    assert conversation.meta["thread_id"] == "t-77"


def test_the_generic_reader_names_the_paths_it_needs(fixtures: Path) -> None:
    text = (fixtures / "generic-export.json").read_text(encoding="utf-8")
    from mycelium_chats.readers.generic import GenericJsonReader

    with pytest.raises(ReaderError, match=r"needs \['messages', 'role', 'content'\]"):
        GenericJsonReader().read(text, ImportContext(project="p", mapping={"title": "subject"}))


def test_the_generic_reader_refuses_a_mapping_key_it_does_not_know(fixtures: Path) -> None:
    text = (fixtures / "generic-export.json").read_text(encoding="utf-8")
    from mycelium_chats.readers.generic import GenericJsonReader

    mapping = {"messages": "history", "role": "speaker", "content": "body", "auhtor": "x"}
    with pytest.raises(ReaderError, match="unknown key"):
        GenericJsonReader().read(text, ImportContext(project="p", mapping=mapping))


def test_a_mapping_that_matches_nothing_says_so_with_the_paths(fixtures: Path) -> None:
    from mycelium_chats.readers.generic import GenericJsonReader

    mapping = {"messages": "nowhere", "role": "speaker", "content": "body"}
    with pytest.raises(ReaderError, match="matched no conversations"):
        GenericJsonReader().read('{"threads": []}', ImportContext(project="p", mapping=mapping))
