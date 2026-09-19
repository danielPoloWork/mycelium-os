# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""How this project decides what encoding a document's bytes are in (roadmap 6.15).

HTML arrives as bytes and has to become text before anything can parse it, and
the rule that picks the encoding is a **parser decision this repository owns**
rather than one it inherits from whatever happens to be installed.

**The defect this exists to remove.** BeautifulSoup — which docling's HTML
backend parses through — resolves an encoding detector *at import time* from the
first of ``cchardet``, ``chardet`` and ``charset-normalizer`` it can import, and
consults it for any document that declares no encoding. Nothing in a project's
own dependency list decides which of the three that is: at roadmap 6.6 a
dependency group for an unrelated release tool pulled ``chardet`` into the
environment and **seven documents of the vendored ingested corpus projected
differently** (BUG-0032). Ingestion is authoring-time, so this is not a hole in
NFR-1 — it is a hole in the reproducibility of a *committed artifact*, and
``tools/build_ingested_corpus.py --check`` could only detect it afterwards,
unable to tell an environment difference from a parser change.

**The rule.** In order, first one that decodes the bytes wins:

1. a **byte-order mark** — the one encoding declaration carried in the byte
   stream itself;
2. an **encoding the document declares** — ``<meta charset>``,
   ``<meta http-equiv="content-type">``, or an XML declaration;
3. **UTF-8**, if the bytes are valid UTF-8;
4. **windows-1252**, the last-ditch fallback for legacy bytes.

Nothing else is consulted, and every step is a function of the bytes alone, so
two machines with different packages installed read a document identically. It
is deliberately *BeautifulSoup's own chain with the ambient step removed* rather
than a new invention — which is also why adopting it left the committed corpus
byte-identical: every one of its 62 HTML sources is valid UTF-8 and declares
nothing, so step 3 decides, exactly as it did before (ADR-0134). The one place it
is deliberately not identical is how far step 2 looks (see :data:`_DECLARED`).

**What is given up, and it is named rather than hidden.** A document that
declares no encoding, is not valid UTF-8, and is not windows-1252 — undeclared
Shift-JIS, say — was sometimes read correctly by a detector and is now read as
windows-1252, i.e. as mojibake. That case gets a warning on the document rather
than silence, because it is precisely where the ambient detector used to have
the casting vote. The remedy is the one the web already has: a document that is
not UTF-8 declares what it is.

**Why a detector could not be pinned instead.** Declaring one — bs4 publishes a
``beautifulsoup4[charset-normalizer]`` extra for exactly this — makes it
*present*, not *chosen*: bs4 prefers ``cchardet`` and then ``chardet`` over it,
so any environment holding one of those still overrides the declaration. And the
answer depends on the detector's **version**, not only its identity: replayed
against this corpus, every ``chardet`` from 3.0.4 to 6.0.0 misreads seven
documents and 7.6.0 misreads none. A dependency pin cannot pin an answer that
moves with a minor release (ADR-0134).
"""

import codecs
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Self

from mycelium.ingest.errors import ParseError

__all__ = ["UTF8_BOM", "DecodeRule", "Decoded", "declared_encoding", "decode_html"]

UTF8_BOM: Final = codecs.BOM_UTF8
"""The three bytes that say "this is UTF-8" inside the stream itself."""

_BYTE_ORDER_MARKS: Final[tuple[tuple[bytes, str], ...]] = (
    # UTF-32 before UTF-16: a little-endian UTF-32 mark *starts with* the
    # little-endian UTF-16 one, so testing the shorter first would mis-read it.
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

_FALLBACK: Final = "windows-1252"
"""What legacy bytes are read as when nothing says otherwise — the same
last-ditch encoding BeautifulSoup and every browser end at."""

_DECLARED: Final = re.compile(
    rb"""<\s*meta[^>]+charset\s*=\s*["']?\s*([^>\s"';/]+)"""
    rb"""|<\?xml[^>]+encoding\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
"""An encoding the document declares, in either of the two syntaxes that carry one.

The whole document is scanned. HTML5 prescans 1024 bytes and BeautifulSoup looks
at 2 KiB or 5 % of the document, whichever is larger, because a browser has a page
to start painting; a compiler has no such race, and a document that says what it
is should be read as it says, wherever it says it. This is the only step where
the rule departs from the chain it is otherwise a copy of, and it departs in the
direction of honouring the author."""


class DecodeRule(StrEnum):
    """Which step of the rule decided, recorded so a reading can be explained."""

    BYTE_ORDER_MARK = "byte-order-mark"
    DECLARATION = "declaration"
    UTF8 = "utf-8"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class Decoded:
    """One document's bytes, read as text, and the account of how."""

    text: str
    encoding: str
    """The codec that decoded it, in Python's canonical spelling."""

    rule: DecodeRule
    notes: tuple[str, ...] = ()
    """What a reader of the fidelity report needs to be told about this reading.

    Empty for the ordinary cases, and that is deliberate: the rule is total and
    public, so *"read as UTF-8 because the bytes are valid UTF-8"* is a fact
    anyone holding the bytes can recompute, and a note on every document is a
    note nobody reads. Non-empty exactly where the bytes did not determine the
    answer on their own — a declaration that does not decode them, or a fallback."""

    def utf8_with_bom(self) -> bytes:
        """The same text as bytes no downstream reader can guess wrong.

        A UTF-8 byte-order mark is the one encoding declaration that lives in the
        byte stream rather than in the markup, so prefixing it changes no element,
        no attribute and no character of the document — and BeautifulSoup takes a
        sniffed mark as *definite*, ahead of the detector it would otherwise
        consult. That is what closes the path: the bytes handed to the HTML
        backend answer the question before it can be asked.

        The mark is added only to the bytes handed to a parser. Nothing stored
        carries it — a byte-order mark in a document this project *writes* is the
        defect BUG-0008 records.
        """
        return UTF8_BOM + self.text.encode("utf-8")

    @classmethod
    def _of(cls, data: bytes, encoding: str, rule: DecodeRule, notes: tuple[str, ...]) -> Self:
        return cls(
            text=data.decode(encoding),
            encoding=codecs.lookup(encoding).name,
            rule=rule,
            notes=notes,
        )


def declared_encoding(data: bytes) -> str | None:
    """The encoding `data` declares, as written, or ``None``.

    Returned verbatim rather than canonicalised, because an unusable declaration
    has to be reported in the words the document used.
    """
    match = _DECLARED.search(data)
    if match is None:
        return None
    name = match.group(1) or match.group(2)
    return name.decode("ascii", errors="replace").strip()


def decode_html(data: bytes, *, source_uri: str) -> Decoded:
    """Read `data` as text by the rule in this module's docstring.

    Raises :class:`~mycelium.ingest.errors.ParseError` when no step decodes the
    bytes — the per-document failure the evidence lane quarantines, which is the
    honest answer for a file that is not text in any encoding this rule knows.
    """
    for mark, encoding in _BYTE_ORDER_MARKS:
        if data.startswith(mark):
            body = data[len(mark) :]
            try:
                return Decoded._of(body, encoding, DecodeRule.BYTE_ORDER_MARK, ())
            except UnicodeDecodeError:
                # A mark whose bytes are not in the encoding it announces. Fall
                # through with the mark still on: nothing downstream can trust it.
                break

    notes: list[str] = []
    declared = declared_encoding(data)
    if declared is not None:
        try:
            return Decoded._of(data, declared, DecodeRule.DECLARATION, ())
        except LookupError:
            notes.append(
                f"the document declares the encoding {declared!r}, which is not an encoding "
                f"this build knows; it was read by the {DecodeRule.UTF8}/{_FALLBACK} rule instead"
            )
        except UnicodeDecodeError:
            notes.append(
                f"the document declares the encoding {declared!r} and its bytes are not valid "
                f"in it; it was read by the {DecodeRule.UTF8}/{_FALLBACK} rule instead"
            )

    try:
        utf8 = Decoded._of(data, "utf-8", DecodeRule.UTF8, tuple(notes))
    except UnicodeDecodeError:
        utf8 = None
    if utf8 is not None:
        if "\x00" not in utf8.text:
            return utf8
        # UTF-8 accepted the bytes and produced NUL characters, which HTML5 says
        # can never be content: this is almost always UTF-16 with no mark. The
        # rule still does not guess — guessing is what it exists to remove — but
        # a reading nobody could have authored is said out loud rather than
        # projected in silence.
        notes.append(
            "the document decoded as UTF-8 containing NUL characters, which HTML cannot "
            "carry; it is most likely UTF-16 without a byte-order mark, and it should "
            "declare what it is"
        )
        return Decoded(text=utf8.text, encoding=utf8.encoding, rule=utf8.rule, notes=tuple(notes))

    if declared is None:
        notes.append(
            f"the document declares no encoding and its bytes are not valid UTF-8, so it was "
            f"read as {_FALLBACK}; if that is wrong, the document should declare what it is"
        )
    try:
        return Decoded._of(data, _FALLBACK, DecodeRule.FALLBACK, tuple(notes))
    except UnicodeDecodeError as error:
        said = "no declaration" if declared is None else f"{declared!r} declared"
        msg = (
            f"{source_uri}: these bytes are not text in any encoding the HTML lane reads - "
            f"no byte-order mark, {said}, not valid UTF-8, and not valid {_FALLBACK} ({error})"
        )
        raise ParseError(msg) from error
