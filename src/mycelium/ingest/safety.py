# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Bounds on hostile input, checked before an engine sees it (spec 02 §8, D-017).

The connector already refuses a source that is too *large*. That is not enough,
and this module exists because measuring said so rather than because a threat
model guessed it. Two findings, both on files far below any byte ceiling:

- **A 550 KB HTML file nested 50 000 elements deep never finished converting.**
  docling took 0.6 s at depth 200, 7 s at 1 000, 45 s at 5 000, and had not
  returned after five minutes at 50 000. Cost is superlinear in *structure*, and
  no limit on bytes bounds it.
- **The same file made pandoc's adapter raise `RecursionError`** out of
  `json.loads` — an exception no caller was catching, so a hostile document
  crashed ingestion instead of being quarantined by it.

So the guards here bound *shape*, not size, and they run in microseconds on a
linear scan before any engine is handed anything:

``guard_archive``
    A ZIP container (DOCX, ODT, EPUB) declares its uncompressed sizes in its own
    directory, so a decompression bomb can be refused by reading the header —
    50 MB of zeros compresses to 51 KB, which is invisible to a byte ceiling and
    obvious to a ratio check. Member names are checked too: an absolute or
    `..`-bearing entry has no legitimate use in a document container.

``guard_markup``
    Maximum tag-nesting depth and tag count, from one pass over the bytes. It is
    a *bound*, not a parse: it never has to be exactly right, only conservative
    enough that no honest document approaches it and no hostile one slips past.
    The default depth ceiling is 256; the deepest document in this repository's
    own corpora nests 8.

A breach is a :class:`~mycelium.ingest.errors.ParseError` naming the limit and
the measured value — the per-document failure ingestion quarantines, never an
abort of the whole build (spec 02 §5).
"""

import io
import zipfile
from dataclasses import dataclass
from typing import Final

from mycelium.ingest.errors import ParseError
from mycelium.ingest.media import DOCX, EPUB, HTML, LATEX, ODT, RST

__all__ = ["DEFAULT_LIMITS", "Limits", "guard", "guard_archive", "guard_markup"]

_ARCHIVE_TYPES: Final = frozenset({DOCX, ODT, EPUB})
_MARKUP_TYPES: Final = frozenset({HTML, RST, LATEX})


@dataclass(frozen=True, slots=True)
class Limits:
    """What ingestion refuses to attempt. Generous by design — see the module docstring."""

    max_depth: int = 256
    """Tag-nesting depth. Human documents nest single digits; 256 is unreachable
    by accident and reached instantly by a nesting bomb."""

    max_tags: int = 500_000
    """Total markup tags in one document."""

    max_uncompressed_bytes: int = 512 * 1024 * 1024
    """Total declared uncompressed size of a container's members."""

    max_compression_ratio: float = 200.0
    """Uncompressed ÷ compressed. Real DOCX files sit around 5-20; a zeros bomb
    is in the thousands."""

    max_members: int = 10_000
    """Members in one container — a defence against the many-small-files variant."""

    max_nodes: int = 200_000
    """KIR nodes one document may produce, enforced as the builder emits them."""

    max_text_bytes: int = 64 * 1024 * 1024
    """Total node text in one KIR document."""


DEFAULT_LIMITS: Final = Limits()


def guard(data: bytes, media_type: str, *, limits: Limits = DEFAULT_LIMITS) -> None:
    """Apply whichever bounds fit `media_type`. Silence means "worth attempting"."""
    if media_type in _ARCHIVE_TYPES:
        guard_archive(data, limits=limits)
    elif media_type in _MARKUP_TYPES:
        guard_markup(data, limits=limits)


def guard_archive(data: bytes, *, limits: Limits = DEFAULT_LIMITS) -> None:
    """Refuse a ZIP container that would cost more to open than it claims to be.

    Reading the central directory is cheap and requires decompressing nothing —
    the sizes a bomb needs to lie about are the ones it has to declare.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile:
        # Not an archive at all. Left to the parser to report in its own words
        # rather than pre-empted here: "this DOCX is not a ZIP" is a parse
        # failure, and the engines already say so precisely.
        return

    if len(infos) > limits.max_members:
        msg = f"archive declares {len(infos)} members, above the {limits.max_members} limit"
        raise ParseError(msg)

    uncompressed = sum(info.file_size for info in infos)
    compressed = sum(info.compress_size for info in infos) or len(data) or 1
    if uncompressed > limits.max_uncompressed_bytes:
        msg = (
            f"archive declares {uncompressed} uncompressed bytes, above the "
            f"{limits.max_uncompressed_bytes}-byte limit"
        )
        raise ParseError(msg)
    ratio = uncompressed / compressed
    if ratio > limits.max_compression_ratio:
        msg = (
            f"archive expands {ratio:.0f}x ({compressed} to {uncompressed} bytes), above the "
            f"{limits.max_compression_ratio:.0f}x limit — a decompression bomb looks like this"
        )
        raise ParseError(msg)

    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/") or (len(name) > 1 and name[1] == ":"):
            msg = f"archive member {info.filename!r} escapes the container"
            raise ParseError(msg)


def guard_markup(data: bytes, *, limits: Limits = DEFAULT_LIMITS) -> None:
    """Refuse markup nested or populated beyond what any document needs.

    One linear pass, no parser, no allocation proportional to the input. Void and
    self-closing tags do not open a level, and a stray closing tag cannot drive
    the depth below zero — the scan is a bound on a well-formed reading, and a
    malformed document is the engine's business to report.
    """
    depth = 0
    deepest = 0
    tags = 0
    index = 0
    while True:
        index = data.find(b"<", index)
        if index == -1:
            break
        following = data[index + 1 : index + 2]
        if following == b"/":
            depth = max(0, depth - 1)
            tags += 1
        elif following.isalpha():
            tags += 1
            end = data.find(b">", index)
            if end == -1:
                break
            if data[end - 1 : end] != b"/":
                name = _tag_name(data, index + 1)
                if name not in _VOID_TAGS:
                    depth += 1
                    deepest = max(deepest, depth)
        index += 1
        if tags > limits.max_tags:
            msg = f"document carries more than {limits.max_tags} markup tags"
            raise ParseError(msg)
        if deepest > limits.max_depth:
            msg = (
                f"markup nests deeper than {limits.max_depth} levels; no document needs that, "
                "and parsing it costs superlinear time (ADR-0033)"
            )
            raise ParseError(msg)


_VOID_TAGS: Final = frozenset(
    {
        b"area",
        b"base",
        b"br",
        b"col",
        b"embed",
        b"hr",
        b"img",
        b"input",
        b"link",
        b"meta",
        b"param",
        b"source",
        b"track",
        b"wbr",
        b"!doctype",
        b"?xml",
    }
)


def _tag_name(data: bytes, start: int) -> bytes:
    end = start
    limit = min(len(data), start + 32)
    while end < limit and (data[end : end + 1].isalpha() or data[end : end + 1] in {b"!", b"?"}):
        end += 1
    return data[start:end].lower()
