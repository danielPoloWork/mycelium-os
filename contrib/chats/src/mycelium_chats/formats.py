# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Export and resume: getting a conversation back out (doc 08 §§1, 9).

Two of the module's three jobs live here. **Port** is `chats export`: emit the
conversation in a shape another tool consumes. **Resume** is `chats resume`: emit
a *continuation package* — the conversation, or a budgeted tail of it, ready to
paste into any chatbot so the thread carries on where it stopped.

Four formats, which doc 08's deferred list fixes as the whole set for v1
("multi-format export adapters beyond the four listed" is a non-goal):

``jsonl``      the canonical record, verbatim — the archive's own bytes
``markdown``   the projection's shape, for reading and pasting
``openai``     ``{"messages": [{"role", "content"}]}`` — the OpenAI chat shape
``anthropic``  ``{"system", "messages": […]}`` — Anthropic's, where the system
               prompt is a top-level field rather than a message

The two API shapes are where a lossless archive meets a lossy destination, and
the losses are stated rather than silent. Neither accepts a ``fragment``, and
neither has a place for a timestamp or a tool-call blob; both collapse `tool`
turns, which they model differently and neither models the way an archive does.
So an export to an API shape reports what it dropped, and the record it came
from is untouched — which is the whole reason the canonical form is not the API
form (doc 08 §3).

**Truncation is oldest-first**, per doc 08 §9. A conversation's recent turns are
the ones a continuation needs; its opening turns are the ones a model can most
afford to lose. The budget counts tokens with the same estimator the compiler
uses, so a `--budget-tokens` here means what `budget_tokens` means everywhere
else in the system.
"""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Final

from mycelium.chunking import ChunkingPolicy
from mycelium_chats.projection import message_heading
from mycelium_chats.record import Fragment, Message, Transcript, encode_transcript

__all__ = [
    "FORMATS",
    "Rendered",
    "render",
    "tail",
]

FORMATS: Final = ("jsonl", "markdown", "openai", "anthropic")
"""The four doc 08 §9 names. Adding a fifth is a module release, not a core one —
which is the point of a module owning its own CLI surface."""

_ESTIMATE: Final = ChunkingPolicy().count_tokens
"""The compiler's own token estimate (ADR-0007's Strategy, its default).

Borrowed so `--budget-tokens 4000` means the same number of tokens here as it
does in `mycelium_search`'s pack stage. It is an estimate in both places, and
being *the same* estimate matters more than being exact.
"""


@dataclass(frozen=True, slots=True)
class Rendered:
    """One rendered conversation, and what the rendering could not carry."""

    text: str
    format: str
    messages: int
    dropped: tuple[str, ...] = ()
    """Human-readable notes: what this format has no place for."""


def tail(
    transcript: Transcript, *, turns: int | None = None, budget_tokens: int | None = None
) -> tuple[Message | Fragment, ...]:
    """The last `turns` lines, or as many as fit in `budget_tokens`.

    Oldest-first truncation (doc 08 §9): lines are taken from the end backwards
    until a limit is met, so what survives is the end of the conversation. With
    neither limit the whole transcript is returned, which is what `resume` on a
    short conversation should do.

    A single line larger than the whole budget is **kept**, because a resume
    package with nothing in it is not a smaller answer, it is a useless one — and
    the caller is told the budget was exceeded rather than handed silence.
    """
    lines = list(transcript.lines)
    if turns is not None:
        lines = lines[-turns:] if turns > 0 else []
    if budget_tokens is None:
        return tuple(lines)

    kept: list[Message | Fragment] = []
    spent = 0
    for line in reversed(lines):
        cost = _ESTIMATE(line.content)
        if kept and spent + cost > budget_tokens:
            break
        kept.append(line)
        spent += cost
    return tuple(reversed(kept))


def render(
    transcript: Transcript,
    fmt: str,
    *,
    lines: Sequence[Message | Fragment] | None = None,
) -> Rendered:
    """Render `transcript` (or just `lines` of it) in `fmt`."""
    if fmt not in FORMATS:
        known = ", ".join(FORMATS)
        msg = f"unknown format {fmt!r}; this module writes: {known}"
        raise ValueError(msg)
    selected = tuple(lines) if lines is not None else transcript.lines
    if fmt == "jsonl":
        return _jsonl(transcript, selected)
    if fmt == "markdown":
        return _markdown(transcript, selected)
    if fmt == "openai":
        return _openai(transcript, selected)
    return _anthropic(transcript, selected)


def _jsonl(transcript: Transcript, lines: Sequence[Message | Fragment]) -> Rendered:
    """The canonical record. Lossless by definition — it *is* the archive."""
    if len(lines) == len(transcript.lines):
        text = encode_transcript(transcript)
    else:
        # A truncated record is still a record: the header is unchanged and the
        # lines are a suffix, so `seq` has a gap. Deliberate — renumbering would
        # produce a file claiming to be a whole conversation that is not one.
        parts = [transcript.conversation.model_dump_json(exclude_none=False)]
        parts.extend(line.model_dump_json(exclude_none=False) for line in lines)
        text = "\n".join(parts) + "\n"
    return Rendered(text=text, format="jsonl", messages=_count(lines))


def _markdown(transcript: Transcript, lines: Sequence[Message | Fragment]) -> Rendered:
    """The projection's shape, for a human to read or paste.

    Rebuilt here rather than read from the projected file: an export must work
    for a conversation retention excluded from the vault, and must not depend on
    a build having run.
    """
    blocks: list[str] = [f"# {transcript.conversation.title}"]
    for line in lines:
        blocks.append(f"## {message_heading(line)}")
        blocks.append(line.content)
    return Rendered(text="\n\n".join(blocks) + "\n", format="markdown", messages=_count(lines))


def _openai(transcript: Transcript, lines: Sequence[Message | Fragment]) -> Rendered:
    """``{"messages": [{"role": …, "content": …}]}`` — the shape every API took up."""
    messages = [
        {"role": line.role, "content": line.content}
        for line in lines
        if isinstance(line, Message) and line.role != "tool"
    ]
    payload = {"messages": messages}
    return Rendered(
        text=json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        format="openai",
        messages=len(messages),
        dropped=tuple(_losses(lines, keeps_system=True)),
    )


def _anthropic(transcript: Transcript, lines: Sequence[Message | Fragment]) -> Rendered:
    """``{"system": …, "messages": […]}`` — a system prompt is not a message here.

    And the messages must alternate: consecutive turns of one role are joined
    with a blank line rather than sent as two, because the API refuses the
    second. Joining is a *rendering* decision and the record keeps both turns.
    """
    system = "\n\n".join(
        line.content for line in lines if isinstance(line, Message) and line.role == "system"
    )
    turns: list[dict[str, str]] = []
    for line in lines:
        if not isinstance(line, Message) or line.role in {"system", "tool"}:
            continue
        if turns and turns[-1]["role"] == line.role:
            turns[-1]["content"] = f"{turns[-1]['content']}\n\n{line.content}"
            continue
        turns.append({"role": line.role, "content": line.content})
    payload: dict[str, object] = {"messages": turns}
    if system:
        payload = {"system": system, "messages": turns}
    notes = list(_losses(lines, keeps_system=False))
    merged = _merged(lines)
    if merged:
        notes.append(
            f"{merged} consecutive same-role turn(s) merged: this API requires alternation"
        )
    return Rendered(
        text=json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        format="anthropic",
        messages=len(turns),
        dropped=tuple(notes),
    )


def _merged(lines: Sequence[Message | Fragment]) -> int:
    """How many turns this rendering had to join into their predecessor.

    Counted rather than inferred from the output, so the note names a number the
    reader can check against the record.
    """
    count = 0
    previous: Message | None = None
    for line in lines:
        if not isinstance(line, Message) or line.role in {"system", "tool"}:
            continue
        if previous is not None and previous.role == line.role:
            count += 1
        previous = line
    return count


def _losses(lines: Sequence[Message | Fragment], *, keeps_system: bool) -> Iterator[str]:
    """What an API shape has no place for, counted."""
    fragments = sum(1 for line in lines if isinstance(line, Fragment))
    if fragments:
        yield (
            f"{fragments} fragment(s) omitted: an API message list has no shape "
            "for unsegmented text"
        )
    tools = sum(1 for line in lines if isinstance(line, Message) and line.role == "tool")
    if tools:
        yield f"{tools} tool turn(s) omitted: this format models tool use differently"
    if not keeps_system:
        return
    stamped = sum(1 for line in lines if isinstance(line, Message) and line.ts is not None)
    if stamped:
        yield f"timestamps on {stamped} message(s) omitted: the format carries none"


def _count(lines: Sequence[Message | Fragment]) -> int:
    return sum(1 for line in lines if isinstance(line, Message))
