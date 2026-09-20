# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What encoding a document's bytes are read in, and who decides (roadmap 6.15).

Two halves. The first is the rule itself — byte-order mark, then a declaration,
then UTF-8, then windows-1252 — exercised at each step and at each way a step can
fail. The second is the property the rule exists for: an encoding detector that
happens to be importable cannot change what an ingestion projects (BUG-0032).

The second half is written so it cannot pass vacuously. The tests that bind a
hostile detector first assert that the detector *would* change how BeautifulSoup
reads the very same bytes, and only then that it does not change what the parser
produces — because a guard whose premise has quietly stopped holding is a guard
that passes with the guard deleted (BUG-0020).
"""

import codecs
from pathlib import Path

import bs4.dammit
import pytest
from bs4 import BeautifulSoup

from mycelium.ingest.encoding import UTF8_BOM, Decoded, DecodeRule, decode_html
from mycelium.ingest.errors import ParseError
from mycelium.ingest.media import DOCX, HTML
from mycelium.ingest.registry import BUILTIN_PARSERS
from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.protocols import Blob
from mycelium.sdk.types import KirDocument

pytestmark = pytest.mark.boundary("B4")
"""The threat-model boundary these tests hold: source content entering the compiler."""

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
CORPUS_SOURCES = Path(__file__).parent.parent / "eval" / "corpora" / "uv-docs-ingested" / "sources"

CURLY = "’"
"""A right single quotation mark: three bytes in UTF-8, three characters in
windows-1252, which is what makes a wrong encoding visible rather than theoretical."""

MOJIBAKE = "’".encode().decode("cp1252")
"""Those three characters — what the quote above becomes when it is read wrong."""


class HostileDetector:
    """An encoding detector that is confidently wrong, the way chardet was.

    ``bs4.dammit`` binds whichever of cchardet, chardet and charset-normalizer it
    can import and asks it about any document that declares nothing. Binding this
    one is, in effect, what an unrelated dependency group did at roadmap 6.6.
    """

    __name__ = "hostile"

    @staticmethod
    def detect(data: bytes) -> dict[str, object]:
        return {"encoding": "windows-1252", "confidence": 0.99}


@pytest.fixture
def hostile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs4.dammit, "chardet_module", HostileDetector)


def read(data: bytes) -> Decoded:
    return decode_html(data, source_uri="file:inline.html")


def docling_kir(data: bytes, *, media_type: str = HTML) -> KirDocument:
    parser = BUILTIN_PARSERS["docling"]()
    blob = Blob.of(data, media_type=media_type, source_uri="file:inline")
    return parser.parse(blob, doc_id=DOC_ID)


def as_text(markup: str) -> str:
    """The same markup parsed from `str`, where no encoding question arises at all."""
    return BeautifulSoup(markup, "html.parser").get_text()


# ---------------------------------------------------------------------------
# The rule, step by step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mark", "codec"),
    [
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
    ],
)
def test_a_byte_order_mark_decides_and_does_not_survive(mark: bytes, codec: str) -> None:
    """The mark is a declaration, not content: it decides, and is then gone.

    All five widths, and the pair that makes the order matter: a little-endian
    UTF-32 mark *starts with* the little-endian UTF-16 one, so a rule that tests
    the shorter first reads a UTF-32 document as UTF-16.
    """
    text = f"<p>a paragraph{CURLY}s worth</p>"
    outcome = read(mark + text.encode(codec))
    assert outcome.rule is DecodeRule.BYTE_ORDER_MARK
    assert outcome.encoding == codecs.lookup(codec).name
    assert outcome.text == text
    assert outcome.notes == ()


def test_utf16_without_a_mark_is_not_guessed_at_but_is_not_silent_either() -> None:
    """The rule's sharpest limit, pinned rather than left to be discovered.

    UTF-16 of ASCII is *valid UTF-8* — every other byte is a NUL — so the UTF-8
    step accepts it and produces text nobody authored. A detector sometimes saw
    through that; this rule does not guess, because guessing is the thing it
    exists to remove. What it does instead is say so: HTML cannot carry a NUL, so
    a decode that produces one is reported on the document.
    """
    outcome = read("<p>plain</p>".encode("utf-16-le"))
    assert outcome.rule is DecodeRule.UTF8
    assert "\x00" in outcome.text
    assert len(outcome.notes) == 1
    assert "most likely UTF-16 without a byte-order mark" in outcome.notes[0]


@pytest.mark.parametrize(
    "markup",
    [
        '<meta charset="windows-1252">',
        "<meta charset=windows-1252>",
        '<meta http-equiv="content-type" content="text/html; charset=windows-1252">',
    ],
)
def test_an_encoding_the_document_declares_is_honoured(markup: str) -> None:
    """In whichever of the syntaxes that carry one."""
    text = f"<html><head>{markup}</head><body><p>café</p></body></html>"
    outcome = read(text.encode("cp1252"))
    assert outcome.rule is DecodeRule.DECLARATION
    assert outcome.encoding == "cp1252"
    assert outcome.text == text
    assert outcome.notes == ()


def test_a_declaration_past_the_prescan_window_is_still_honoured() -> None:
    """The one place the rule is deliberately *not* BeautifulSoup's.

    HTML5 prescans 1024 bytes and bs4 looks at 2 KiB or 5 % of the document,
    whichever is larger, because a browser has a page to start painting. A
    compiler has no such race, so a document that says what it is is read as it
    says, wherever it says it. The padding here is past both windows.
    """
    padding = "<!-- " + "x" * 4000 + " -->"
    text = f"<html><head>{padding}<meta charset='windows-1252'></head><body>café</body></html>"
    outcome = read(text.encode("cp1252"))
    assert outcome.rule is DecodeRule.DECLARATION
    assert outcome.text == text


def test_valid_utf8_that_declares_nothing_is_utf8_and_says_nothing() -> None:
    """The overwhelmingly common case, and every document of the vendored corpus.

    No note, deliberately: the rule is total and public, so a reader holding the
    bytes can recompute this, and a note on every document is a note nobody reads.
    """
    text = f"<p>a paragraph{CURLY}s worth</p>"
    outcome = read(text.encode("utf-8"))
    assert outcome.rule is DecodeRule.UTF8
    assert outcome.encoding == "utf-8"
    assert outcome.text == text
    assert outcome.notes == ()


def test_bytes_that_declare_nothing_and_are_not_utf8_fall_back_and_say_so() -> None:
    """The one case this rule is worse at than a detector, reported rather than hidden."""
    text = "<p>café</p>"
    outcome = read(text.encode("cp1252"))
    assert outcome.rule is DecodeRule.FALLBACK
    assert outcome.encoding == "cp1252"
    assert outcome.text == text
    assert len(outcome.notes) == 1
    assert "declares no encoding" in outcome.notes[0]
    assert "should declare what it is" in outcome.notes[0]


def test_a_declaration_that_does_not_decode_the_bytes_is_reported() -> None:
    """A document that says UTF-8 and is not: read on, and say the declaration failed."""
    text = "<html><head><meta charset='utf-8'></head><body><p>café</p></body></html>"
    outcome = read(text.encode("cp1252"))
    assert outcome.rule is DecodeRule.FALLBACK
    assert outcome.text == text
    assert "declares the encoding 'utf-8'" in outcome.notes[0]
    assert "not valid in it" in outcome.notes[0]


def test_an_encoding_no_codec_answers_to_is_reported_rather_than_raised() -> None:
    text = "<html><head><meta charset='klingon-1'></head><body><p>ok</p></body></html>"
    outcome = read(text.encode("utf-8"))
    assert outcome.rule is DecodeRule.UTF8
    assert outcome.text == text
    assert "'klingon-1'" in outcome.notes[0]
    assert "not an encoding this build knows" in outcome.notes[0]


def test_bytes_that_are_text_in_nothing_the_rule_knows_are_a_parse_error() -> None:
    """A per-document failure, which the evidence lane quarantines (spec 02 §5).

    0x81, 0x8d and 0x90 are three of the five positions windows-1252 leaves
    undefined, so these bytes are neither UTF-8 nor windows-1252 and nothing is
    left to try.
    """
    with pytest.raises(ParseError, match="not text in any encoding"):
        read(b"<p>\x81\x90\x8d</p>")


def test_a_byte_order_mark_that_lies_does_not_take_the_document_down() -> None:
    """A UTF-16 mark on bytes that are not UTF-16: read on rather than refuse."""
    outcome = read(b"\xff\xfe" + "<p>café</p>".encode("cp1252"))
    assert outcome.rule is DecodeRule.FALLBACK


# ---------------------------------------------------------------------------
# What the rule is for: nothing ambient decides
# ---------------------------------------------------------------------------


def test_the_marked_bytes_read_back_as_the_same_text_with_no_mark_in_them(hostile: None) -> None:
    """The mechanism at the seam it has to hold: what `utf8_with_bom` writes is
    what BeautifulSoup reads, and the detector is never asked."""
    raw = (FIXTURES / "source.html").read_bytes()
    expected = as_text(raw.decode("utf-8"))

    # The premise: on these bytes a detector *can* change what BeautifulSoup reads.
    assert BeautifulSoup(raw, "html.parser").get_text() != expected

    marked = read(raw).utf8_with_bom()
    assert marked.startswith(UTF8_BOM)
    soup = BeautifulSoup(marked, "html.parser")
    assert soup.original_encoding == "utf-8"
    assert soup.get_text() == expected
    assert "﻿" not in soup.get_text()


def test_an_importable_detector_cannot_change_what_html_projects(hostile: None) -> None:
    """The defect of BUG-0032, and the property that closes it.

    A detector bound by an unrelated package reads this document as windows-1252,
    which turns its one typographic quote into three characters — asserted, not
    assumed — and the KIR comes out with the sentence the author wrote.

    The KIR is checked for the *mojibake* rather than for the quote because
    docling's backend normalises a typographic apostrophe to a straight one, so
    the quote is not in the output under any reading. What tells the two readings
    apart is the wreckage the wrong one leaves.
    """
    raw = (FIXTURES / "source.html").read_bytes()
    misread = BeautifulSoup(raw, "html.parser")
    assert misread.original_encoding == "windows-1252"
    assert MOJIBAKE in misread.get_text(), "the premise: the detector mangles this document"

    texts = [node.text or "" for node in docling_kir(raw).nodes]
    assert any("pandoc's Markdown writer" in text for text in texts), "the sentence, intact"
    assert not any(MOJIBAKE in text for text in texts), "and no mojibake reached the KIR"


def test_the_html_lane_records_nothing_when_the_bytes_decided(hostile: None) -> None:
    """An ordinary HTML document's fidelity report gains no note from any of this."""
    assert docling_kir(b"<h1>Caching</h1><p>Prune the cache.</p>").warnings == ()


def test_a_fallback_reaches_the_document_that_needed_it(hostile: None) -> None:
    """And when the bytes did *not* decide, the reading is on the record — in the
    KIR, because the fidelity report is a pure function of it (ADR-0034)."""
    kir = docling_kir("<h1>Café</h1>".encode("cp1252"))
    assert len(kir.warnings) == 1
    assert "declares no encoding" in kir.warnings[0]


def test_docx_is_not_touched_by_any_of_this(hostile: None) -> None:
    """A DOCX is a zip: decoding its bytes as text would destroy it, and its parts
    carry their own encoding. The rule is HTML's, not the parser's."""
    data = (FIXTURES / "source.docx").read_bytes()
    kir = docling_kir(data, media_type=DOCX)
    assert kir.source_digest == digest_bytes(data)
    assert any(node.text for node in kir.nodes)


# ---------------------------------------------------------------------------
# The corpus this was found on
# ---------------------------------------------------------------------------


def test_every_committed_html_source_is_plain_utf8() -> None:
    """Which is why adopting the rule left the vendored corpus byte-identical.

    Not decoration: it is what makes the committed evidence documents reproducible
    from their sources on any machine, and what a future re-render has to preserve.
    A source that declared an encoding, or needed the fallback, would be read by a
    different step of the rule — legitimately, but the corpus should say so out
    loud rather than have it discovered in a diff.
    """
    sources = sorted(CORPUS_SOURCES.rglob("*.html"))
    # A floor rather than a count, so a glob that finds nothing cannot pass. It was
    # 60 while most of the corpus was an HTML distractor; roadmap 6.8 judged 66 of
    # the 81 documents, and a judged document rotates into DOCX or PDF (ADR-0056),
    # which left 37. The assertion is about the loop below having something to read.
    assert len(sources) >= 30, "a glob that finds no HTML source proves nothing"
    outcomes = {
        path.relative_to(CORPUS_SOURCES).as_posix(): read(path.read_bytes()) for path in sources
    }
    assert {outcome.rule for outcome in outcomes.values()} == {DecodeRule.UTF8}
    assert not [name for name, outcome in outcomes.items() if outcome.notes]
