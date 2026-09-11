# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The reader protocol, the registry, and what a reader is handed and returns."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Protocol, runtime_checkable

from pydantic import JsonValue

from mycelium_chats.record import Fragment, Message, Role

__all__ = [
    "READERS",
    "ImportContext",
    "ReadResult",
    "Reader",
    "ReaderError",
    "ReadConversation",
    "normalise_role",
    "placeholder_lines",
    "reader_for",
    "reader_ids",
]


class ReaderError(ValueError):
    """The input is not the shape this reader reads, or is unusable.

    A per-*input* failure, and the import reports it rather than dying on it
    when several files were named: the ingestion doctrine's quarantine-not-abort
    rule (spec 02 §5), applied to an authoring command.
    """


@dataclass(frozen=True, slots=True)
class ImportContext:
    """Everything a reader may need that is not the input itself."""

    project: str
    """Where the conversation is filed. Required by doc 08 §5."""
    title: str | None = None
    """An operator-supplied title, which overrides whatever the export says."""
    source_uri: str = ""
    """Where the bytes came from — a path, or ``-`` for standard input."""
    mapping: Mapping[str, str] = field(default_factory=dict)
    """`[chats] mapping`, for the `generic` reader. Empty for every other."""


@dataclass(frozen=True, slots=True)
class ReadConversation:
    """One conversation a reader recovered from the input.

    Deliberately *not* a :class:`~mycelium_chats.record.Transcript`: a reader
    reports what it found, and identity, custody, sequencing, secret scanning and
    the header belong to :mod:`mycelium_chats.archive`. One export file holds many
    conversations, and none of them has an id until the archive mints one.
    """

    title: str
    lines: tuple[Message | Fragment, ...]
    """In conversation order. ``seq`` and ``conv_id`` are placeholders the archive
    replaces — a reader cannot know either."""
    provider_conv_id: str | None = None
    started_at: datetime | None = None
    structure_inferred: bool = False
    """True when turn boundaries or roles were guessed rather than read."""
    recognised: int = 0
    """Source turns read from explicit structure — the fidelity report's numerator."""
    tags: tuple[str, ...] = ()
    meta: dict[str, JsonValue] = field(default_factory=dict)
    """Conversation-level export fields this schema has no home for, preserved."""
    unsegmented: bool = False
    """True when the reader could not find turns at all and kept the input whole.

    Narrower than ``structure_inferred``, which every paste sets: this says the
    reader *gave up* rather than guessed, so the conversation is one fragment and
    the optional segmenter (doc 08 §6) is the thing that could improve it. A typed
    field rather than a `meta` string, because it is a question the archive asks
    on every import and an answer read out of prose is an answer nobody pinned
    (roadmap 5.16)."""
    segmenter: str | None = None
    """``llm/<model>`` when the optional segmenter proposed these boundaries.

    No *reader* sets it, and that is the point: a reader reports what the source
    stated, and this records that something else read structure into text that
    stated none. It travels to :attr:`mycelium_chats.record.Conversation.segmenter`,
    which doc 08 §6 requires so a human can tell inferred structure a model
    proposed from inferred structure a heuristic did."""


@dataclass(frozen=True, slots=True)
class ReadResult:
    """What one input yielded: conversations, and what the reader wants said."""

    conversations: tuple[ReadConversation, ...]
    warnings: tuple[str, ...] = ()


@runtime_checkable
class Reader(Protocol):
    """One input shape, read into conversations."""

    id: str
    """The `--provider` value that pins this reader, and the header's `provider`."""

    description: str

    def sniff(self, text: str, *, source_uri: str) -> bool:
        """Whether this reader recognises `text` — cheap, and never destructive."""
        ...

    def read(self, text: str, context: ImportContext) -> ReadResult:
        """Read `text`, or raise :class:`ReaderError`."""
        ...


def _readers() -> tuple[Reader, ...]:
    """The registry, built on demand so the import graph stays a tree."""
    from mycelium_chats.readers import chatgpt, claude, generic, pasted, transcript

    found: tuple[Reader, ...] = (
        chatgpt.ChatGptReader(),
        claude.ClaudeReader(),
        generic.GenericJsonReader(),
        transcript.TranscriptReader(),
        pasted.PastedTextReader(),
    )
    return found


READERS: Final = "chatgpt, claude, generic, transcript, pasted"
"""The reader ids, for a message that has to list them. Kept as a string so the
registry is not built to render an error about the registry."""


def reader_ids() -> tuple[str, ...]:
    return tuple(reader.id for reader in _readers())


def reader_for(
    text: str, *, provider: str | None, source_uri: str, mapping: Mapping[str, str] | None = None
) -> Reader:
    """The reader for this input: the pinned one, else the first that recognises it.

    `provider` is pinned resolution and wins outright — an operator who names a
    reader gets it, and its own `read` says why the input does not fit, which is
    more useful than a sniff quietly choosing something else (spec 05 §4.2's rule,
    borrowed).

    Without `--provider`, readers are tried in registry order, most specific
    first. `generic` only participates when `[chats] mapping` is configured,
    because an unconfigured field mapping recognises nothing; `pasted` is last
    because any text is some text, and a reader that always matches must never be
    reached before the ones that can be wrong.
    """
    available = _readers()
    if provider is not None:
        for reader in available:
            if reader.id == provider:
                return reader
        known = ", ".join(reader.id for reader in available)
        msg = f"unknown --provider {provider!r}; this module reads: {known}"
        raise ReaderError(msg)

    for reader in available:
        if reader.id == "generic" and not mapping:
            continue
        if reader.sniff(text, source_uri=source_uri):
            return reader
    known = ", ".join(reader.id for reader in available)
    msg = (
        f"no reader recognises {source_uri or 'this input'}; readers: {known}. "
        "Name one with --provider, or configure [chats] mapping for a JSON export "
        "no built-in reader knows."
    )
    raise ReaderError(msg)


def normalise_role(value: object, *, default: Role = "user") -> Role:
    """Map a provider's word for a role onto the four this schema has.

    Every export spells them differently — `human`, `Human`, `bot`, `model`,
    `gpt`, `ai` — and translating at the edge is what lets a consumer of the
    record ignore where it came from. An unrecognised word falls back to
    `default` and the *caller* records the original in `meta`, so the mapping
    never loses what it could not place.
    """
    text = str(value or "").strip().casefold()
    if text in {"user", "human", "you", "me", "prompt"}:
        return "user"
    if text in {"assistant", "bot", "model", "gpt", "ai", "claude", "chatgpt", "gemini"}:
        return "assistant"
    if text == "system":
        return "system"
    if text in {"tool", "function", "tool_result", "tool_use"}:
        return "tool"
    return default


def placeholder_lines(
    entries: Sequence[tuple[Role, str, datetime | None, str | None, dict[str, JsonValue]]],
) -> tuple[Message | Fragment, ...]:
    """Build message lines with placeholder identity, in order.

    `conv_id` and `seq` are filled by the archive; a reader supplies a legal
    placeholder so the records validate as it builds them. The placeholder ULID
    is a constant rather than a fresh one: a reader that minted identity would be
    the second writer of a field the archive owns.
    """
    return tuple(
        Message(
            conv_id=_PLACEHOLDER_ID,
            seq=position,
            role=role,
            content=content,
            ts=timestamp,
            model=model,
            meta=meta,
        )
        for position, (role, content, timestamp, model, meta) in enumerate(entries, start=1)
    )


_PLACEHOLDER_ID: Final = "00000000000000000000000000"
"""A syntactically valid ULID that is obviously not one, so a placeholder that
escaped into a written record would be visible rather than plausible."""
