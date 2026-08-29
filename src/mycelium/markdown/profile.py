# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Mycelium Markdown Profile v1 — the Obsidian-flavored syntax (spec 03 §3.1, D-022).

CommonMark and GFM tables come from markdown-it; this module adds the three
constructs Obsidian vaults rely on that CommonMark has no notion of:

============================  ===========================================
Syntax                        Result
============================  ===========================================
``[[doc]]`` ``[[doc#H]]``     a ``wikilink`` token carrying its raw target
``[[doc|label]]``             …with the label as its display text
``![[doc]]``                  an ``embed`` token (links, never transcluded)
``#tag``                      a ``tag_ref`` token
``> [!note] Title``           a blockquote recognised as a ``callout``
============================  ===========================================

Everything else a vault may contain — Dataview queries, Templater directives,
plugin syntax nobody here has heard of — is left as plain text by construction:
these rules match their own delimiters and nothing else, so unknown syntax can
never break a build (the profile's "tolerated" row).

Callouts are recognised rather than tokenized: a callout *is* a blockquote whose
first line opens with ``[!type]``, so the block parser stays untouched and the
adapter reinterprets the quote. Wikilinks and tags need real inline rules,
registered before ``link`` and ``text`` respectively so they win their delimiters.
"""

import re
from dataclasses import dataclass
from typing import Final

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline

__all__ = [
    "CALLOUT_PATTERN",
    "Callout",
    "TAG_PATTERN",
    "WIKILINK_CLOSE",
    "WIKILINK_OPEN",
    "match_callout",
    "profile_markdown_it",
]

WIKILINK_OPEN: Final = "[["
WIKILINK_CLOSE: Final = "]]"

CALLOUT_PATTERN: Final = re.compile(r"^\[!(?P<kind>[A-Za-z0-9_-]+)\]\s*(?P<title>.*?)\s*$")
"""``[!note] Optional title`` — the first line of a callout blockquote."""

TAG_PATTERN: Final = re.compile(r"#(?![0-9]+(?:\s|$))([\w][\w/-]*)", re.UNICODE)
"""``#tag`` — at least one word character, and never a bare number (``#1`` is prose)."""

_TAG_PRECEDERS: Final = frozenset("([{<\"'")


@dataclass(frozen=True, slots=True)
class Callout:
    """The head of a callout blockquote: its type and optional title."""

    kind: str
    title: str | None


def match_callout(first_line: str) -> Callout | None:
    """Return the callout head if `first_line` opens one, else ``None``."""
    match = CALLOUT_PATTERN.match(first_line.strip())
    if match is None:
        return None
    title = match.group("title") or None
    return Callout(kind=match.group("kind").lower(), title=title)


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    """Parse ``[[target]]``, ``[[target|label]]``, and the ``![[target]]`` embed."""
    start = state.pos
    is_embed = state.src[start] == "!"
    open_at = start + 1 if is_embed else start
    if not state.src.startswith(WIKILINK_OPEN, open_at):
        return False

    close_at = state.src.find(WIKILINK_CLOSE, open_at + len(WIKILINK_OPEN))
    if close_at == -1:
        return False
    inner = state.src[open_at + len(WIKILINK_OPEN) : close_at]
    if not inner or "[" in inner or "\n" in inner:
        return False

    target, separator, label = inner.partition("|")
    target = target.strip()
    if not target:
        return False
    display = label.strip() if separator else target

    if not silent:
        token = state.push("embed" if is_embed else "wikilink", "", 0)
        token.content = display
        token.meta = {"target": target}
        token.markup = WIKILINK_OPEN

    state.pos = close_at + len(WIKILINK_CLOSE)
    return True


def _tag_rule(state: StateInline, silent: bool) -> bool:
    """Parse an inline ``#tag``, but only where a tag can legally start."""
    start = state.pos
    if state.src[start] != "#":
        return False
    # A tag opens a line, follows whitespace, or follows an opening bracket or
    # quote. `C#` and `issue#3` are prose, and stay prose.
    if start > 0:
        previous = state.src[start - 1]
        if not previous.isspace() and previous not in _TAG_PRECEDERS:
            return False
    match = TAG_PATTERN.match(state.src, start)
    if match is None:
        return False

    if not silent:
        token = state.push("tag_ref", "", 0)
        token.content = match.group(1)
        token.markup = "#"

    state.pos = match.end()
    return True


def profile_markdown_it() -> MarkdownIt:
    """Build the parser for Mycelium Markdown Profile v1.

    CommonMark plus GFM tables (the profile's first row), plus the wikilink,
    embed, and tag rules. HTML is *not* enabled: authored content is untrusted
    (D-017), and raw HTML has no place in a representation whose whole purpose is
    to be typed and quotable — it reaches KIR as an ``opaque`` node instead.
    """
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    md.inline.ruler.before("link", "wikilink", _wikilink_rule)
    md.inline.ruler.before("text", "tag_ref", _tag_rule)
    return md
