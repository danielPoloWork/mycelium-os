# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Claude export reader (doc 08 §6).

The official export's ``conversations.json`` is a JSON array whose conversations
store their turns as a **list** — ``chat_messages``, in order — which makes this
the simple case beside ChatGPT's node tree, and the second provider doc 08 §10's
first gate requires.

Two shapes of message body exist in the wild and this reader reads both. The
older one is a flat ``text`` string. The newer one is a ``content`` list of typed
blocks (``{"type": "text", "text": …}``, and others for tool use and thinking),
which is preferred when present because it is the faithful one: a block whose
type this module has no rendering for is preserved into ``meta.blocks`` rather
than concatenated into prose that would read as something the assistant said.

``attachments`` and ``files`` are references to bytes that are not in the export.
They are preserved into ``meta`` verbatim — doc 08 §4's invariant 4 wants
attachments in the CAS, and an export that names a file it does not contain has
nothing to put there, so the reference is kept and the absence is a warning.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Final

from pydantic import JsonValue

from mycelium_chats.readers.base import (
    ImportContext,
    ReadConversation,
    ReaderError,
    ReadResult,
    normalise_role,
)
from mycelium_chats.record import Fragment, Message

__all__ = ["ClaudeReader"]

_PLACEHOLDER: Final = "00000000000000000000000000"

_CONVERSATION_KEYS: Final = frozenset(
    {"uuid", "name", "created_at", "updated_at", "chat_messages", "account"}
)
_MESSAGE_KEYS: Final = frozenset({"uuid", "text", "content", "sender", "created_at", "updated_at"})
_TEXT_BLOCKS: Final = frozenset({"text"})


class ClaudeReader:
    """Reads the Claude ``conversations.json`` export."""

    id = "claude"
    description = "Claude conversations.json export (ordered chat_messages)"

    def sniff(self, text: str, *, source_uri: str) -> bool:
        """A JSON array whose first object has `chat_messages` and a `uuid`."""
        try:
            parsed = json.loads(text)
        except ValueError:
            return False
        items = parsed if isinstance(parsed, list) else [parsed]
        first = next((item for item in items if isinstance(item, dict)), None)
        return first is not None and "chat_messages" in first and "uuid" in first

    def read(self, text: str, context: ImportContext) -> ReadResult:
        try:
            parsed = json.loads(text)
        except ValueError as error:
            msg = f"not JSON: {error}"
            raise ReaderError(msg) from error
        items = parsed if isinstance(parsed, list) else [parsed]
        conversations: list[ReadConversation] = []
        warnings: list[str] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                warnings.append(f"entry {index} is not an object; skipped")
                continue
            conversation, notes = _one(item, context)
            conversations.append(conversation)
            warnings.extend(notes)
        if not conversations:
            msg = "no conversations in this export"
            raise ReaderError(msg)
        return ReadResult(conversations=tuple(conversations), warnings=tuple(warnings))


def _one(item: Mapping[str, Any], context: ImportContext) -> tuple[ReadConversation, list[str]]:
    raw = item.get("chat_messages")
    if not isinstance(raw, list):
        msg = "a Claude conversation needs a `chat_messages` array"
        raise ReaderError(msg)

    lines: list[Message | Fragment] = []
    warnings: list[str] = []
    attachments = 0
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        built, note = _message(entry)
        if built is None:
            continue
        lines.append(built)
        attachments += note

    if attachments:
        warnings.append(
            f"{attachments} message(s) reference attachments the export does not contain; "
            "the references are preserved in `meta` and there are no bytes to take into custody"
        )

    return (
        ReadConversation(
            title=context.title or str(item.get("name") or "").strip() or "Untitled conversation",
            lines=tuple(lines),
            provider_conv_id=_str(item.get("uuid")),
            started_at=_stamp(item.get("created_at")),
            structure_inferred=False,
            recognised=len(lines),
            meta=_unmapped(item, _CONVERSATION_KEYS),
        ),
        warnings,
    )


def _message(entry: Mapping[str, Any]) -> tuple[Message | None, int]:
    """One `chat_messages` entry, and whether it referenced absent attachments."""
    meta: dict[str, JsonValue] = _unmapped(entry, _MESSAGE_KEYS)
    texts: list[str] = []
    opaque: list[JsonValue] = []

    blocks = entry.get("content")
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and block.get("type") in _TEXT_BLOCKS:
                value = block.get("text")
                if isinstance(value, str):
                    texts.append(value)
                    continue
            opaque.append(block)
    if not texts:
        flat = entry.get("text")
        if isinstance(flat, str) and flat:
            texts.append(flat)

    referenced = 0
    for key in ("attachments", "files"):
        value = entry.get(key)
        if isinstance(value, list) and value:
            meta[key] = value
            referenced = 1

    body = "\n".join(texts).strip("\n")
    if not body and not opaque and not referenced:
        return None, 0
    if opaque:
        meta["blocks"] = opaque

    sender = entry.get("sender")
    role = normalise_role(sender)
    if sender is not None and str(sender).casefold() != role:
        meta["provider_role"] = str(sender)

    return (
        Message(
            conv_id=_PLACEHOLDER,
            seq=1,
            role=role,
            ts=_stamp(entry.get("created_at")),
            content=body,
            meta=meta,
        ),
        referenced,
    )


def _unmapped(item: Mapping[str, Any], known: frozenset[str]) -> dict[str, JsonValue]:
    return {key: item[key] for key in sorted(item) if key not in known and item[key] is not None}


def _stamp(value: object) -> datetime | None:
    """An ISO-8601 timestamp as Claude writes it, or ``None``.

    Accepts the `Z` suffix Python's parser refused before 3.11 and still accepts
    it explicitly, because an export written by a service is not a place to be
    clever about input. A naive timestamp is read as UTC — the export's own
    convention — rather than as local time, which would make the same file import
    differently on two machines.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
