# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Hostile input (roadmap 4.2): every file in the hostile suite produces **one typed
failure, quickly** — never a hang, never a crash, never an unhandled exception.

The suite exists because two of these were real defects, measured rather than imagined
(ADR-0033):

- `nested.html` — 5 000 nested elements, 55 KB. docling took **45 seconds** on it, and at
  50 000 had not returned after five minutes. No byte ceiling bounds that, because the cost
  is in structure.
- The same shape made pandoc's adapter raise `RecursionError` out of `json.loads` — an
  exception nothing was catching, so a hostile document crashed ingestion instead of being
  quarantined by it.

The guards that answer them run before any engine does, and this file is where "fast" is
asserted rather than assumed: `HOSTILE_BUDGET_S` fails the suite if a defence regresses
into taking the time it was written to remove.
"""

import contextlib
import shutil
import time
from pathlib import Path

import pytest

from mycelium.ingest import Custody, Registry, ingest_source
from mycelium.ingest.errors import IngestError, ParseError
from mycelium.ingest.media import DOCX, HTML, MARKDOWN, PDF
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.ingest.parsers.builder import KirBuilder
from mycelium.ingest.safety import DEFAULT_LIMITS, Limits, guard, guard_archive, guard_markup
from mycelium.sdk.types import CustodyKind, NodeKind

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
HOSTILE = FIXTURES / "hostile"

HAVE_PANDOC = shutil.which(pandoc_parser.DEFAULT_EXECUTABLE) is not None

HOSTILE_BUDGET_S = 5.0
"""How long the whole hostile suite may take, per file, before something has regressed.

Generous by two orders of magnitude against the numbers that motivated the guards —
the point is to catch a defence that stopped working, not to benchmark a CI runner."""

# Every hostile fixture, and the outcome it must produce. `None` means "parses
# fine": a file can be malformed-looking and still be a legitimate document, and
# a suite that demanded failure everywhere would be testing its own expectations.
CASES: dict[str, str | None] = {
    "bomb.docx": "expands",
    "escaping.docx": "escapes the container",
    "laughs.docx": "docling",
    "nested.html": "nests deeper",
    "notazip.docx": "docling",
    "truncated.pdf": "PDFium could not read",
    "empty.pdf": "PDFium could not read",
    "mislabelled.md": None,
}


@pytest.fixture(scope="module")
def registry() -> Registry:
    names = ["markdown", "docling", "pdf"] + (["pandoc"] if HAVE_PANDOC else [])
    return Registry.resolve(parsers=names, connectors=["file"], roots=[HOSTILE])


def test_the_suite_is_complete() -> None:
    """A fixture nobody asserts about is a fixture that stopped being a test."""
    on_disk = {path.name for path in HOSTILE.iterdir() if path.is_file()}
    assert on_disk == set(CASES)


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_hostile_file_fails_as_one_document(
    name: str, registry: Registry, tmp_path: Path
) -> None:
    expected = CASES[name]
    started = time.perf_counter()
    try:
        result = ingest_source(
            tmp_path / ".mycelium",
            registry,
            str(HOSTILE / name),
            doc_id="01J1ZC8Q4R6XKQ3F0V9T8B2M7N",
        )
    except IngestError as error:
        assert expected is not None, f"{name} was expected to parse, and raised {error}"
        assert expected in str(error), f"{name}: {error}"
    except Exception as error:  # noqa: BLE001 - the whole point of the assertion
        pytest.fail(f"{name} raised an untyped {type(error).__name__}: {error}")
    else:
        assert expected is None, f"{name} was expected to fail with {expected!r}"
        assert result.kir is not None

    elapsed = time.perf_counter() - started
    assert elapsed < HOSTILE_BUDGET_S, f"{name} took {elapsed:.1f}s — a guard has regressed"


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_hostile_file_is_in_custody_even_when_it_cannot_be_parsed(
    name: str, registry: Registry, tmp_path: Path
) -> None:
    """Custody before compilation (ADR-0033).

    A quarantined file whose bytes were never kept cannot be re-examined, and
    re-examining them is the whole reason to quarantine rather than drop.
    """
    mycelium_dir = tmp_path / ".mycelium"
    with contextlib.suppress(IngestError):
        ingest_source(
            mycelium_dir, registry, str(HOSTILE / name), doc_id="01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
        )
    originals = [
        record for record in Custody(mycelium_dir).records() if record.kind is CustodyKind.ORIGINAL
    ]
    assert len(originals) == 1
    assert Custody(mycelium_dir).get(originals[0].digest) == (HOSTILE / name).read_bytes()


def test_the_extension_that_lies_is_parsed_as_it_claims_and_says_so(
    registry: Registry, tmp_path: Path
) -> None:
    result = ingest_source(
        tmp_path / ".mycelium",
        registry,
        str(HOSTILE / "mislabelled.md"),
        doc_id="01J1ZC8Q4R6XKQ3F0V9T8B2M7N",
    )
    assert result.parser_id == "markdown"
    assert any("application/pdf" in warning for warning in result.kir.warnings)


# ---------------------------------------------------------------------------
# The guards themselves
# ---------------------------------------------------------------------------


def test_a_decompression_bomb_is_refused_from_its_own_header() -> None:
    # The archive declares its uncompressed sizes, so no byte is decompressed to
    # find out: 51 KB on disk, 50 MB claimed.
    data = (HOSTILE / "bomb.docx").read_bytes()
    assert len(data) < 100_000
    with pytest.raises(ParseError, match="decompression bomb"):
        guard_archive(data)


def test_an_archive_member_climbing_out_is_refused() -> None:
    with pytest.raises(ParseError, match="escapes the container"):
        guard_archive((HOSTILE / "escaping.docx").read_bytes())


def test_something_that_is_not_an_archive_is_left_to_the_parser() -> None:
    # "This DOCX is not a ZIP" is a parse failure, and the engines say it
    # precisely; pre-empting it here would replace a good message with a worse one.
    guard_archive((HOSTILE / "notazip.docx").read_bytes())


def test_nesting_past_the_ceiling_is_refused_in_microseconds() -> None:
    data = (HOSTILE / "nested.html").read_bytes()
    started = time.perf_counter()
    with pytest.raises(ParseError, match="nests deeper than 256"):
        guard_markup(data)
    assert time.perf_counter() - started < 0.5, "the guard must be cheaper than the parse"


def test_the_real_fixtures_all_pass_every_guard() -> None:
    """A guard that refuses honest documents is worse than no guard."""
    for name, media_type in (
        ("source.docx", DOCX),
        ("source.html", HTML),
        ("source.md", MARKDOWN),
        ("text-layer.pdf", PDF),
    ):
        guard((FIXTURES / name).read_bytes(), media_type)


def test_a_document_of_ordinary_depth_passes() -> None:
    guard_markup(b"<html><body><div><p>a paragraph</p></div></body></html>")
    # Void elements do not open a level, or every image would count as nesting.
    guard_markup(b"<p>" + b"<br><img src='x'>" * 5000 + b"</p>")


def test_a_stray_closing_tag_cannot_drive_the_depth_negative() -> None:
    guard_markup(b"</div></div><p>text</p>")


def test_the_tag_count_ceiling_bites() -> None:
    limits = Limits(max_tags=10)
    with pytest.raises(ParseError, match="markup tags"):
        guard_markup(b"<p>x</p>" * 50, limits=limits)


def test_the_node_ceiling_stops_a_document_that_explodes_into_kir() -> None:
    builder = KirBuilder(limits=Limits(max_nodes=3))
    for _ in range(3):
        builder.add(NodeKind.PARAGRAPH, text="x")
    with pytest.raises(ParseError, match="more than 3 KIR nodes"):
        builder.add(NodeKind.PARAGRAPH, text="x")


def test_the_text_ceiling_stops_a_document_that_explodes_into_prose() -> None:
    builder = KirBuilder(limits=Limits(max_text_bytes=16))
    with pytest.raises(ParseError, match="bytes of node text"):
        builder.add(NodeKind.PARAGRAPH, text="x" * 32)


def test_the_defaults_are_generous_enough_to_be_invisible() -> None:
    # Stated as a test because the numbers are the argument: a ceiling an honest
    # document can reach is a bug report waiting to happen.
    assert DEFAULT_LIMITS.max_depth >= 256
    assert DEFAULT_LIMITS.max_tags >= 100_000
    assert DEFAULT_LIMITS.max_compression_ratio >= 100


@pytest.mark.skipif(not HAVE_PANDOC, reason="the pandoc binary is not on PATH")
def test_pandoc_refuses_a_tree_deeper_than_it_will_walk() -> None:
    """The second measured defect: recursion must be a refusal, not a stack overflow."""
    builder = KirBuilder()
    block: object = {"t": "Para", "c": [{"t": "Str", "c": "deep"}]}
    for _ in range(300):
        block = {"t": "BlockQuote", "c": [block]}
    with pytest.raises(ParseError, match="nests deeper than"):
        pandoc_parser._block(builder, block, parent=None)
