# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Markdown transcript reader (doc 08 §6).

*"Heading/blockquote-structured parsing; role markers from common conventions."*
A Markdown transcript is a file a human wrote or a tool emitted, and it carries
its structure in markup rather than in data — so unlike a provider export, the
boundaries here are **read** rather than known, and the difference from the
pasted-text reader is that the markup is explicit enough that reading it is not
a guess.

Three conventions are recognised, and each one is a *marker* that opens a turn:

``> [!user]`` / ``> [!assistant] model``  the Obsidian callout this module's own
projection writes, which makes the projection re-readable — a round trip
through the vault and back into a record.

``## User`` / ``### Assistant: gpt-5``  a heading whose text is a role.

``**User:**`` / ``User:`` at the start of a line, the convention a hand-written
transcript uses.

Everything up to the first marker is preamble: a title, a date line, a note. It
is kept as a ``fragment`` rather than attributed to a speaker who did not say it,
because guessing a role is exactly what invariant 2 forbids. Text after a marker
belongs to that turn, verbatim, markup and all — a transcript's code fences and
lists are part of what was said.

``structure_inferred`` is **false** here: a marker is structure the source
states. What this reader cannot know is timestamps, so ``ts`` is ``None`` unless
a marker carries one.
"""

import re
from datetime import UTC, datetime
from typing import Final

from pydantic import JsonValue

from mycelium_chats.readers.base import (
    ImportContext,
    ReadConversation,
    ReaderError,
    ReadResult,
    normalise_role,
)
from mycelium_chats.record import Fragment, Message, Role

__all__ = ["TranscriptReader", "markers_in"]

_PLACEHOLDER: Final = "00000000000000000000000000"

_ROLE_WORDS: Final = (
    "user",
    "human",
    "you",
    "me",
    "assistant",
    "bot",
    "model",
    "gpt",
    "chatgpt",
    "claude",
    "gemini",
    "ai",
    "system",
    "tool",
)
_ROLES: Final = "|".join(_ROLE_WORDS)

CALLOUT: Final = re.compile(rf"^>\s*\[!(?P<role>{_ROLES})\]\s*(?P<rest>.*)$", re.IGNORECASE)
"""`> [!assistant] gpt-5` — the shape this module's own projection writes."""

HEADING: Final = re.compile(
    rf"^#{{1,6}}\s+(?:\d+\s*[·.\-]\s*)?(?P<role>{_ROLES})\b\s*[:·\-]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
"""`## User`, `### Assistant: gpt-5`, `## 3 · assistant` — a heading naming a role."""

BOLD: Final = re.compile(
    rf"^\*{{0,2}}(?P<role>{_ROLES})\*{{0,2}}\s*:\s*(?P<rest>.*)$", re.IGNORECASE
)
"""`**User:**` or `User:` opening a line."""

_TITLE: Final = re.compile(r"^#\s+(?P<title>.+?)\s*$")

_MODEL_NOISE: Final = re.compile(r"^[\s(\[·:\-]+|[\s)\]]+$")


class TranscriptReader:
    """Reads a Markdown transcript with role markers."""

    id = "transcript"
    description = "Markdown transcript with callout, heading or `Role:` markers"

    def sniff(self, text: str, *, source_uri: str) -> bool:
        """At least two markers of one kind, so a document that merely says
        "user" in a heading is not mistaken for a transcript.

        Two rather than one: a conversation has at least two turns, and a
        one-marker match is far more likely to be prose about users than a
        transcript of one.
        """
        return len(markers_in(text)) >= 2

    def read(self, text: str, context: ImportContext) -> ReadResult:
        markers = markers_in(text)
        if not markers:
            msg = (
                "no role markers found; a transcript needs `> [!user]`, `## User` or `User:` lines"
            )
            raise ReaderError(msg)

        lines = text.splitlines()
        title = context.title or _title_of(lines) or "Untitled transcript"
        built: list[Message | Fragment] = []

        preamble = "\n".join(lines[: markers[0][0]]).strip()
        if preamble:
            built.append(
                Fragment(
                    conv_id=_PLACEHOLDER,
                    seq=1,
                    content=preamble,
                    meta={"reason": "preamble", "note": "text before the first role marker"},
                )
            )

        callouts = bool(markers) and CALLOUT.match(lines[markers[0][0]]) is not None
        for position, (index, role, model, first) in enumerate(markers):
            limit = markers[position + 1][0] if position + 1 < len(markers) else len(lines)
            end = _quote_ends(lines, index + 1, limit) if callouts else limit
            body = "\n".join([first, *lines[index + 1 : end]])
            meta: dict[str, JsonValue] = {}
            built.append(
                Message(
                    conv_id=_PLACEHOLDER,
                    seq=len(built) + 1,
                    role=role,
                    model=model,
                    ts=None,
                    content=_unquote(body).strip("\n"),
                    meta=meta,
                )
            )

        return ReadResult(
            conversations=(
                ReadConversation(
                    title=title,
                    lines=tuple(built),
                    started_at=_date_in(lines),
                    structure_inferred=False,
                    recognised=len(markers),
                ),
            )
        )


def markers_in(text: str) -> tuple[tuple[int, Role, str | None, str], ...]:
    """Every role marker: ``(line index, role, model, remainder of the line)``.

    One convention wins for the whole document — whichever matches most — because
    a transcript that mixes them is far less likely than a document that happens
    to contain one line looking like another convention. Deciding once per
    document rather than per line is what stops a stray `Note:` inside a
    code fence from opening a turn.
    """
    lines = text.splitlines()
    by_pattern: dict[str, list[tuple[int, Role, str | None, str]]] = {}
    for name, pattern in (("callout", CALLOUT), ("heading", HEADING), ("bold", BOLD)):
        found: list[tuple[int, Role, str | None, str]] = []
        for index, line in enumerate(lines):
            match = pattern.match(line)
            if match is None:
                continue
            role = normalise_role(match.group("role"))
            rest = match.group("rest") or ""
            model, remainder = (
                (_model(rest), "") if name in {"callout", "heading"} else (None, rest)
            )
            found.append((index, role, model, remainder))
        by_pattern[name] = found
    best = max(by_pattern.values(), key=len, default=[])
    return tuple(best)


def _quote_ends(lines: list[str], start: int, limit: int) -> int:
    """Where the blockquote opened before `start` stops.

    A callout *is* a blockquote, so its content is the quoted run and nothing
    after it — the first unquoted line ends the block, which is Markdown's own
    rule. Reading to the next marker instead would swallow whatever sits between
    two turns, and in this module's own projection that is the next message's
    heading (found by the round-trip test, which is what it is for).
    """
    end = start
    while end < limit and lines[end].startswith(">"):
        end += 1
    return end


def _model(rest: str) -> str | None:
    """A model name trailing a marker: `> [!assistant] gpt-5`, `## Assistant: gpt-5`.

    Split on the separator the projection uses between a model and a timestamp,
    so `gpt-5 · 2026-09-01T12:00:30Z` reads back as the model alone.
    """
    text = _MODEL_NOISE.sub("", rest).strip()
    text = text.split("\u00b7", 1)[0].strip()
    return text or None


def _unquote(text: str) -> str:
    """Strip one level of blockquote markers from a callout's body.

    A callout's content is quoted, so the message text is the body with `> `
    removed — and only one level, because a quote *inside* the message is part of
    what was said and must survive verbatim.
    """
    lines = text.splitlines()
    if not lines or not any(line.startswith(">") for line in lines if line.strip()):
        return text
    stripped: list[str] = []
    for line in lines:
        if line.startswith("> "):
            stripped.append(line[2:])
        elif line.startswith(">"):
            stripped.append(line[1:])
        else:
            stripped.append(line)
    return "\n".join(stripped)


def _title_of(lines: list[str]) -> str | None:
    for line in lines:
        match = _TITLE.match(line)
        if match is not None and not HEADING.match(line):
            return match.group("title").strip()
    return None


def _date_in(lines: list[str]) -> datetime | None:
    """A date in the first few lines, when a transcript states one.

    Read only from the preamble — a date inside a message is something the
    speaker said, not when the conversation happened.
    """
    for line in lines[:8]:
        match = re.search(r"\b(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?))?\b", line)
        if match is None:
            continue
        stamp = match.group(1) + ("T" + match.group(2) if match.group(2) else "T00:00")
        try:
            return datetime.fromisoformat(stamp).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None
