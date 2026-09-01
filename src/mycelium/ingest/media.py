# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Which media type a source is, and how much that claim is worth.

A parser is chosen by media type, so this is the dispatch key for the whole
ingestion lane. Two rules keep the choice honest:

**The extension is a claim, not a fact.** It is what the operator's filesystem
says, and the content is untrusted (D-017). So the extension picks the candidate
type and :func:`sniff` checks the bytes against it. A contradiction is *reported*
rather than resolved silently: parsing still follows the extension — that is what
the operator asked for and what the pinned parser list was written against — and
the disagreement travels with the document as a warning.

**The map is closed.** An unknown extension is `None`, never
``application/octet-stream``: a type no parser declares would fail dispatch
anyway, and "this extension is not one Mycelium ingests" is the more useful
sentence. Every type here is declared by a parser that ships in this repository.

Sniffing is deliberately shallow. Container formats (`.docx`, `.odt`, `.epub`)
are all ZIP archives, so magic bytes can confirm "this is a ZIP" and no more;
telling one part layout from another is the parser's job, and a parser handed the
wrong one fails per document — which is the outcome quarantine exists for.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

__all__ = [
    "DOCX",
    "EPUB",
    "EXTENSIONS",
    "HTML",
    "LATEX",
    "MARKDOWN",
    "MEDIA_TYPES",
    "ODT",
    "PDF",
    "RST",
    "ZIP",
    "MediaTypeClaim",
    "classify",
    "media_type_for_name",
    "sniff",
]

MARKDOWN: Final = "text/markdown"
HTML: Final = "text/html"
PDF: Final = "application/pdf"
DOCX: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ODT: Final = "application/vnd.oasis.opendocument.text"
EPUB: Final = "application/epub+zip"
RST: Final = "text/x-rst"
LATEX: Final = "application/x-latex"
ZIP: Final = "application/zip"

MEDIA_TYPES: Final = (MARKDOWN, HTML, PDF, DOCX, ODT, EPUB, RST, LATEX)
"""Every media type v1 ingestion knows how to name, and some parser declares."""

EXTENSIONS: Final[Mapping[str, str]] = {
    ".md": MARKDOWN,
    ".markdown": MARKDOWN,
    ".html": HTML,
    ".htm": HTML,
    ".pdf": PDF,
    ".docx": DOCX,
    ".odt": ODT,
    ".epub": EPUB,
    ".rst": RST,
    ".tex": LATEX,
}
"""Filename extension → media type. Keys are lowercase; lookup lowercases its input."""

_ZIP_CONTAINERS: Final = frozenset({DOCX, ODT, EPUB})
_MAGIC: Final = (
    (b"%PDF-", PDF),
    (b"PK\x03\x04", ZIP),
    (b"PK\x05\x06", ZIP),  # an empty archive is still an archive
)


@dataclass(frozen=True, slots=True)
class MediaTypeClaim:
    """What the name says, what the bytes say, and whether they agree."""

    declared: str | None
    detected: str | None

    @property
    def mismatch(self) -> str | None:
        """A warning line when the bytes contradict the extension, else ``None``.

        Only a contradiction counts. Silence from :func:`sniff` — every
        text-based format has no magic number — is not evidence of anything, and
        reporting it as if it were would put a warning on most ingested files.
        """
        if self.declared is None or self.detected is None:
            return None
        expected = ZIP if self.declared in _ZIP_CONTAINERS else self.declared
        if self.detected == expected:
            return None
        return (
            f"content begins like {self.detected} but the extension claims "
            f"{self.declared}; parsed as {self.declared}"
        )


def media_type_for_name(name: str) -> str | None:
    """The media type a filename claims, or ``None`` for an extension we do not ingest."""
    return EXTENSIONS.get(PurePosixPath(name).suffix.lower())


def sniff(data: bytes) -> str | None:
    """What the leading bytes say the content is, or ``None`` when they say nothing.

    Every ZIP container answers :data:`ZIP`: the signature identifies the
    container, and which document format is inside it is not a question magic
    bytes can answer.
    """
    for signature, media_type in _MAGIC:
        if data.startswith(signature):
            return media_type
    return None


def classify(name: str, data: bytes) -> MediaTypeClaim:
    """Classify a source from its name and its leading bytes."""
    return MediaTypeClaim(declared=media_type_for_name(name), detected=sniff(data))
