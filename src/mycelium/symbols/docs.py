# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Symbols from what documentation defines (roadmap 5.1, ADR-0073).

Spec 03 §2's second source is *"definition syntax (docs)"*, and Markdown has
exactly one construct with that name — the definition list::

    snapshot
    : An immutable, published build.

The Mycelium Markdown Profile (spec 03 §3.1) is Obsidian-flavoured and Obsidian
renders no definition lists, so markdown-it sees the lines above as one
paragraph with a soft break. That is enough: KIR keeps the break as a newline,
and the shape — term lines, then lines that open with ``: `` — is recognised in
the paragraph's *text*, with no parser plugin and no new node kind in a closed
vocabulary (spec 03 §4). The syntax is read where it is written; nothing about
how the document is parsed or chunked changes.

The second form is the one documentation actually uses. Measured over the
three corpora the evaluation runs on (2026-09-10): **zero** definition lists,
and a heading whose whole text is the thing it documents — ``## uv.lock``,
``### .python-version``, a command name in backticks — is how reference pages
are written. So a heading defines a symbol when its text *is* an identifier:
one token, carrying a signal that it is a name rather than a word — an
underscore, a dot, a path separator, a ``::``, a camel-case hump, or a trailing
``()``. That is spec 04 §2's own definition of an identifier-like token, applied
to headings. ``## Retries`` is a title and defines nothing; ``## RetryPolicy``
defines ``sym:doc:RetryPolicy``. Backticks do not survive into KIR (the adapter
flattens inline code to its text), so the rule is on the text alone and a
heading written with or without them reads the same.

Every symbol here is language ``doc`` and kind ``term``: documentation defines
*terms*, and whether a term is also a class in some language is a question the
code side answers with its own symbol under its own language.
"""

import re
from typing import Final

__all__ = [
    "DOC_LANGUAGE",
    "MAX_TERM_LENGTH",
    "TERM_KIND",
    "definition_terms",
    "heading_term",
]

DOC_LANGUAGE: Final = "doc"
"""The `<language>` segment of every symbol documentation defines."""

TERM_KIND: Final = "term"
"""The `kind` of every symbol documentation defines."""

MAX_TERM_LENGTH: Final = 80
"""A term longer than this is a sentence that happens to precede a colon."""

_NUMBERING: Final = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
"""A leading section number (`3.3 mycelium_neighbors`), dropped before the test."""

_TOKEN: Final = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.:/+-]*$")
"""One token: no whitespace, the characters identifiers and paths are made of."""

_VERSION: Final = re.compile(r"^v?\d+(?:\.\d+)+$", re.IGNORECASE)
"""`v0.4.0` has dots and is not a name."""

_CAMEL: Final = re.compile(r"[a-z][A-Z]")

_DEFINITION_LINE: Final = re.compile(r"^:\s")


def heading_term(text: str) -> str | None:
    """The identifier a heading defines, or ``None`` when the heading is a title.

    The heading's text, less a leading section number and a trailing colon, must
    be a single token with at least one identifier signal. ``helper()`` keeps its
    name and loses the parentheses — the parentheses were the signal.
    """
    stripped = _NUMBERING.sub("", text.strip(), count=1).strip().rstrip(":.")
    callable_ = stripped.endswith("()")
    if callable_:
        stripped = stripped[:-2]
    if not stripped or not _TOKEN.match(stripped) or _VERSION.match(stripped):
        return None
    if not any(character.isalpha() for character in stripped):
        return None
    signalled = (
        callable_
        or "_" in stripped
        or "." in stripped
        or "/" in stripped
        or "::" in stripped
        or _CAMEL.search(stripped) is not None
    )
    return stripped if signalled else None


def definition_terms(text: str) -> tuple[tuple[int, str], ...]:
    """``(line offset, term)`` for each term a definition-list paragraph defines.

    The paragraph's lines are term lines followed by definition lines, every
    one of the latter opening with ``: ``; anything else is prose and yields
    nothing. The offset is the term's line within the paragraph, so a caller
    holding the paragraph's source line can say exactly where the term sits.
    """
    lines = text.split("\n")
    first_definition = next(
        (index for index, line in enumerate(lines) if _DEFINITION_LINE.match(line)), None
    )
    if first_definition is None or first_definition == 0:
        return ()
    if not all(_DEFINITION_LINE.match(line) for line in lines[first_definition:]):
        return ()
    terms: list[tuple[int, str]] = []
    for offset, line in enumerate(lines[:first_definition]):
        term = line.strip()
        if term and len(term) <= MAX_TERM_LENGTH:
            terms.append((offset, term))
    return tuple(terms)
