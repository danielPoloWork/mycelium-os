# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The generic JSON reader (doc 08 §6) — a configured field mapping.

*"a generic JSON mapper (configurable field mapping) for unknown shapes"*. The
escape hatch: a provider this module has never seen, read by telling it where
the fields are instead of shipping a release.

The mapping is dotted paths into the export, set in `[chats] mapping`::

    [chats.mapping]
    messages = "history"          # the array of turns
    role = "speaker"              # the role, within a turn
    content = "body"              # the text, within a turn
    timestamp = "at"              # optional
    title = "subject"             # optional, conversation level
    conversations = "threads"     # optional; absent means the root is one

Six keys, and only three are required — an export with an array of turns, each
having a role and a text, is the shape every chat API converged on. A path
segment that is an integer indexes a list, so ``payload.0.messages`` works.

**This reader is off unless configured**, and that is why it can sit ahead of
the transcript and paste readers in the registry: an unconfigured mapping
recognises nothing, so it never competes for an input somebody else should read
(see :func:`mycelium_chats.readers.reader_for`).

Unmapped keys are preserved exactly as they are by the provider readers — the
invariant does not weaken because the shape was described by an operator rather
than by this module.
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

__all__ = ["MAPPING_KEYS", "REQUIRED_KEYS", "GenericJsonReader"]

_PLACEHOLDER: Final = "00000000000000000000000000"

MAPPING_KEYS: Final = ("conversations", "messages", "role", "content", "timestamp", "title")
REQUIRED_KEYS: Final = ("messages", "role", "content")


class GenericJsonReader:
    """Reads any JSON export through `[chats] mapping`."""

    id = "generic"
    description = "Any JSON export, through the [chats] mapping field paths"

    def sniff(self, text: str, *, source_uri: str) -> bool:
        """Whether the input is JSON at all.

        The mapping decides the rest, and the registry only offers this reader
        when a mapping is configured — so "is it JSON" is the whole question this
        method can honestly answer.
        """
        try:
            json.loads(text)
        except ValueError:
            return False
        return True

    def read(self, text: str, context: ImportContext) -> ReadResult:
        mapping = dict(context.mapping)
        unknown = sorted(set(mapping) - set(MAPPING_KEYS))
        if unknown:
            msg = (
                f"[chats.mapping] has unknown key(s) {unknown}; "
                f"this reader maps: {', '.join(MAPPING_KEYS)}"
            )
            raise ReaderError(msg)
        missing = [key for key in REQUIRED_KEYS if not mapping.get(key)]
        if missing:
            msg = (
                f"[chats.mapping] needs {missing} to read a JSON export; set them to dotted "
                f'paths into the file, e.g. messages = "history", role = "speaker", '
                'content = "body"'
            )
            raise ReaderError(msg)

        try:
            document = json.loads(text)
        except ValueError as error:
            msg = f"not JSON: {error}"
            raise ReaderError(msg) from error

        roots = _conversations(document, mapping.get("conversations"))
        conversations: list[ReadConversation] = []
        warnings: list[str] = []
        for index, root in enumerate(roots):
            turns = _dig(root, mapping["messages"])
            if not isinstance(turns, list):
                warnings.append(
                    f"entry {index}: {mapping['messages']!r} is not an array here; skipped"
                )
                continue
            lines: list[Message | Fragment] = []
            for turn in turns:
                built = _turn(turn, mapping)
                if built is not None:
                    lines.append(built)
            if not lines:
                warnings.append(f"entry {index}: no readable turns; skipped")
                continue
            title = context.title or _title(root, mapping.get("title")) or "Untitled conversation"
            conversations.append(
                ReadConversation(
                    title=title,
                    lines=tuple(lines),
                    structure_inferred=False,
                    recognised=len(lines),
                    meta=_conversation_meta(root, mapping),
                )
            )

        if not conversations:
            msg = (
                "the mapping matched no conversations; check the paths against the file "
                f"({', '.join(f'{key}={mapping[key]!r}' for key in REQUIRED_KEYS)})"
            )
            raise ReaderError(msg)
        return ReadResult(conversations=tuple(conversations), warnings=tuple(warnings))


def _conversations(document: object, path: str | None) -> tuple[Any, ...]:
    """The conversation objects: the mapped array, else the document itself."""
    if path:
        found = _dig(document, path)
        if isinstance(found, list):
            return tuple(found)
        return (found,) if found is not None else ()
    if isinstance(document, list):
        return tuple(document)
    return (document,)


def _dig(value: object, path: str) -> Any:
    """Follow a dotted path, indexing lists by integer segments.

    Returns ``None`` for a path that does not resolve rather than raising: a
    mapping is an operator's description of a file they have, and the useful
    error is *"the mapping matched no conversations"* with the paths printed,
    not a traceback at the first absent key.
    """
    current: Any = value
    for segment in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(segment)
        elif isinstance(current, list) and segment.lstrip("-").isdigit():
            index = int(segment)
            current = current[index] if -len(current) <= index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _turn(turn: object, mapping: Mapping[str, str]) -> Message | None:
    if not isinstance(turn, Mapping):
        return None
    content = _dig(turn, mapping["content"])
    if isinstance(content, list):
        # A blocked body, as the newer APIs write it: keep the text parts.
        parts = [part for part in content if isinstance(part, str)]
        content = "\n".join(parts) if parts else None
    if not isinstance(content, str) or not content.strip():
        return None
    raw_role = _dig(turn, mapping["role"])
    role = normalise_role(raw_role)
    meta: dict[str, JsonValue] = {
        key: turn[key]
        for key in sorted(turn)
        if key not in {mapping["role"], mapping["content"], mapping.get("timestamp", "")}
        and turn[key] is not None
    }
    if raw_role is not None and str(raw_role).casefold() != role:
        meta["provider_role"] = str(raw_role)
    return Message(
        conv_id=_PLACEHOLDER,
        seq=1,
        role=role,
        ts=_stamp(_dig(turn, mapping["timestamp"]) if mapping.get("timestamp") else None),
        content=content,
        meta=meta,
    )


def _title(root: object, path: str | None) -> str | None:
    if not path:
        return None
    found = _dig(root, path)
    return found.strip() if isinstance(found, str) and found.strip() else None


def _conversation_meta(root: object, mapping: Mapping[str, str]) -> dict[str, JsonValue]:
    if not isinstance(root, Mapping):
        return {}
    consumed = {mapping["messages"].split(".")[0]}
    if mapping.get("title"):
        consumed.add(mapping["title"].split(".")[0])
    return {key: root[key] for key in sorted(root) if key not in consumed and root[key] is not None}


def _stamp(value: object) -> datetime | None:
    """A timestamp in whichever of the two common shapes the export used."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None
