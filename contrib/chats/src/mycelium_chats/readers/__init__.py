# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Readers: one input shape in, chat records out (doc 08 §6).

A reader is the module's own protocol, and the reason it is *not* a
:class:`mycelium.sdk.protocols.Parser` is worth stating, because it is one of
the plugin-API findings roadmap 5.5 exists to produce (ADR-0077). A `Parser`
maps bytes to **KIR** — the document AST the compiler chunks and indexes. A chat
export maps to a **chat record**, which is a different canonical form with a
different schema, and the KIR only appears later when the compiler parses the
*projection*. Declaring these as `Parser`s would have meant either lying about
their output type or compiling `.chat.jsonl` directly, which doc 08 §7 rules out
by making the Markdown projection the indexed artifact. So the shape below is
internal to the module, and the observation for the 1.0 freeze is that spec 05
§4.1's protocol set has no seat for a format reader whose output is not KIR.

**Sniffing decides nothing an operator asked about.** `--provider` pins the
reader when it is given, exactly as `[ingest] parsers` pins a parser: pinned
resolution first, detection only as a convenience when nothing was pinned. A
sniff that matches nothing is an error naming every reader, never a silent
fall-through to the most permissive one — which the pasted-text reader would
otherwise always be, since any bytes are *some* text.

The five readers, in sniff order (most specific first):

``chatgpt``     the official ChatGPT export's ``conversations.json``
``claude``      the official Claude export's ``conversations.json``
``generic``     any JSON, through `[chats] mapping` — off unless configured
``transcript``  a Markdown transcript with role markers
``pasted``      plain text a human copied out of a web page
"""

from mycelium_chats.readers.base import (
    READERS,
    ImportContext,
    Reader,
    ReaderError,
    ReadResult,
    reader_for,
    reader_ids,
)

__all__ = [
    "READERS",
    "ImportContext",
    "ReadResult",
    "Reader",
    "ReaderError",
    "reader_for",
    "reader_ids",
]
