# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ChatGPT export reader (doc 08 §6).

The official export's ``conversations.json`` is a JSON array of conversations,
and each one stores its turns as a **tree** rather than a list: ``mapping`` is a
node table keyed by id, every node points at its ``parent``, and ``current_node``
names the leaf the conversation actually ended on. Branches exist because a user
can edit a turn and regenerate from it, which forks the tree and leaves the
abandoned branch in the file.

**So the linearisation is a decision, not a formality.** This reader walks
``current_node`` up its parent chain and reverses it, which is the path the user
last saw — the conversation as it happened. Abandoned branches are *not*
dropped: nodes the walk did not visit are counted, named in a warning, and their
text is kept as ``fragment`` lines, because doc 08 §6 says unparseable residue is
"kept as a raw block in the record, never dropped" and an abandoned branch is
exactly residue that a naive reader would lose silently.

Content arrives as ``content.parts``, a list that usually holds strings and
sometimes holds objects (image pointers, audio assets). A string part is content;
an object part is not text this module can render, so it is preserved into
``meta.parts`` and accounted for rather than flattened into a misleading string.
"""

import json
from collections.abc import Mapping, Sequence
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

__all__ = ["ChatGptReader"]

_PLACEHOLDER: Final = "00000000000000000000000000"

_CONVERSATION_KEYS: Final = frozenset(
    {"title", "create_time", "update_time", "mapping", "current_node", "conversation_id", "id"}
)
"""Top-level keys this reader interprets. Everything else is preserved."""

_MESSAGE_KEYS: Final = frozenset({"author", "create_time", "content", "id"})


class ChatGptReader:
    """Reads the ChatGPT ``conversations.json`` export."""

    id = "chatgpt"
    description = "ChatGPT conversations.json export (node tree, current-branch walk)"

    def sniff(self, text: str, *, source_uri: str) -> bool:
        """A JSON array whose first object has both `mapping` and `current_node`.

        Both, not either: `mapping` alone is a common key in unrelated JSON, and
        the pair is what makes this ChatGPT's tree rather than somebody's dict.
        """
        try:
            parsed = json.loads(text)
        except ValueError:
            return False
        items = parsed if isinstance(parsed, list) else [parsed]
        first = next((item for item in items if isinstance(item, dict)), None)
        return first is not None and "mapping" in first and "current_node" in first

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
    mapping = item.get("mapping")
    if not isinstance(mapping, dict):
        msg = "a ChatGPT conversation needs a `mapping` object"
        raise ReaderError(msg)

    walked = _current_branch(mapping, item.get("current_node"))
    lines: list[Message | Fragment] = []
    recognised = 0
    for node_id in walked:
        node = mapping.get(node_id)
        message = node.get("message") if isinstance(node, dict) else None
        if not isinstance(message, dict):
            continue  # the root node carries no message
        built = _message(message)
        if built is None:
            continue
        lines.append(built)
        recognised += 1

    # Branches the walk did not visit: kept, counted, and named.
    warnings: list[str] = []
    abandoned = [
        node_id
        for node_id, node in mapping.items()
        if node_id not in walked
        and isinstance(node, dict)
        and isinstance(node.get("message"), dict)
    ]
    for node_id in sorted(abandoned):
        node = mapping[node_id]
        built = _message(node["message"])
        if built is None:
            continue
        lines.append(
            Fragment(
                conv_id=_PLACEHOLDER,
                seq=len(lines) + 1,
                content=built.content,
                meta={
                    "reason": "abandoned_branch",
                    "node": node_id,
                    "role": built.role,
                    **({"ts": built.ts.isoformat()} if built.ts is not None else {}),
                },
            )
        )
    if abandoned:
        warnings.append(
            f"{len(abandoned)} message(s) on abandoned edit branches kept as fragments "
            "(a regenerated turn leaves its predecessor in the export)"
        )

    started = _epoch(item.get("create_time"))
    return (
        ReadConversation(
            title=context.title or str(item.get("title") or "").strip() or "Untitled conversation",
            lines=tuple(lines),
            provider_conv_id=_first_str(item, ("conversation_id", "id")),
            started_at=started,
            structure_inferred=False,
            recognised=recognised,
            meta=_unmapped(item, _CONVERSATION_KEYS),
        ),
        warnings,
    )


def _current_branch(mapping: Mapping[str, Any], current: object) -> tuple[str, ...]:
    """The node ids from the root to `current`, in conversation order.

    Walks parents rather than children because the parent link is single-valued
    and the child links are not: from the leaf there is exactly one path back, so
    no choice has to be invented. A missing or unknown `current_node` falls back
    to the whole table in file order — which is what an export truncated by hand
    looks like, and is better than reading nothing.
    """
    if not isinstance(current, str) or current not in mapping:
        return tuple(mapping)
    chain: list[str] = []
    seen: set[str] = set()
    node_id: str | None = current
    while isinstance(node_id, str) and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        chain.append(node_id)
        node = mapping[node_id]
        node_id = node.get("parent") if isinstance(node, dict) else None
    return tuple(reversed(chain))


def _message(message: Mapping[str, Any]) -> Message | None:
    """One node's message, or ``None`` when it carries no text at all."""
    content = message.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    texts: list[str] = []
    opaque: list[JsonValue] = []
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, str):
                texts.append(part)
            else:
                opaque.append(part)
    elif isinstance(content, str):
        texts.append(content)

    body = "\n".join(texts).strip("\n")
    if not body and not opaque:
        return None

    author = message.get("author")
    raw_role = author.get("role") if isinstance(author, dict) else None
    role = normalise_role(raw_role)
    metadata = message.get("metadata")
    model = metadata.get("model_slug") if isinstance(metadata, dict) else None

    meta: dict[str, JsonValue] = _unmapped(message, _MESSAGE_KEYS)
    if opaque:
        # Non-text parts: an image pointer or an audio asset. Preserved whole
        # rather than rendered, because there is no honest text for them.
        meta["parts"] = opaque
    if raw_role is not None and str(raw_role).casefold() != role:
        meta["provider_role"] = str(raw_role)
    if isinstance(content, dict) and content.get("content_type") not in (None, "text"):
        meta["content_type"] = str(content["content_type"])

    return Message(
        conv_id=_PLACEHOLDER,
        seq=1,
        role=role,
        model=str(model) if isinstance(model, str) and model else None,
        ts=_epoch(message.get("create_time")),
        content=body,
        meta=meta,
    )


def _unmapped(item: Mapping[str, Any], known: frozenset[str]) -> dict[str, JsonValue]:
    """Every key this reader did not interpret, preserved (invariant 3).

    Sorted, and only where the value is JSON — which it is, the input was JSON —
    so two machines reading the same export write the same `meta`.
    """
    return {key: item[key] for key in sorted(item) if key not in known and item[key] is not None}


def _epoch(value: object) -> datetime | None:
    """A ChatGPT timestamp: epoch seconds as a float, or absent."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _first_str(item: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None
