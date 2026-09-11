# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Markdown projection: the view the compiler indexes (doc 08 §7).

A record is tier 1; this is its tier-2 projection, regenerable and never
hand-edited — the evidence lane's own doctrine (D-020), applied to a
conversation instead of a PDF. It lands under ``knowledge/evidence/chats/`` so
the folder that *is* its verification status says `evidence` (D-021), and from
there the ordinary compiler picks it up like any other Markdown file. No core
change was needed for a conversation to become citable knowledge, which is the
half of doc 08 §10's sixth gate that went well.

**The projection is a pure function of the record.** Nothing here reads
`[chunking]`, and that is deliberate rather than incidental: gate 2 asks for
"same record → byte-identical Markdown", and a projection that varied with the
chunker's token budget would make that promise relative to a configuration —
worse, it would rewrite committed tier-2 files when somebody tuned the chunker.
So the shape below is fixed, and the chunker meets it as it finds it.

**A heading per message, and the message's content inside a callout.** Two
decisions, each load-bearing, and the first one is a finding.

Doc 08 §7 wants the *chunking unit* to be the message, and since roadmap 5.13
the core delivers exactly that on its own: a callout **bounds** a chunk, so
consecutive callouts are consecutive chunks and none of them merges with the
prose beside it (ADR-0085). When this projection was written the chunker
implemented that for tables and code blocks only, so the workaround below was
load-bearing; it no longer is.

**The heading stays, for the reason it also had.** An anchor has to be stable
across a re-read, and a section slug is the only thing that gives a message one:
without its own heading a conversation's messages would share one slug and be
told apart by ordinal, so inserting or re-reading a message would move every
anchor after it. One message, one section, one chunk, and the anchor is a
message anchor: ``#12-assistant/0``.

The content is wrapped in a callout because message text is **verbatim and
arbitrary** — people paste Markdown into chats — and Obsidian renders it as doc
08 §7 asks.

**Quoting alone is not enough, and a test found that rather than a reader.**
CommonMark allows block structure *inside* a blockquote: `> ## X` is a heading,
and `> ---` under a line of text makes that line a setext heading — which took
the callout itself with it. Either one opens a section the projection did not
author, so the chunking unit stops being the message and an anchor is derived
from what somebody pasted. So :func:`_neutralise` escapes the two line shapes
that open block structure, with a backslash.

That is the evidence lane's own rule, not a new one. Its projector "emits
*text*, never assertions" — a source saying ``see [[secrets]]`` projects the
words and not the link (threat model B11). A heading is an assertion about the
document's structure, and an ingested conversation does not get to make one.

The escape costs nothing a reader or the index can see: CommonMark reads ``\\##``
as a literal ``##``, so the rendered view and the *indexed text* both carry the
original characters, and only the block-level meaning is gone. The record keeps
the true bytes regardless — it always does.

**What this used to cost, and no longer does:** a message larger than the
chunker's ceiling stayed one chunk instead of splitting at paragraph boundaries
as §7's last clause asks, because a callout was one block and a block is never
split (ADR-0007). Roadmap 5.13 closed it — a callout's blocks pack among
themselves, so an oversize message splits exactly where its author put a
paragraph break (ADR-0085). Measured on the fixture corpus at roadmap 5.5, the
largest projected message was well inside the 800-token ceiling anyway; what
changed is that the ceiling now behaves as §7 says when a message exceeds it.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Final

from mycelium.ingest import redact_text, scan_text
from mycelium.sdk.types import ProvenanceOrigin
from mycelium_chats.paths import ARCHIVE_DIRNAME
from mycelium_chats.record import Conversation, Fragment, Message, Transcript

__all__ = [
    "ChatProjection",
    "collection_of",
    "message_heading",
    "neutralise",
    "project_transcript",
]

_QUOTE: Final = "> "
_ROLE_CALLOUTS: Final[Mapping[str, str]] = {
    "user": "user",
    "assistant": "assistant",
    "system": "system",
    "tool": "tool",
}
"""Callout type per role. Obsidian renders an unknown type as a generic note, so
these need no registration — and naming them after the roles keeps the
projection re-readable by this module's own transcript reader."""

_NEEDS_QUOTES: Final = ":#[]{}&*!|>'\"%@`,"

_ATX: Final = re.compile(r"^#{1,6}(\s|$)")
"""``## X`` — an ATX heading, even inside a blockquote."""

_SETEXT: Final = re.compile(r"^(=+|-+)\s*$")
"""``---`` or ``===`` alone on a line: under text it makes a setext heading, and
that heading swallows the callout it was written inside."""


@dataclass(frozen=True, slots=True)
class ChatProjection:
    """One projected conversation, before it is written."""

    path: PurePosixPath
    text: str
    title: str


def collection_of(conversation: Conversation) -> str:
    """``chats/<project>`` — doc 08 §7's `collection`, and the retrieval filter.

    The one machine-read field that carries the project, which is why doc 08 §7's
    other conversation-level keys need not be contract fields: `collection:` is
    what `mycelium search --collection chats/acme` filters on, and it is a field
    spec 03 §3 already defines.
    """
    return f"{ARCHIVE_DIRNAME}/{conversation.project}"


def message_heading(line: Message | Fragment) -> str:
    """The heading text that opens one line's section — and its anchor slug.

    ``12 · assistant`` slugs to ``12-assistant``: the sequence number first
    because it is what makes the anchor stable and ordered, the role second
    because it is what a human reading a citation wants to know. Deliberately
    free of the message's own words — a heading built from content would move
    every anchor whenever a transcript was re-read, and heading text is indexed
    at weight 3.0, so putting a turn's prose there would double-count it.
    """
    role = line.role if isinstance(line, Message) else "fragment"
    return f"{line.seq} · {role}"


def project_transcript(
    transcript: Transcript,
    record_path: PurePosixPath,
    *,
    projection: PurePosixPath,
    findings: bool = False,
) -> ChatProjection:
    """Render `transcript` as its evidence document.

    Both paths are supplied by the archive rather than recomputed here, because
    the archive is the one place that knows the configured timezone the record's
    path was dated in — recomputing would be a second opinion about where a file
    already is.

    `findings` says the archive's scan matched a secret pattern, in which case
    every line is redacted here — the projection is the copy that reaches Git and
    the index, and doc 08 §6 redacts there unconditionally whatever
    `[chats] redact_in_record` decided about the record itself.
    """
    conversation = transcript.conversation
    source = str(record_path)
    frontmatter = _frontmatter(
        {
            "title": conversation.title,
            "origin": ProvenanceOrigin.INGESTED.value,
            "source": source,
            "source_digest": conversation.source_digest,
            "collection": collection_of(conversation),
            "tags": list(conversation.tags),
            # Below the contract line: spec 03 §3 closes the machine-read field
            # set, so these land in `properties` — preserved verbatim, never
            # machine-interpreted, and visible as Obsidian properties, which is
            # what doc 08 §7 wants them for (ADR-0077 records the divergence).
            "conv_id": conversation.conv_id,
            "provider": conversation.provider,
            "project": conversation.project,
            "started_at": _stamp(conversation.started_at),
            "structure_inferred": conversation.structure_inferred or None,
        }
    )
    body = "\n\n".join(_blocks(transcript, redact=findings))
    return ChatProjection(
        path=projection,
        text=f"{frontmatter}\n{body}\n",
        title=conversation.title,
    )


def _blocks(transcript: Transcript, *, redact: bool) -> Iterator[str]:
    """Title, metadata line, then a heading and a callout per line."""
    conversation = transcript.conversation
    yield f"# {conversation.title}"
    yield _metadata(transcript)
    for line in transcript.lines:
        yield f"## {message_heading(line)}"
        yield _callout(line, redact=redact)


def _metadata(transcript: Transcript) -> str:
    """One line of provenance a human reads before the conversation itself.

    Prose rather than a table, because it is one sentence's worth of facts and a
    table of two columns and five rows reads worse. It is indexed like any prose,
    which is wanted: "chatgpt" and the project name are how somebody searches for
    a conversation they half-remember.
    """
    conversation = transcript.conversation
    parts = [f"Archived conversation from **{conversation.provider}**"]
    parts.append(f"project `{conversation.project}`")
    parts.append(f"{len(transcript.messages)} message(s)")
    if transcript.fragments:
        parts.append(f"{len(transcript.fragments)} fragment(s)")
    if conversation.started_at is not None:
        parts.append(f"started {_stamp(conversation.started_at)}")
    models = sorted({line.model for line in transcript.messages if line.model})
    if models:
        parts.append("model " + ", ".join(f"`{model}`" for model in models))
    sentence = " · ".join(parts) + "."
    if conversation.structure_inferred:
        sentence += (
            " Turn boundaries in this transcript were **inferred**: the source carried no"
            " machine-readable structure, so the roles below are a reading of it and the"
            " content is verbatim."
        )
    if conversation.secrets:
        matched = ", ".join(f"`{flag}`" for flag in conversation.secrets)
        sentence += (
            " Secret-like text was found on import and is **redacted here**;"
            f" the rules that matched were {matched}."
        )
    return sentence


def _callout(line: Message | Fragment, *, redact: bool) -> str:
    """One line as an Obsidian callout, its content quoted verbatim.

    Every line of the content is prefixed, including blank ones, so the callout
    is one block: a bare blank line would end the blockquote and split the
    message into two units, which is exactly the chunking unit this projection
    exists to keep whole.
    """
    content = line.content
    if redact:
        content = redact_text(content, scan_text(content))

    if isinstance(line, Message):
        kind = _ROLE_CALLOUTS.get(line.role, "note")
        titles = [part for part in (line.model, _stamp(line.ts)) if part]
        head = f"[!{kind}]" + (f" {' · '.join(titles)}" if titles else "")
    else:
        head = "[!fragment] preserved, unsegmented"

    lines = [head, *(neutralise(line) for line in content.split("\n"))] if content else [head]
    return "\n".join(f"{_QUOTE}{item}".rstrip() for item in lines)


def neutralise(line: str) -> str:
    """Escape a line that would open block structure inside the callout.

    Two shapes, both escaped with a backslash so the characters survive and the
    meaning does not: an ATX heading, and a setext underline. Everything else —
    lists, fences, tables, nested quotes, thematic breaks — stays exactly as it
    was written, because none of them opens a *section* and the chunker packs
    them inside the turn they belong to (tested).
    """
    if _ATX.match(line) or _SETEXT.match(line):
        return "\\" + line
    return line


def _stamp(value: datetime | None) -> str | None:
    """RFC 3339 with a `Z`, matching how every other record here renders one."""
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _frontmatter(fields: Mapping[str, object]) -> str:
    """Render the frontmatter block, hand-written for the reason `project()` gives.

    Absent values are omitted rather than emitted as `null`: a key with no value
    is noise in a file a human opens in Obsidian, and `None` is already the
    parsed shape of an absent key.
    """
    lines = ["---"]
    for key, value in fields.items():
        if value is None or value == [] or value == "":
            continue
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(_scalar(str(item)) for item in value)}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _scalar(value: str) -> str:
    """Quote a YAML scalar that could be read as anything but a string."""
    if not value or value.strip() != value or any(char in value for char in _NEEDS_QUOTES):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value
