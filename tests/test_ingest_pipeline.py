# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The evidence lane end to end (roadmap 4.2): acquire, store, guard, parse, store — and
the order those five happen in, which is the part that is a decision rather than a list."""

import shutil
from pathlib import Path

import pytest

from mycelium.ingest import (
    Custody,
    Registry,
    encode_kir,
    encode_report,
    ingest_source,
    write_projection,
)
from mycelium.ingest.errors import ConnectorError, ParseError, UnsupportedMediaTypeError
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.sdk.identity import canonical_json, digest_bytes
from mycelium.sdk.types import CustodyKind

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
HOSTILE = FIXTURES / "hostile"
DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"

HAVE_PANDOC = shutil.which(pandoc_parser.DEFAULT_EXECUTABLE) is not None


@pytest.fixture(scope="module")
def registry() -> Registry:
    names = ["markdown", "docling", "pdf"] + (["pandoc"] if HAVE_PANDOC else [])
    return Registry.resolve(parsers=names, connectors=["file"], roots=[FIXTURES, HOSTILE])


@pytest.fixture
def mycelium_dir(tmp_path: Path) -> Path:
    return tmp_path / ".mycelium"


@pytest.mark.parametrize(
    ("name", "parser_id"),
    [("source.md", "markdown"), ("source.docx", "docling"), ("text-layer.pdf", "pdf")],
)
def test_a_source_ends_up_in_custody_with_its_kir(
    name: str, parser_id: str, registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / name), doc_id=DOC_ID)
    custody = Custody(mycelium_dir)

    assert result.parser_id == parser_id
    assert custody.get(result.original.digest) == (FIXTURES / name).read_bytes()
    assert custody.get(result.kir_digest) == encode_kir(result.kir)

    original = custody.record(result.original.digest)
    kir_record = custody.record(result.kir_digest)
    assert original is not None and kir_record is not None
    assert original.kind is CustodyKind.ORIGINAL
    assert original.kir_digest == result.kir_digest
    assert kir_record.kind is CustodyKind.KIR
    assert kir_record.derived_from == original.digest
    # The parser that produced it is on the record, so a snapshot can explain
    # which engine compiled which document (spec 05 §4.2).
    assert kir_record.connector == parser_id


def test_the_kir_blob_is_canonical_json(registry: Registry, mycelium_dir: Path) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.md"), doc_id=DOC_ID)
    stored = Custody(mycelium_dir).get(result.kir_digest)
    assert stored is not None
    # Canonical, so the digest of a compiled document is a fact about the
    # document rather than about the machine that compiled it (spec 03 §1).
    assert stored.decode("utf-8") == canonical_json(result.kir.model_dump(mode="json"))
    assert result.kir_digest == digest_bytes(stored)


def test_ingesting_twice_changes_nothing(registry: Registry, mycelium_dir: Path) -> None:
    first = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    second = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert second.original == first.original
    assert second.kir_digest == first.kir_digest
    assert second.fidelity_digest == first.fidelity_digest
    assert second.projection == first.projection
    kinds = sorted(record.kind.value for record in Custody(mycelium_dir).records())
    assert kinds == ["fidelity", "kir", "original"], "one of each, not two"


def test_the_original_is_kept_even_when_the_parse_is_refused(
    registry: Registry, mycelium_dir: Path
) -> None:
    with pytest.raises(ParseError):
        ingest_source(mycelium_dir, registry, str(HOSTILE / "bomb.docx"), doc_id=DOC_ID)
    custody = Custody(mycelium_dir)
    records = list(custody.records())
    assert [record.kind for record in records] == [CustodyKind.ORIGINAL]
    assert custody.get(records[0].digest) == (HOSTILE / "bomb.docx").read_bytes()
    assert records[0].kir_digest is None, "nothing compiled, so nothing linked"


def test_a_source_outside_the_roots_never_reaches_custody(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("# nope\n", encoding="utf-8")
    with pytest.raises(ConnectorError, match="outside the declared root"):
        ingest_source(mycelium_dir, registry, str(outside), doc_id=DOC_ID)
    # Custody is for what was acquired; a refused acquisition acquired nothing.
    assert not Custody(mycelium_dir).root.exists()


def test_a_media_type_no_parser_reads_is_refused_before_the_write(
    mycelium_dir: Path, tmp_path: Path
) -> None:
    (tmp_path / "page.html").write_text("<p>x</p>", encoding="utf-8")
    lexical_only = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[tmp_path])
    with pytest.raises(UnsupportedMediaTypeError):
        ingest_source(mycelium_dir, lexical_only, str(tmp_path / "page.html"), doc_id=DOC_ID)
    assert not Custody(mycelium_dir).root.exists()


def test_the_ingested_document_carries_the_identity_it_was_given(
    registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert result.kir.doc_id == DOC_ID
    assert result.kir.source_digest == result.original.digest


# ---------------------------------------------------------------------------
# The fidelity report, the budget, and the projection (roadmap 4.3)
# ---------------------------------------------------------------------------


def test_the_fidelity_report_is_stored_and_linked(registry: Registry, mycelium_dir: Path) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    custody = Custody(mycelium_dir)

    assert custody.get(result.fidelity_digest) == encode_report(result.report)
    record = custody.record(result.fidelity_digest)
    assert record is not None
    assert record.kind is CustodyKind.FIDELITY
    assert record.derived_from == result.original.digest
    # And the original names it, so a build holding only the digest can find it.
    assert result.original.fidelity_digest == result.fidelity_digest


def test_a_clean_source_reports_no_loss(registry: Registry, mycelium_dir: Path) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert result.report.lost == 0
    assert result.report.elements > 0
    assert result.report.parser == result.parser_id


def test_a_source_over_budget_is_refused_but_still_accounted_for(
    registry: Registry, mycelium_dir: Path
) -> None:
    """The order in ADR-0034: the report is stored before the budget is applied.

    A refusal with no evidence behind it is not a diagnosis — an operator needs to
    see *what* was lost to decide whether to raise the budget or drop the source.
    """
    with pytest.raises(ParseError, match="did not survive parsing"):
        ingest_source(mycelium_dir, registry, str(HOSTILE / "no-text-layer.pdf"), doc_id=DOC_ID)
    kinds = [record.kind for record in Custody(mycelium_dir).records()]
    assert CustodyKind.ORIGINAL in kinds
    assert CustodyKind.FIDELITY in kinds, "the report survives the refusal"


def test_the_budget_can_be_raised_to_admit_a_total_loss(
    registry: Registry, mycelium_dir: Path
) -> None:
    result = ingest_source(
        mycelium_dir,
        registry,
        str(HOSTILE / "no-text-layer.pdf"),
        doc_id=DOC_ID,
        max_failed_elements=1.0,
    )
    assert result.report.loss == 1.0
    # The projection says so where a person reads it, not only in the report.
    assert "[!missing]" in result.projection.text


def test_the_projection_is_written_under_the_evidence_folder(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    result = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    written = write_projection(tmp_path, result)
    assert written == tmp_path / result.projection.path
    assert written.parent.name == "evidence"
    assert written.read_text(encoding="utf-8") == result.projection.text


def test_writing_the_same_projection_twice_changes_nothing(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    first = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    written = write_projection(tmp_path, first)
    stamp = written.stat().st_mtime_ns
    second = ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert write_projection(tmp_path, second) == written
    assert written.stat().st_mtime_ns == stamp, "an unchanged source leaves no diff"


def test_ingesting_writes_nothing_into_the_repository_by_itself(
    registry: Registry, mycelium_dir: Path, tmp_path: Path
) -> None:
    # `ingest_source` writes only into `.mycelium/`; putting a file into someone's
    # Git working tree is `write_projection`'s decision to be asked for.
    ingest_source(mycelium_dir, registry, str(FIXTURES / "source.docx"), doc_id=DOC_ID)
    assert not (tmp_path / "knowledge").exists()
