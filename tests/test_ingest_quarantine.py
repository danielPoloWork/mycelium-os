# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The quarantine (roadmap 4.6): spec 02 §5's three verbs — *recorded*, skipped, reported.

The first is the one this file is about, because it is the one a warning on stderr does
not deliver. A refusal has to survive the terminal it scrolled past, name the stage that
produced it, and point at the bytes that caused it — otherwise "quarantined" is just a
nicer word for dropped.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.ingest.errors import (
    ConnectorError,
    CustodyError,
    GuardError,
    LossBudgetError,
    ParseError,
    SourceTooLargeError,
    UnsupportedMediaTypeError,
)
from mycelium.ingest.quarantine import Quarantine, quarantine_root, stage_of
from mycelium.sdk.types import QuarantineStage

DIGEST = "sha256:" + "ab" * 32
URI = "file:///tmp/sources/report.pdf"
EARLIER = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def quarantine(tmp_path: Path) -> Quarantine:
    return Quarantine(tmp_path / ".mycelium")


# ---------------------------------------------------------------------------
# The stage is read off the type, never off the message
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConnectorError("outside the declared roots"), QuarantineStage.ACQUIRE),
        (SourceTooLargeError("above the ceiling"), QuarantineStage.ACQUIRE),
        (UnsupportedMediaTypeError("no pinned parser"), QuarantineStage.DISPATCH),
        (GuardError("nesting depth 512 exceeds 256"), QuarantineStage.GUARD),
        (LossBudgetError("40% lost, above the budget"), QuarantineStage.BUDGET),
        (ParseError("pandoc exited 1"), QuarantineStage.PARSE),
    ],
)
def test_the_stage_comes_from_the_error_type(error: Exception, expected: QuarantineStage) -> None:
    # 4.6 split `GuardError` and `LossBudgetError` out of `ParseError` precisely so
    # this function never has to read a sentence: a classifier that matched on
    # prose would be one reworded message away from silently mislabelling.
    assert stage_of(error) is expected  # type: ignore[arg-type]


def test_a_custody_failure_is_not_a_quarantine_stage() -> None:
    # Custody going bad is never quarantined (ADR-0033) — it is the one ingestion
    # failure that is not about *this* document — so it should never reach here.
    # If it ever does, `parse` is the honest fallback rather than a crash.
    assert stage_of(CustodyError("evidence is gone")) is QuarantineStage.PARSE


# ---------------------------------------------------------------------------
# Writing and clearing
# ---------------------------------------------------------------------------


def test_a_refusal_is_written_where_it_can_be_found(quarantine: Quarantine) -> None:
    record = quarantine.record(
        URI,
        ParseError("PDFium could not read this document"),
        media_type="application/pdf",
        source_digest=DIGEST,
    )
    assert record.source_uri == URI
    assert record.stage is QuarantineStage.PARSE
    assert record.reason == "ParseError"
    assert "PDFium" in record.detail
    assert record.source_digest == DIGEST
    assert quarantine.path_for(URI).is_file()


def test_the_record_points_at_the_bytes_that_caused_it(quarantine: Quarantine) -> None:
    # The whole reason ingestion stores the original *before* parsing (ADR-0033):
    # a quarantined file whose bytes were never kept cannot be re-examined.
    quarantine.record(URI, ParseError("boom"), source_digest=DIGEST)
    stored = quarantine.get(URI)
    assert stored is not None
    assert stored.source_digest == DIGEST


def test_a_failure_before_acquisition_has_no_digest_to_point_at(
    quarantine: Quarantine,
) -> None:
    quarantine.record("file:///tmp/gone.md", ConnectorError("cannot be resolved"))
    stored = quarantine.get("file:///tmp/gone.md")
    assert stored is not None
    assert stored.source_digest is None
    assert stored.stage is QuarantineStage.ACQUIRE


def test_re_failing_amends_one_record_rather_than_accumulating(
    quarantine: Quarantine,
) -> None:
    first = quarantine.record(URI, ParseError("boom"), now=EARLIER)
    second = quarantine.record(URI, ParseError("boom again"), now=LATER)
    assert quarantine.count() == 1
    # "Since when" is the question an operator opens the list with, so `first_seen`
    # never moves — the same rule custody's does.
    assert second.first_seen == first.first_seen == EARLIER
    assert second.last_seen == LATER
    assert second.detail == "boom again"


def test_a_source_that_starts_failing_differently_says_so(quarantine: Quarantine) -> None:
    quarantine.record(URI, UnsupportedMediaTypeError("no parser"), now=EARLIER)
    later = quarantine.record(URI, ParseError("PDFium refused it"), now=LATER)
    assert later.stage is QuarantineStage.PARSE
    assert later.first_seen == EARLIER


def test_success_clears_the_record(quarantine: Quarantine) -> None:
    quarantine.record(URI, ParseError("boom"))
    assert quarantine.clear(URI) is True
    assert quarantine.get(URI) is None
    assert quarantine.count() == 0


def test_clearing_something_that_was_never_quarantined_is_not_an_error(
    quarantine: Quarantine,
) -> None:
    # `--forget` on a healthy source: the operator asked for it to be absent from
    # the list, and it is.
    assert quarantine.clear("file:///tmp/fine.md") is False


def test_clearing_before_anything_was_ever_quarantined(tmp_path: Path) -> None:
    assert Quarantine(tmp_path / ".mycelium").clear(URI) is False


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_nothing_quarantined_is_an_empty_list_not_an_error(tmp_path: Path) -> None:
    quarantine = Quarantine(tmp_path / ".mycelium")
    assert list(quarantine.records()) == []
    assert quarantine.count() == 0


def test_records_come_back_oldest_failure_first(quarantine: Quarantine) -> None:
    quarantine.record("file:///b.md", ParseError("b"), now=LATER)
    quarantine.record("file:///a.md", ParseError("a"), now=EARLIER)
    # Filename order is digest order, which is noise; "what has been broken
    # longest" is the question.
    assert [record.source_uri for record in quarantine.records()] == [
        "file:///a.md",
        "file:///b.md",
    ]


def test_an_unreadable_record_does_not_hide_the_readable_ones(
    quarantine: Quarantine,
) -> None:
    quarantine.record(URI, ParseError("boom"))
    (quarantine.root / "not-a-record.json").write_text("{ broken", encoding="utf-8")
    # A corrupt note *about* a failure must not become a second failure that hides
    # the first: this is a diagnostic store, not evidence.
    assert [record.source_uri for record in quarantine.records()] == [URI]


def test_files_that_are_not_records_are_ignored(quarantine: Quarantine) -> None:
    quarantine.record(URI, ParseError("boom"))
    (quarantine.root / "notes.txt").write_text("scratch", encoding="utf-8")
    assert quarantine.count() == 1


def test_the_record_is_json_a_human_and_another_tool_can_read(
    quarantine: Quarantine,
) -> None:
    import json

    quarantine.record(URI, ParseError("boom"), source_digest=DIGEST)
    payload = json.loads(quarantine.path_for(URI).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "mycelium/quarantine/v0"
    assert payload["stage"] == "parse"
    assert payload["source_digest"] == DIGEST


def test_two_sources_do_not_collide(quarantine: Quarantine) -> None:
    quarantine.record("file:///a/report.pdf", ParseError("a"))
    quarantine.record("file:///b/report.pdf", ParseError("b"))
    assert quarantine.count() == 2


def test_the_root_is_beside_custody_not_inside_it(tmp_path: Path) -> None:
    mycelium_dir = tmp_path / ".mycelium"
    assert quarantine_root(mycelium_dir) == mycelium_dir / "quarantine"
    # Inside `cas/` it would be swept as a shard the garbage collector did not
    # recognise; beside it, `mycelium gc` never sees it at all.
    assert "cas" not in quarantine_root(mycelium_dir).parts


def test_garbage_collection_never_reaches_the_quarantine(tmp_path: Path) -> None:
    """The same promise ADR-0033 made for custody, for the same reason.

    A quarantine record is an operator's evidence that something is wrong. Sweeping
    it would delete the only note that a source failed — and the sweep an operator
    reaches for is exactly the one they run when the store feels too large, which
    is the worst possible moment to lose the list of what never made it in.
    """
    from mycelium.build.snapshots import collect_garbage
    from mycelium.ingest.errors import ParseError
    from mycelium.ingest.quarantine import Quarantine
    from mycelium.store import STORE_DIRNAME

    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "a.md").write_text("# A\n\ntext\n", encoding="utf-8")

    from mycelium.build.orchestrator import build

    build(tmp_path)
    quarantine = Quarantine(tmp_path / STORE_DIRNAME)
    quarantine.record("file:///tmp/broken.pdf", ParseError("PDFium refused it"))

    collect_garbage(tmp_path, keep=0, cache_max_age_days=0)

    assert quarantine.count() == 1, "the quarantine survived the most aggressive sweep"
