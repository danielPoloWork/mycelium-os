# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Mycelium Chats — a local archive of user↔chatbot conversations (D-025, spec doc 08).

The first **module** (D-027's second taxonomy level): its own distribution, its
own CLI surface, activated by name in ``[modules] enabled``, and built
exclusively on the extension points the core makes public — which is the other
half of why it exists. Doc 08 §2 says it plainly: *"if the D-023 extension
points can't support this module cleanly, they get fixed before the 1.0 API
freeze"*.

Three jobs, in doc 08 §1's order:

**Archive.** A provider export, a Markdown transcript or a pasted conversation
becomes a canonical ``*.chat.jsonl`` record under ``chats/``, with the original
in tier-1 custody, content verbatim, and everything the schema has no field for
preserved rather than dropped (:mod:`~mycelium_chats.record`,
:mod:`~mycelium_chats.archive`).

**Resume.** ``mycelium chats resume`` emits a continuation package — the whole
conversation or a token-budgeted tail — so the thread can carry on in any
chatbot (:mod:`~mycelium_chats.formats`).

**Port.** ``mycelium chats export`` writes the four shapes doc 08 §9 lists, and
says what each one cannot carry.

And the reason the archive is *knowledge* rather than a pile of files: every
conversation is projected into ``knowledge/evidence/chats/`` as Markdown the
compiler indexes like anything else, so ``mycelium_search`` finds chat content
with citations that resolve to a conversation and a message
(:mod:`~mycelium_chats.projection`).

**Boundary (D-004 stays intact).** This archives *historical transcripts as
knowledge sources* — documents about the past. It is not agent memory: nothing
here manages any agent's live working state, and a conversation enters the
archive the way a PDF enters ingestion, as evidence with custody.

**Local, always.** No network egress, ever (doc 08 §8). Imports read files or
standard input, and nothing in this distribution opens a socket.
"""

from mycelium_chats.plugin import ChatsModule, plugin

__all__ = ["ChatsModule", "plugin"]

__version__ = "0.1.0"
