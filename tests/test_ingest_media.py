# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Media-type classification (roadmap 4.1): the extension is the claim dispatch uses, the
bytes are the check, and only a contradiction is reported."""

import pytest

from mycelium.ingest.media import (
    DOCX,
    EXTENSIONS,
    HTML,
    MARKDOWN,
    MEDIA_TYPES,
    PDF,
    ZIP,
    classify,
    media_type_for_name,
    sniff,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("notes.md", MARKDOWN),
        ("NOTES.MD", MARKDOWN),
        ("a/b/c.markdown", MARKDOWN),
        ("page.HTM", HTML),
        ("report.pdf", PDF),
        ("brief.docx", DOCX),
    ],
)
def test_extension_names_the_media_type(name: str, expected: str) -> None:
    assert media_type_for_name(name) == expected


def test_an_unknown_extension_is_none_rather_than_octet_stream() -> None:
    # A type nothing declares would fail dispatch anyway; `None` lets the caller
    # say "this extension is not one Mycelium ingests" instead.
    assert media_type_for_name("archive.tar.gz") is None
    assert media_type_for_name("Makefile") is None


def test_every_mapped_extension_names_a_known_media_type() -> None:
    assert set(EXTENSIONS.values()) <= set(MEDIA_TYPES)


def test_sniff_recognises_pdf_and_zip_containers_only() -> None:
    assert sniff(b"%PDF-1.7\n...") == PDF
    assert sniff(b"PK\x03\x04rest of an ooxml part") == ZIP
    assert sniff(b"PK\x05\x06") == ZIP
    assert sniff(b"# a markdown heading\n") is None


def test_a_container_extension_agrees_with_a_zip_signature() -> None:
    # Magic bytes can say "this is a ZIP" and no more; which OOXML layout is
    # inside it is the parser's question, not the sniffer's.
    assert classify("brief.docx", b"PK\x03\x04").mismatch is None


def test_a_text_format_with_no_signature_is_not_a_mismatch() -> None:
    assert classify("notes.md", b"# heading\n").mismatch is None


def test_contradicting_bytes_are_reported_and_the_extension_still_wins() -> None:
    claim = classify("notes.md", b"%PDF-1.4\n")
    assert claim.declared == MARKDOWN
    assert claim.detected == PDF
    assert claim.mismatch is not None
    assert "text/markdown" in claim.mismatch
    assert "application/pdf" in claim.mismatch
