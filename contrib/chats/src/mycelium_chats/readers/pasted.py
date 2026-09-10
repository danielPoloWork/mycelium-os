# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The pasted-text reader (doc 08 §6) — the one that is allowed to guess.

*"Deterministic heuristics for common patterns ("You said:", "ChatGPT:",
blank-line turns); ambiguous segmentation → `structure_inferred: true` +
fidelity warnings."*

This is the reader for text a human selected in a browser and copied. There is
no data and no markup — only the labels the web page happened to render — so
segmentation is genuinely a guess, and the whole design of this reader is about
saying so.

**Every paste is inferred structure**, and that is the honest reading of what a
label is. `You said:` is prose a web page rendered, not a field a machine wrote
— a human can type it inside a message, and a provider can change it next week.
So both paths below set ``structure_inferred: true`` and every message they
produce carries ``meta.inferred``; what differs is whether segmentation
*succeeded*.

A *labelled* paste has at least two turn labels, so the boundaries are read from
them and the fidelity report counts the turns as **inferred** — content verbatim,
structure a reading (invariant 2).

An *unlabelled* paste has nothing but blank lines. Then the reader refuses to
attribute roles it cannot know: the whole text becomes **one** `fragment` and the
report counts zero turns read. That is deliberately worse than alternating
`user` / `assistant` by paragraph, which is the obvious heuristic and is wrong
often enough that a record built from it would be a record nobody can cite.
Invariant 2 permits inferring structure; it does not permit inventing a speaker.

The alternative — guess, then let a human fix it — was rejected because the
record is the archive. A fabricated attribution that reaches the index is a
false statement about who said what, and the projection makes it citable.
"""

import json
import re
from typing import Final

from mycelium_chats.readers.base import (
    ImportContext,
    ReadConversation,
    ReaderError,
    ReadResult,
    normalise_role,
)
from mycelium_chats.record import Fragment, Message

__all__ = ["LABEL", "PastedTextReader"]

_PLACEHOLDER: Final = "00000000000000000000000000"

LABEL: Final = re.compile(
    r"^\s*(?P<who>You|User|Me|Human|ChatGPT|Claude|Gemini|Assistant|Copilot|Bot|AI)"
    r"(?:\s+said)?\s*:\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
"""`You said:`, `ChatGPT said:`, `Claude:` — the labels a web page renders.

`said` is optional because the providers disagree: ChatGPT's web export writes
"You said:" and "ChatGPT said:", while a copy from Claude gives bare "Claude:".
"""

_MIN_LABELS: Final = 2
"""Below this the paste is treated as unlabelled: one label is as likely to be
prose ("Claude: a note on naming") as a turn boundary."""


class PastedTextReader:
    """Reads plain text a human copied out of a chat interface."""

    id = "pasted"
    description = "Plain text pasted from a web chat; labelled turns, else one fragment"

    def sniff(self, text: str, *, source_uri: str) -> bool:
        """Any non-empty text that is **not** a JSON document.

        Near-total, and deliberately last in the registry: this reader exists so
        that no input is refused for having no recognisable shape, and it must
        never be reached before a reader that could be wrong about the input it
        does recognise (see :func:`mycelium_chats.readers.reader_for`).

        The one exclusion is JSON, and it is what makes the refusal useful. A
        provider export no built-in reader knows *is* readable — through
        `[chats] mapping` — so falling through to here would archive its
        punctuation as a conversation and call that success. Refusing lets
        `reader_for` say "configure a mapping", which is the actionable answer.
        """
        if not text.strip():
            return False
        try:
            json.loads(text)
        except ValueError:
            return True
        return False

    def read(self, text: str, context: ImportContext) -> ReadResult:
        if not text.strip():
            msg = "empty input: there is nothing to archive"
            raise ReaderError(msg)

        lines = text.splitlines()
        labels = [
            (index, match)
            for index, line in enumerate(lines)
            if (match := LABEL.match(line)) is not None
        ]

        if len(labels) < _MIN_LABELS:
            return ReadResult(
                conversations=(
                    ReadConversation(
                        title=context.title or _first_sentence(text) or "Pasted conversation",
                        lines=(
                            Fragment(
                                conv_id=_PLACEHOLDER,
                                seq=1,
                                content=text.strip("\n"),
                                meta={
                                    "reason": "unsegmented_paste",
                                    "note": (
                                        "no turn labels found; roles were not guessed, so the "
                                        "paste is kept whole"
                                    ),
                                },
                            ),
                        ),
                        structure_inferred=True,
                        recognised=0,
                    ),
                ),
                warnings=(
                    "no turn labels found in the paste: it is archived as a single fragment "
                    "with structure_inferred = true. Add `You said:` / `<Assistant> said:` "
                    "labels, or import a provider export, to get message-level anchors.",
                ),
            )

        built: list[Message | Fragment] = []
        preamble = "\n".join(lines[: labels[0][0]]).strip()
        if preamble:
            built.append(
                Fragment(
                    conv_id=_PLACEHOLDER,
                    seq=1,
                    content=preamble,
                    meta={"reason": "preamble", "note": "text before the first turn label"},
                )
            )

        for position, (index, match) in enumerate(labels):
            end = labels[position + 1][0] if position + 1 < len(labels) else len(lines)
            body = "\n".join([match.group("rest") or "", *lines[index + 1 : end]])
            who = match.group("who")
            role = normalise_role(who)
            built.append(
                Message(
                    conv_id=_PLACEHOLDER,
                    seq=len(built) + 1,
                    role=role,
                    ts=None,
                    content=body.strip("\n"),
                    meta={"label": who} if who.casefold() != role else {},
                )
            )

        return ReadResult(
            conversations=(
                ReadConversation(
                    title=context.title or _first_sentence(text) or "Pasted conversation",
                    lines=tuple(built),
                    structure_inferred=True,
                    recognised=0,
                ),
            )
        )


def _first_sentence(text: str, limit: int = 60) -> str | None:
    """A title from the paste's own first words, when the operator gave none.

    Not a summary — the first line, truncated. Anything cleverer would be the
    module writing prose about a conversation, which is the synthesis lane's job
    and subject to its governance (D-020).
    """
    for line in text.splitlines():
        stripped = LABEL.sub(lambda match: match.group("rest") or "", line).strip()
        if not stripped:
            continue
        return stripped if len(stripped) <= limit else stripped[: limit - 1].rstrip() + "…"
    return None
