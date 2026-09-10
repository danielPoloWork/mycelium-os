# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Canonical Chat Record — ``mycelium/chat/v0`` (module spec doc 08 §4).

One conversation is one ``*.chat.jsonl`` file: line 1 is the header, every line
after it is a message or a fragment. JSONL was chosen over YAML and Markdown for
the reasons doc 08 §3 records — append-only, streamable, greppable, lossless,
and already the shape every chatbot API consumes — and the split between this
file and its Markdown projection mirrors the system's own evidence doctrine:
one canonical record, one derived view (D-020).

**The fidelity contract is four invariants, and three of them live here.**

``content`` is verbatim, always. No rewriting, no cleanup, no summarisation —
which is why nothing in this module has a "normalise" step and why
:class:`Message` stores a plain ``str`` rather than anything parsed.

*Structure* may be inferred; *content* may not. A pasted transcript has no
machine-readable turn boundaries, so a reader may guess them — and when it does,
the header says ``structure_inferred`` and every guessed message says
``meta.inferred``. A reader never guesses at content.

Unknown provider fields are preserved rather than dropped. Whatever an export
carries that this schema has no field for lands in ``meta``, verbatim. It is the
same loss-aware custody rule KIR's ``opaque`` node follows (ADR-0034): a format
this module does not fully understand must still be *accounted for*.

The fourth invariant — the original input is kept in tier-1 custody, with its
digest in the header — belongs to :mod:`mycelium_chats.archive`.

**Timestamps normalise to UTC**, per spec 03 §1's conventions, which doc 08 §4
adopts by reference. Doc 08's own example shows a ``+02:00`` offset and §5 wants
*local* dates in archive paths; both are honoured without a second timestamp
field, because the instant is exact and the path's timezone is a separate,
configured decision (``[chats] timezone``). What a reader loses is the offset the
provider happened to write, which is a rendering detail rather than a fact about
the conversation.

**A fragment is not a failure.** Residue a reader could not segment is kept as a
``fragment`` line rather than dropped, so "zero silent loss" (doc 08 §10, gate 1)
is a property of the record and not a promise about the readers.
"""

import json
from collections.abc import Iterable, Iterator, Sequence
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, PositiveInt, StringConstraints, model_validator

from mycelium.sdk.types import Record, Sha256Digest, Ulid, UtcDatetime

__all__ = [
    "Conversation",
    "Fragment",
    "Message",
    "Participant",
    "Role",
    "Transcript",
    "decode_transcript",
    "encode_transcript",
    "participants_of",
    "renumber",
]

Role = Literal["user", "assistant", "system", "tool"]
"""Who produced a message.

Four values, closed, and mapped to by every reader — a provider's own vocabulary
(`human`, `bot`, `model`, `gpt`) is translated at the edge so a consumer of this
record never has to know which export it came from. `system` and `tool` exist
because exports carry them and dropping them would breach the preservation
invariant; the projection renders them like any other turn.
"""

_NonEmpty = Annotated[str, StringConstraints(min_length=1)]


class Participant(Record):
    """One party to the conversation: a role, a label, and maybe a model."""

    schema_version: Literal["mycelium/chat-participant/v0"] = "mycelium/chat-participant/v0"
    role: Role
    label: _NonEmpty
    """What to call them — the provider's display name, or the role itself."""
    model: str | None = None
    """The assistant's model where the export names it, else ``None``. Never guessed."""


class Conversation(Record):
    """Line 1 of a record: everything true of the conversation as a whole."""

    kind: Literal["conversation"] = "conversation"
    schema_version: Literal["mycelium/chat/v0"] = "mycelium/chat/v0"
    conv_id: Ulid
    """Identity (doc 08 §5). The filename is convenience; renames break nothing."""
    title: _NonEmpty
    project: _NonEmpty
    """Required, per doc 08 §5 — `--project` or `[chats] default_project`."""
    provider: _NonEmpty
    """Which reader produced this record: `chatgpt`, `claude`, `transcript`, …"""
    provider_conv_id: str | None = None
    """The provider's own id, where the export carries one — what makes a
    re-import recognisable as the same conversation rather than a second copy."""
    started_at: UtcDatetime | None = None
    """When the conversation began, when the export says. ``None`` is a fact, not
    a default: a pasted transcript genuinely does not know."""
    imported_at: UtcDatetime
    source_digest: Sha256Digest
    """The tier-1 blob holding the original input, so the archive is re-derivable
    and auditable (doc 08 §4, invariant 5)."""
    structure_inferred: bool = False
    """Whether turn boundaries or roles were guessed rather than read."""
    participants: tuple[Participant, ...] = ()
    tags: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    """Secret-scan rule ids that matched this conversation's content (doc 08 §6).
    The finding is recorded here and redacted in the projection and the index;
    the original stays in custody, because it is the evidence."""
    segmenter: str | None = None
    """`llm/<model>` when an optional LLM proposed the segmentation, else ``None``
    — the label doc 08 §6 requires so a reader can tell inferred structure that a
    model proposed from inferred structure a heuristic did."""


class Message(Record):
    """One turn, verbatim."""

    kind: Literal["message"] = "message"
    conv_id: Ulid
    seq: PositiveInt
    """Position in the conversation, from 1. Stable: the projection's anchors are
    built from it, so a citation survives a re-projection."""
    role: Role
    model: str | None = None
    ts: UtcDatetime | None = None
    content: str
    """Verbatim. The invariant the whole module exists to keep."""
    meta: dict[str, JsonValue] = Field(default_factory=dict)
    """Whatever the export carried that this schema has no field for — tool
    calls, attachment digests, `inferred: true` — preserved rather than dropped."""


class Fragment(Record):
    """Source text no reader could segment, kept rather than dropped."""

    kind: Literal["fragment"] = "fragment"
    conv_id: Ulid
    seq: PositiveInt
    content: str
    meta: dict[str, JsonValue] = Field(default_factory=dict)


class Transcript(Record):
    """A whole record in memory: its header and its lines, in order.

    Not itself a line of the file — a convenience for everything that reads or
    writes one, and the object the fidelity report, the projection and every
    export format are pure functions of.
    """

    schema_version: Literal["mycelium/chat-transcript/v0"] = "mycelium/chat-transcript/v0"
    conversation: Conversation
    lines: tuple[Message | Fragment, ...] = ()

    @model_validator(mode="after")
    def _lines_belong_and_are_ordered(self) -> Self:
        expected = 1
        for line in self.lines:
            if line.conv_id != self.conversation.conv_id:
                msg = f"line {line.seq} belongs to {line.conv_id}, not {self.conversation.conv_id}"
                raise ValueError(msg)
            if line.seq != expected:
                msg = f"expected seq {expected}, found {line.seq}: a record is densely numbered"
                raise ValueError(msg)
            expected += 1
        return self

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(line for line in self.lines if isinstance(line, Message))

    @property
    def fragments(self) -> tuple[Fragment, ...]:
        return tuple(line for line in self.lines if isinstance(line, Fragment))

    @property
    def inferred(self) -> tuple[Message, ...]:
        """Messages whose structure was guessed — what the fidelity report counts."""
        return tuple(line for line in self.messages if line.meta.get("inferred") is True)

    def verbatim(self) -> str:
        """Every line's content, in order, joined by newlines.

        The left-hand side of gate 3's containment property (doc 08 §10): what
        the record holds must be a superset of what the source said, so this is
        the string a test compares against the source text.
        """
        return "\n".join(line.content for line in self.lines)


def encode_transcript(transcript: Transcript) -> str:
    """The record's bytes: one JSON object per line, header first, LF-terminated.

    Deterministic by construction — the field order is the model's, keys are not
    re-sorted (JSONL is read line by line, so a stable field order is what makes
    a diff readable), and every line ends with `\\n` including the last.
    """
    lines = [transcript.conversation.model_dump_json(exclude_none=False)]
    lines.extend(line.model_dump_json(exclude_none=False) for line in transcript.lines)
    return "\n".join(lines) + "\n"


def decode_transcript(text: str) -> Transcript:
    """Read a record back, validating every line.

    A record is a file a human may have edited and a tool may have truncated, so
    nothing here is trusted: the header must be a header, every following line
    must declare a kind this schema knows, and the sequence numbers must be dense
    — the same "a cache is never trusted blindly" rule the build's artifact
    envelopes follow (ADR-0015).
    """
    raw = [line for line in text.splitlines() if line.strip()]
    if not raw:
        msg = "an empty file is not a chat record: line 1 must be the conversation header"
        raise ValueError(msg)
    conversation = Conversation.model_validate_json(raw[0])
    lines: list[Message | Fragment] = []
    for number, line in enumerate(raw[1:], start=2):
        lines.append(_line(line, number))
    return Transcript(conversation=conversation, lines=tuple(lines))


def _line(text: str, number: int) -> Message | Fragment:
    try:
        parsed = json.loads(text)
    except ValueError as error:
        msg = f"line {number} is not JSON: {error}"
        raise ValueError(msg) from error
    kind = parsed.get("kind") if isinstance(parsed, dict) else None
    if kind == "message":
        return Message.model_validate(parsed)
    if kind == "fragment":
        return Fragment.model_validate(parsed)
    msg = f'line {number} declares kind {kind!r}; a record holds "message" and "fragment" lines'
    raise ValueError(msg)


def renumber(lines: Iterable[Message | Fragment]) -> Iterator[Message | Fragment]:
    """Re-sequence lines from 1, preserving order.

    Readers build their lines before they know how many survive filtering, so
    numbering is applied once at the end — which keeps `seq` dense, and dense is
    what makes a projection anchor predictable.
    """
    for position, line in enumerate(lines, start=1):
        yield line.model_copy(update={"seq": position})


def participants_of(lines: Sequence[Message | Fragment]) -> tuple[Participant, ...]:
    """Derive the participant list from the messages themselves.

    Read off the record rather than declared by a reader, so the header cannot
    disagree with its own lines. One entry per (role, model) pair actually
    present, in first-appearance order, because that is the order a reader of the
    transcript meets them.
    """
    seen: list[Participant] = []
    for line in lines:
        if not isinstance(line, Message):
            continue
        if any(item.role == line.role and item.model == line.model for item in seen):
            continue
        seen.append(Participant(role=line.role, label=line.role, model=line.model))
    return tuple(seen)
