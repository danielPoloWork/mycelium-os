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
and a heading built around the thing it documents — ``## uv.lock``,
``## The pyproject.toml``, ``## manylinux_compatible enforcement`` — is how
reference pages are written. So a heading defines the name it is **about**, and
a heading is about a name when it *is* that name, or that name and one other
word (:data:`MAX_HEADING_WORDS`). ``## Retries`` is a title and defines nothing;
``## RetryPolicy``, ``## The pyproject.toml`` and ``## pylock.toml format`` each
define one term. Backticks do not survive into KIR (the adapter flattens inline
code to its text), so the rule is on the text alone and a heading written with
or without them reads the same.

**The one-extra-word bound is measured, not chosen** (roadmap 5.19). At one
word — ADR-0073's original rule — the *only* headings a documentation corpus
offers are the entries of a structural tour: of uv's seven, four sit under
*Working on projects ▸ Project structure* and three under *Installing uv ▸
Installation methods*, while the reference sections that actually explain those
files (``## The pyproject.toml``, ``## pylock.toml format``, ``## uv.lock
output``) were invisible. Widening by one word reaches twelve more on uv and ten
on its ingested twin with **no non-name on any of the three corpora**. Widening
by two reaches ``e.g`` — out of a heading that is a git URL with a
parenthetical — and by four it reaches ``x86_64`` out of *"Transparent x86_64
emulation on aarch64"*, where the subject is the emulation and the architecture
is a modifier. So the bound is the largest one at which no corpus yields
something that is not a name.

**A heading with two names is a sentence, not a title**, and yields nothing:
*"For local dependencies, uv caches based on the last-modified time of …
``setup.py``, or ``setup.cfg`` file."* is a paragraph the HTML projection turned
into a heading, and a section documents one subject. Per-word sentence
punctuation is stripped before the test for the same reason — *"Learn more about
the core concepts in uv."* would otherwise define ``uv.``.

What the widening does **not** change is what a *name* is: every term still has
to be an :func:`identifier_like` token, so the planner can still find every
symbol the extractor writes (ADR-0080). Only which headings are read has moved.

Every symbol here is language ``doc`` and kind ``term``: documentation defines
*terms*, and whether a term is also a class in some language is a question the
code side answers with its own symbol under its own language.
"""

import re
from typing import Final

__all__ = [
    "DOC_LANGUAGE",
    "MAX_HEADING_WORDS",
    "MAX_TERM_LENGTH",
    "TERM_KIND",
    "definition_terms",
    "heading_subject",
    "identifier_like",
]

DOC_LANGUAGE: Final = "doc"
"""The `<language>` segment of every symbol documentation defines."""

TERM_KIND: Final = "term"
"""The `kind` of every symbol documentation defines."""

MAX_TERM_LENGTH: Final = 80
"""A term longer than this is a sentence that happens to precede a colon."""

MAX_HEADING_WORDS: Final = 2
"""How many words a heading may hold and still be *about* one of them.

The name, plus at most one word that frames it — an article (``The
pyproject.toml``), a qualifier (``pylock.toml format``), a verb (``Using
requirements.in``). Measured rather than chosen: see the module docstring for
what each wider bound admits on the three corpora, and ADR-0091 for the sites it
was measured against."""

_NUMBERING: Final = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
"""A leading section number (`3.3 mycelium_neighbors`), dropped before the test."""

_TOKEN: Final = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.:/+-]*$")
"""One token: no whitespace, the characters identifiers and paths are made of."""

_VERSION: Final = re.compile(r"^v?\d+(?:\.\d+)+$", re.IGNORECASE)
"""`v0.4.0` has dots and is not a name."""

_CAMEL: Final = re.compile(r"[a-z][A-Z]")

_DEFINITION_LINE: Final = re.compile(r"^:\s")


def identifier_like(token: str, *, callable_: bool = False) -> bool:
    """Whether `token` is spec 04 §2's *identifier-like token*.

    One token — no whitespace — made of the characters identifiers and paths are
    made of, carrying at least one signal that it is a name rather than a word:
    an underscore, a dot, a path separator, a ``::``, a camel-case hump, or (for
    a caller that stripped them) a trailing ``()``. ``Retries`` is a word;
    ``RetryPolicy``, ``uv.lock``, ``mycelium_neighbors`` and ``docs/adr`` are
    names. A version string is neither: ``v0.4.0`` has dots and names nothing.

    Spec 04 §2 states this test for the *planner* — the signal that routes a
    query to exact lookup — and roadmap 5.1 needed the same test for *headings*,
    to decide which of them define a term. They are one rule and this is the one
    copy of it: a heading that defines a symbol and a query that can find one
    have to agree about what a name looks like, and two regexes drifting apart
    would make the leg miss exactly the symbols the extractor created
    (ADR-0080).
    """
    if not token or not _TOKEN.match(token) or _VERSION.match(token):
        return False
    if not any(character.isalpha() for character in token):
        return False
    return (
        callable_
        or "_" in token
        or "." in token
        or "/" in token
        or "::" in token
        or _CAMEL.search(token) is not None
    )


def _word_name(word: str) -> str | None:
    """One heading word as a name, less the punctuation a heading puts on it.

    Quoting and bracketing marks go first, then the punctuation that ends a
    clause — which is what keeps *"…concepts in uv."* from defining ``uv.``.
    Parentheses are stripped **after** the callable test and not before, or
    ``helper()`` would arrive as ``helper``, having lost the one signal that made
    it a name. A leading dot is never stripped, because ``.venv`` and
    ``.python-version`` are names that begin with one, and an underscore never
    is, because ``__init__`` is a name made of them.
    """
    stripped = word.strip("`*\"'[]{}").rstrip(",;:!?.").lstrip(",;:!?")
    callable_ = stripped.endswith("()")
    if callable_:
        stripped = stripped[:-2]
    stripped = stripped.strip("()")
    return stripped if identifier_like(stripped, callable_=callable_) else None


def heading_subject(text: str) -> tuple[str, bool] | None:
    """``(name, the heading is that name)``, or ``None`` for a heading about none.

    The heading's text, less a leading section number, must be at most
    :data:`MAX_HEADING_WORDS` words and hold **exactly one** name. Two names make
    it a list or a sentence; none makes it a title. ``helper()`` keeps its name
    and loses the parentheses — the parentheses were the signal.

    The second element separates the two shapes this rule now accepts, because
    resolution needs to tell them apart: ``## uv.lock`` *is* the name and
    ``## uv.lock output`` *frames* it, and a record that must name one site
    should name the first kind (ADR-0091). It is a fact about the heading, not a
    judgment about the prose beneath it — which is the distinction roadmap 5.19
    measured and could not make.

    Strictly wider than the rule it replaces (ADR-0073's *the heading is the
    name*): a one-word heading reaches the single-name branch unchanged and comes
    back flagged as direct, so nothing a previous build defined stops being
    defined, and nothing it named stops being named.
    """
    words = _NUMBERING.sub("", text.strip(), count=1).split()
    if not words or len(words) > MAX_HEADING_WORDS:
        return None
    names = [name for name in (_word_name(word) for word in words) if name]
    return (names[0], len(words) == 1) if len(names) == 1 else None


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
