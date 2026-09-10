# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Export and resume: the four formats, and what each cannot carry.

The claims under test:

**`jsonl` is lossless** — it is the archive's own bytes, and a round trip
through it is the identity.

**The API shapes are lossy, and say so.** A fragment, a timestamp and a tool
turn have no home in a message list, so an export names what it dropped rather
than letting a caller discover it.

**Truncation is oldest-first**, and a single line larger than the whole budget
is kept rather than leaving a resume package empty.
"""

import json
from datetime import UTC, datetime

import pytest

from mycelium_chats.formats import FORMATS, render, tail
from mycelium_chats.record import Conversation, Fragment, Message, Transcript, decode_transcript

CONV = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
STAMP = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def build(*lines: Message | Fragment) -> Transcript:
    return Transcript(
        conversation=Conversation(
            conv_id=CONV,
            title="Retry design",
            project="research",
            provider="chatgpt",
            imported_at=STAMP,
            source_digest="sha256:" + "cd" * 32,
        ),
        lines=lines,
    )


def message(seq: int, role: str, content: str, **kwargs: object) -> Message:
    return Message(conv_id=CONV, seq=seq, role=role, content=content, **kwargs)  # type: ignore[arg-type]


CONVERSATION = build(
    message(1, "system", "Be concise."),
    message(2, "user", "How many retries?", ts=STAMP),
    message(3, "assistant", "Five, then quarantine.", model="gpt-5", ts=STAMP),
    message(4, "tool", '{"attempts": 5}'),
    Fragment(conv_id=CONV, seq=5, content="An abandoned draft."),
)


# ---------------------------------------------------------------------------
# The set of formats
# ---------------------------------------------------------------------------


def test_the_four_formats_the_spec_names() -> None:
    assert FORMATS == ("jsonl", "markdown", "openai", "anthropic")


def test_an_unknown_format_lists_the_known_ones() -> None:
    with pytest.raises(ValueError, match="jsonl, markdown, openai, anthropic"):
        render(CONVERSATION, "yaml")


# ---------------------------------------------------------------------------
# jsonl — the canonical record
# ---------------------------------------------------------------------------


def test_jsonl_is_the_archive_and_round_trips() -> None:
    rendered = render(CONVERSATION, "jsonl")
    assert decode_transcript(rendered.text) == CONVERSATION
    assert rendered.dropped == ()
    assert rendered.messages == 4


def test_a_truncated_jsonl_keeps_its_sequence_gap() -> None:
    """Renumbering would produce a file claiming to be a whole conversation."""
    rendered = render(CONVERSATION, "jsonl", lines=tail(CONVERSATION, turns=2))
    lines = [json.loads(line) for line in rendered.text.splitlines()]

    assert lines[0]["kind"] == "conversation"
    assert [item["seq"] for item in lines[1:]] == [4, 5]


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------


def test_markdown_carries_every_line_under_its_own_heading() -> None:
    rendered = render(CONVERSATION, "markdown")

    assert rendered.text.startswith("# Retry design\n")
    for heading in ("## 1 · system", "## 3 · assistant", "## 5 · fragment"):
        assert heading in rendered.text
    assert "Five, then quarantine." in rendered.text


# ---------------------------------------------------------------------------
# openai
# ---------------------------------------------------------------------------


def test_openai_emits_a_message_list_and_names_what_it_dropped() -> None:
    rendered = render(CONVERSATION, "openai")
    payload = json.loads(rendered.text)

    assert [item["role"] for item in payload["messages"]] == ["system", "user", "assistant"]
    assert payload["messages"][2]["content"] == "Five, then quarantine."
    assert any("fragment(s) omitted" in note for note in rendered.dropped)
    assert any("tool turn(s) omitted" in note for note in rendered.dropped)
    assert any("timestamps on 2 message(s) omitted" in note for note in rendered.dropped)


# ---------------------------------------------------------------------------
# anthropic
# ---------------------------------------------------------------------------


def test_anthropic_lifts_the_system_prompt_out_of_the_messages() -> None:
    rendered = render(CONVERSATION, "anthropic")
    payload = json.loads(rendered.text)

    assert payload["system"] == "Be concise."
    assert [item["role"] for item in payload["messages"]] == ["user", "assistant"]


def test_anthropic_merges_consecutive_same_role_turns_and_says_so() -> None:
    """The API requires alternation; joining is a rendering decision and the
    record keeps both turns."""
    doubled = build(
        message(1, "user", "First question."),
        message(2, "user", "And a second."),
        message(3, "assistant", "Both answered."),
    )
    rendered = render(doubled, "anthropic")
    payload = json.loads(rendered.text)

    assert [item["role"] for item in payload["messages"]] == ["user", "assistant"]
    assert payload["messages"][0]["content"] == "First question.\n\nAnd a second."
    assert any("merged" in note for note in rendered.dropped)
    assert len(doubled.messages) == 3, "the record is untouched"


def test_anthropic_omits_a_system_key_it_has_nothing_for() -> None:
    plain = build(message(1, "user", "Ask"), message(2, "assistant", "Answer"))
    payload = json.loads(render(plain, "anthropic").text)

    assert "system" not in payload


# ---------------------------------------------------------------------------
# tail — oldest-first truncation
# ---------------------------------------------------------------------------


def test_tail_keeps_the_end_of_the_conversation() -> None:
    assert [line.seq for line in tail(CONVERSATION, turns=2)] == [4, 5]
    assert [line.seq for line in tail(CONVERSATION, turns=99)] == [1, 2, 3, 4, 5]
    assert tail(CONVERSATION, turns=0) == ()


def test_tail_with_no_limit_is_the_whole_conversation() -> None:
    assert tail(CONVERSATION) == CONVERSATION.lines


def test_a_token_budget_takes_as_many_recent_turns_as_fit() -> None:
    long = build(
        message(1, "user", "word " * 200),
        message(2, "assistant", "word " * 200),
        message(3, "user", "short"),
    )
    selected = tail(long, budget_tokens=80)

    assert [line.seq for line in selected] == [3]


def test_a_line_larger_than_the_whole_budget_is_still_kept() -> None:
    """A resume package with nothing in it is not a smaller answer."""
    huge = build(message(1, "user", "word " * 5000))
    assert len(tail(huge, budget_tokens=10)) == 1
