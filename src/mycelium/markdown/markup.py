# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Drop raw HTML markup from the prose KIR indexes, without interpreting it (5.40).

Raw HTML is never parsed by this profile — ``html: False``, because authored
content is untrusted (D-017) — so a document that wraps a caption in
``<p align="center">`` reaches the adapter as one paragraph whose text *is* the
markup. Every tag name, attribute name and attribute value becomes a term of that
chunk and adds to its BM25 length: ``p``, ``align``, ``center``, ``img``, ``alt``,
``src``, ``href`` and a CDN URL, indexed as though the author had written them.
The ingested twin, whose HTML lane hands the same caption to docling, indexes the
sentence and nothing else — the one real lane disagreement ADR-0107 measured.

This module removes the markup and keeps the words. It is deliberately **not**
parsing: nothing here resolves an entity, follows an ``href``, honours a ``src``,
or turns a tag into a node. A run of characters is recognised as markup and
deleted; what is left is the text a reader of the rendered page would see, which
is what the twin indexes and what a query should match.

**The hard part is that `<word>` is also how documentation writes a placeholder.**
Measured across the three corpora (2026-09-14): ``<package_name>``, ``<version>``,
``<hostname>``, ``<token>``, ``<path>``, ``<reason>`` and ninety more — and the
names collide with real elements, because ``<code>``, ``<pre>``, ``<script>``,
``<source>``, ``<path>``, ``<link>``, ``<i>`` and ``<a>`` are all both. A tag-name
whitelist therefore cannot separate them, and neither can "does it look like a
tag": ``<2, and foo ~=1.2.3 is equal to foo >`` is a comparison a reader wrote.

So a run is markup only on **syntactic evidence that a lone placeholder cannot
produce**:

``</name>``
    A closing tag. Prose does not write one.
``<name attr="value">``
    An open or void tag carrying at least one ``name=value`` attribute.
    ``<link once released>`` — a real line from this repository's bug template —
    has bare words and no ``=``, so it stays.
``<name>`` … ``</name>``
    An open tag whose matching close appears **in the same block**. Block scope,
    not document scope: ADR-0107's table names ``<i>`` and ``<u>`` in one cell and
    demonstrates ``<u>lined</u>`` in another, and document scope let the second
    delete the first.
``<!-- … -->``
    A comment, whole — **including any inline code inside it**, which is the one
    place a literal part is deleted rather than preserved. A comment's content is
    invisible on the rendered page and absent from the twin, so indexing it lets a
    search return words the reader cannot find; and three of uv's TODO comments
    quote a command in backticks, so a rule that stopped at the code span would
    leave two thirds of each of them behind.

Everything else is kept, and that asymmetry is the deliberate one: leaving markup
in costs a few noise terms, and deleting a placeholder costs the name of the thing
the sentence is about.

**Inline code is never touched by the tag rules.** ``spans`` already records what
a corpus wrote as code (ADR-0094), and a documentation corpus explains HTML by
quoting it: ``` `<p align="center">` ``` appears five times in this repository's
own roadmap, and ADR-0107's own table names eleven tags in a code span. The
adapter therefore hands this module the block's parts with the code spans marked;
a tag is deleted only when the whole of it lies outside them.
"""

import re
from collections.abc import Iterable, Sequence
from typing import Final

__all__ = ["Part", "strip_markup"]

Part = tuple[str, bool]
"""One piece of a block's flattened text: ``(text, is_literal)``. A literal part
came from inline code and is passed through untouched."""

_NAME: Final = r"[A-Za-z][A-Za-z0-9-]*"

_CLOSING: Final = re.compile(rf"</({_NAME})\s*>")
"""``</p>`` — a closing tag, with the optional whitespace HTML allows."""

_OPENING: Final = re.compile(rf"<({_NAME})((?:\s[^<>]*)?)>")
"""``<p …>`` — an open or void tag. The attribute run may not contain ``<`` or
``>``, so an unterminated ``<`` cannot swallow the rest of a paragraph."""

_ATTRIBUTE: Final = re.compile(rf"\s{_NAME}\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'<>`]+)")
"""``align="center"``, ``align=center``. The ``=`` is the whole discrimination:
a placeholder's words (``<link once released>``) never carry one."""

_COMMENT: Final = re.compile(r"<!--.*?-->", re.DOTALL)
"""A whole comment. An unterminated ``<!--`` is left alone: half a comment is
still somebody's words, and deleting to the end of a block would be guessing."""


def _paired(plain: str) -> frozenset[str]:
    """Tag names the block's plain text both opens and closes."""
    opened = {match.group(1).lower() for match in _OPENING.finditer(plain)}
    closed = {match.group(1).lower() for match in _CLOSING.finditer(plain)}
    return frozenset(opened & closed)


def _markup_spans(
    text: str, literal: Sequence[bool], paired: frozenset[str]
) -> list[tuple[int, int]]:
    """Every ``(start, end)`` of `text` that is markup, ordered and non-overlapping.

    A comment counts wherever it falls; a tag counts only where no character of it
    is literal, so quoting one never deletes it.
    """

    def outside_code(span: tuple[int, int]) -> bool:
        return not any(literal[span[0] : span[1]])

    spans = [match.span() for match in _COMMENT.finditer(text)]
    spans.extend(span for match in _CLOSING.finditer(text) if outside_code(span := match.span()))
    for match in _OPENING.finditer(text):
        name, attributes = match.group(1), match.group(2)
        if not outside_code(match.span()):
            continue
        if _ATTRIBUTE.search(attributes) or name.lower() in paired:
            spans.append(match.span())
    spans.sort()

    merged: list[tuple[int, int]] = []
    for start, end in spans:
        # A tag inside a comment is already covered by the comment's own span.
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            continue
        merged.append((start, end))
    return merged


def strip_markup(parts: Sequence[Part] | Iterable[Part]) -> str:
    """Join a block's flattened parts, deleting the raw HTML markup among them.

    The block is scanned as one string with the literal positions marked, rather
    than part by part, because the two rules need different reach: a tag must lie
    wholly outside inline code to be deleted, and a comment must be able to
    swallow the code it quotes. Pairing is resolved over the plain characters
    only — a corpus that writes ``` `</div>` ``` is naming a tag, not closing one.
    """
    pieces = list(parts)
    text = "".join(part for part, _ in pieces)
    if "<" not in text:
        return text

    literal: list[bool] = []
    for part, is_literal in pieces:
        literal.extend([is_literal] * len(part))
    plain = "".join(
        character for character, is_literal in zip(text, literal, strict=True) if not is_literal
    )
    spans = _markup_spans(text, literal, _paired(plain))
    if not spans:
        return text

    out: list[str] = []
    cursor = 0
    for start, end in spans:
        out.append(text[cursor:start])
        cursor = end
    out.append(text[cursor:])
    # The indentation that laid a wrapper out goes with the wrapper: a caption
    # inside `<p align="center">` is written on its own line, and keeping the
    # newline that positioned the tag would open the block with a blank line that
    # the rendered page does not have. Only a block something was removed from is
    # touched, so nothing else in the corpus moves by a byte.
    return "".join(out).strip()
